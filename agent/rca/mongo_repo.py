from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pymongo import MongoClient

from .utils import error_id_filter, normalize_error_id

# MongoDB repository layer for the RCA Agent.
# Encapsulates all database reads/writes: fetching a case context, cross-case retrieval,
# and persisting/validating agent actions and resolutions.


class MongoRepo:
    def __init__(self, mongo_uri: str, db_name: str):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

    def list_collections(self) -> List[str]:
        return self.db.list_collection_names() # List all collection names in the database

    def fetch_case_context(self, lightning_name: str, le: int, lv: int, lc: int) -> Dict[str, Any]: # Fetch case context
        errors = list(self.db["Errors"].find({"lightning_name": lightning_name}, {"_id": 0}).limit(le))
        events = list(self.db["Events"].find({"lightning_name": lightning_name}, {"_id": 0}).limit(lv))
        catheters = list(self.db["Catheter"].find({"lightning_name": lightning_name}, {"_id": 0}).limit(lc))
        procedure = self.db["Procedures"].find_one({"lightning_name": lightning_name}, {"_id": 0})
        if not procedure:
            procedure = self.db["Procedures"].find_one({"lightningName": lightning_name}, {"_id": 0}) or {} 

        return {"procedure": procedure, "errors": errors, "events": events, "catheters": catheters}

    def retrieve_cross_case_context(
        self,
        current_lightning_name: str,
        target_error_id: str,
        related_event_keys: List[str],
        related_event_types: List[str],
        limit_cases: int,
    ) -> Dict[str, Any]:
        tid = normalize_error_id(target_error_id)
        err_filter = error_id_filter(tid)

        other_errors = list(
            self.db["Errors"]
            .find({"error_id": err_filter, "lightning_name": {"$ne": current_lightning_name}}, {"_id": 0})
            .limit(limit_cases)
        )

        ev_query: Dict[str, Any] = {"lightning_name": {"$ne": current_lightning_name}} 
        ev_or = []
        if related_event_keys:
            ev_or.append({"event_key": {"$in": related_event_keys}})
        if related_event_types:
            ev_or.append({"event_type": {"$in": related_event_types}})
        if ev_or:
            ev_query["$or"] = ev_or
            other_events = list(self.db["Events"].find(ev_query, {"_id": 0}).limit(limit_cases))
        else:
            other_events = []

        prior_actions = list(
            self.db.get_collection("AgentActions", read_preference=None)
            .find({"target_error_id": err_filter, "lightning_name": {"$ne": current_lightning_name}}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(6)
        )

        def compact_action(a):
            return {
                "lightning_name": a.get("lightning_name"),
                "timestamp": a.get("timestamp"),
                "issue_title": a.get("issue_title"),
                "severity": a.get("severity"),
                "target_error_id": normalize_error_id(a.get("target_error_id")),
                "root_causes": a.get("root_causes"),
                "plan": a.get("plan"),
                "verification_rule": a.get("verification_rule"),
                "source": a.get("source"),
                "status": a.get("status"),
                "llm_hypothesis": a.get("llm_hypothesis"),
            }

        return {
            "similar_errors_other_cases": other_errors,
            "similar_events_other_cases": other_events,
            "prior_agent_actions_for_error": [compact_action(x) for x in prior_actions],
        }

    def insert_action_and_resolution(self, lightning_name: str, action_doc: Dict[str, Any], resolution_doc: Dict[str, Any]):
        self.db["AgentActions"].insert_one(action_doc)
        self.db["AgentResolutions"].insert_one(resolution_doc)

    def verify_resolution(self, lightning_name: str, target_error_id: str) -> Optional[Dict[str, Any]]:
        target_error_id = normalize_error_id(target_error_id)
        if not target_error_id:
            return None
        return self.db["AgentResolutions"].find_one(
            {
                "lightning_name": lightning_name,
                "target_error_id": target_error_id,
                "type": {"$in": ["AI_RESOLVED", "AI_NEEDS_HUMAN_REVIEW"]},
            },
            {"_id": 0},
        )
