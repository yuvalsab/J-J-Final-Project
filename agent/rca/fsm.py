# This module implements the core finite-state workflow of the RCA Agent.
# It orchestrates iterative evidence collection, LLM reasoning, decision validation,
# and controlled fallback to human review, ensuring evidence-backed and auditable analysis.

import asyncio
from typing import Any, Dict, List, Optional

from .decision import coerce_decision_lists, make_needs_human_review, validate_decision_quality
from .evidence import build_evidence_map
from .prompt import prompt_analyze
from .selectors import event_keys_from_related_events, merge_unique
from .utils import ensure_sentence, normalize_error_id, safe_json


class AgentFSM:
    def __init__(
        self,
        repo,
        llm,
        log,
        cfg,
        selectors,
    ):
        self.repo = repo
        self.llm = llm
        self.log = log
        self.cfg = cfg
        self.selectors = selectors
        self.last_evidence_map = []  # NEW: keep latest evidence map for optional external use

    def _state(self, name: str, **kvs):
        self.log.log("info", "AGENT_STATE", state=name, **kvs)

    def run_sync(self, lightning_name: str, ctx: dict, target_error: dict, base_related_events: list, max_iters: Optional[int] = None):
        max_iters = int(max_iters or self.cfg.max_iters)
        err = self.selectors.compress_error(target_error)
        target_error_id = err["error_id"]
        proc_compact = self.selectors.compress_procedure(ctx.get("procedure") or {})
        catheters_compact = [self.selectors.compress_catheter(c) for c in (ctx.get("catheters") or [])[:10]]
        events_all = ctx.get("events") or []

        selected = list(base_related_events)
        seen_keys = set()
        seen_types = set()
        last_cross = {}

        for i in range(max_iters):  # main iteration loop for reasoning
            self._state("ITERATION_START", i=i + 1, max_iters=max_iters, selected_events=len(selected), target_error_id=target_error_id)
            related_event_keys, related_event_types = event_keys_from_related_events(selected)

            self._state("CROSS_CASE_RETRIEVE_START", keys=len(related_event_keys), types=len(related_event_types))
            cross = self.repo.retrieve_cross_case_context(
                current_lightning_name=lightning_name,
                target_error_id=target_error_id,
                related_event_keys=related_event_keys,
                related_event_types=related_event_types,
                limit_cases=self.cfg.cross_case_limit,
            )
            last_cross = cross  # save for potential final attempt

            self._state(
                "CROSS_CASE_RETRIEVED",
                cross_errors=len(cross.get("similar_errors_other_cases", [])),
                cross_events=len(cross.get("similar_events_other_cases", [])),
                prior_actions=len(cross.get("prior_agent_actions_for_error", [])),
            )

            payload = {
                "lightning_name": lightning_name,
                "procedure": proc_compact,
                "catheters": catheters_compact,
                "target_error": err,
                "related_events": selected[: self.cfg.related_events_limit],
                "cross_case_learning": cross,
            }

            evidence_map = build_evidence_map(
                proc=proc_compact,
                err=err,
                catheters=catheters_compact,
                related_events=selected[: self.cfg.related_events_limit],
                cross=cross,
                max_items=self.cfg.evidence_max_items,
                evidence_item_max_tokens=self.cfg.evidence_item_max_tokens,
                evidence_head_ratio=self.cfg.evidence_head_ratio,
                related_events_limit=self.cfg.related_events_limit,
            )
            self.last_evidence_map = evidence_map  # NEW
            self._state("EVIDENCE_MAP_BUILT", evidence_items=len(evidence_map), related_events=len(selected[: self.cfg.related_events_limit]))

            prompt = prompt_analyze(payload, evidence_map)

            self._state("LLM_CALL_ANALYZE_START", timeout_s=self.cfg.llm_timeout_s)
            out = self.llm.call_sync(prompt)
            self._state("LLM_CALL_ANALYZE_DONE", out_chars=len(out) if isinstance(out, str) else "n/a")

            decision = safe_json(out)
            decision.setdefault("issue_id", f"{lightning_name}-ERR-{target_error_id}")
            decision.setdefault("issue_title", f"Target Error {target_error_id}")
            decision.setdefault("severity", 2)
            decision["target_error_id"] = normalize_error_id(decision.get("target_error_id") or target_error_id)

            decision = coerce_decision_lists(decision)
            decision["evidence_map"] = evidence_map  # NEW: persist evidence map into JSON for UI traceability
            decision["probable_root_causes"] = [ensure_sentence(x, 140) for x in decision.get("probable_root_causes", []) if isinstance(x, str) and x.strip()][:8]
            decision["proposed_fix_plan"] = [ensure_sentence(x, 140) for x in decision.get("proposed_fix_plan", []) if isinstance(x, str) and x.strip()][:12]

            self._state(
                "VALIDATE_START",
                evidence_items=len(decision.get("evidence", [])),
                plan_steps=len(decision.get("proposed_fix_plan", [])),
                root_causes=len(decision.get("probable_root_causes", [])),
            )

            ok, meta = validate_decision_quality(
                decision,
                evidence_map,
                min_evidence=2,
                require_plan_steps=1,
                require_root_causes=1,
            )
            self._state("VALIDATE_DONE", ok=ok, meta=meta)

            # Extract any new requested event keys/types
            req_keys = decision.get("requested_event_keys") or []
            req_types = decision.get("requested_event_types") or []
            req_keys = [str(x) for x in req_keys] if isinstance(req_keys, list) else []
            req_types = [str(x) for x in req_types] if isinstance(req_types, list) else []

            if ok:  # successful decision - check for more requests
                new_keys = [k for k in req_keys if k and k not in seen_keys]
                new_types = [t for t in req_types if t and t not in seen_types]
                decision["status"] = "SUCCESS"
                decision["verification_rule"] = ensure_sentence(decision.get("verification_rule") or "SUCCESS: evidence-backed RCA (llama3).", 180)  # add default if missing

                # no new requests - return success
                if not new_keys and not new_types:
                    self._state("SUCCESS_RETURN", reason="valid_quality_and_no_more_requests")
                    return decision
                # new requests - fetch and continue the loop
                for k in new_keys:
                    seen_keys.add(k)
                for t in new_types:
                    seen_types.add(t)

                self._state("ASK_FOR_MORE_CONTEXT", new_keys=len(new_keys), new_types=len(new_types))
                extra = self.selectors.select_events_by_keys_types(events_all, new_keys, new_types, limit=self.cfg.fetch_by_keys_types_limit)
                self._state("FETCH_BY_KEYS_TYPES_DONE", fetched=len(extra))

                selected = merge_unique(selected, extra)
                self._state("MERGE_DONE", selected_events=len(selected))
                continue

            # failed quality - try to fetch more evidence
            if req_keys or req_types:
                new_keys = [k for k in req_keys if k and k not in seen_keys]
                new_types = [t for t in req_types if t and t not in seen_types]

                for k in new_keys:
                    seen_keys.add(k)
                for t in new_types:
                    seen_types.add(t)

                self._state("ASK_FOR_MORE_CONTEXT_AFTER_FAIL", new_keys=len(new_keys), new_types=len(new_types))
                extra = self.selectors.select_events_by_keys_types(events_all, new_keys, new_types, limit=self.cfg.fetch_by_keys_types_limit)
                self._state("FETCH_BY_KEYS_TYPES_DONE", fetched=len(extra))

                selected = merge_unique(selected, extra)
                self._state("MERGE_DONE", selected_events=len(selected))
                continue

            # no specific requests - fetch top events for the error_id
            self._state("FETCH_MORE_EVIDENCE_FOR_ERROR", target_error_id=target_error_id)
            extra = self.selectors.select_top_events_for_error(events_all, target_error_id, limit=self.cfg.more_events_after_fail_limit)
            self._state("FETCH_MORE_EVIDENCE_DONE", fetched=len(extra))
            selected = merge_unique(selected, extra)
            self._state("MERGE_DONE", selected_events=len(selected))

        # max iterations exhausted - final attempt with all gathered evidence
        self._state("ITERATIONS_EXHAUSTED", selected_events=len(selected))

        # Get cross-case context one last time
        related_event_keys, related_event_types = event_keys_from_related_events(selected)
        cross = last_cross or self.repo.retrieve_cross_case_context(
            current_lightning_name=lightning_name,
            target_error_id=target_error_id,
            related_event_keys=related_event_keys,
            related_event_types=related_event_types,
            limit_cases=self.cfg.cross_case_limit,
        )
        # Prepare final payload
        payload = {
            "lightning_name": lightning_name,
            "procedure": proc_compact,
            "catheters": catheters_compact,
            "target_error": err,
            "related_events": selected[: self.cfg.related_events_limit],
            "cross_case_learning": cross,
        }

        # Build final evidence map
        evidence_map = build_evidence_map(
            proc=proc_compact,
            err=err,
            catheters=catheters_compact,
            related_events=selected[: self.cfg.related_events_limit],
            cross=cross,
            max_items=self.cfg.evidence_max_items,
            evidence_item_max_tokens=self.cfg.evidence_item_max_tokens,
            evidence_head_ratio=self.cfg.evidence_head_ratio,
            related_events_limit=self.cfg.related_events_limit,
        )
        self.last_evidence_map = evidence_map  # NEW

        self._state("RETURN_NEEDS_HUMAN_REVIEW_PREP", evidence_items=len(evidence_map), related_events=len(selected[: self.cfg.related_events_limit]))

        prompt = prompt_analyze(payload, evidence_map)
        self._state("LLM_CALL_FINAL_ATTEMPT_START", timeout_s=self.cfg.llm_timeout_s)
        out = self.llm.call_sync(prompt)
        self._state("LLM_CALL_FINAL_ATTEMPT_DONE", out_chars=len(out) if isinstance(out, str) else "n/a")

        # Process final decision
        decision = safe_json(out)
        decision.setdefault("issue_id", f"{lightning_name}-ERR-{target_error_id}")
        decision.setdefault("issue_title", f"Target Error {target_error_id}")
        decision.setdefault("severity", 2)
        decision["target_error_id"] = normalize_error_id(decision.get("target_error_id") or target_error_id)
        decision = coerce_decision_lists(decision)
        decision["evidence_map"] = evidence_map  # NEW: persist evidence map into JSON for UI traceability

        ok, meta = validate_decision_quality(decision, evidence_map, min_evidence=2, require_plan_steps=1, require_root_causes=1)
        if ok:
            decision["status"] = "SUCCESS"
            decision["verification_rule"] = ensure_sentence(decision.get("verification_rule") or "SUCCESS: evidence-backed RCA (llama3).", 180)
            self._state("SUCCESS_RETURN_AFTER_FINAL_ATTEMPT")
            return decision

        needs = make_needs_human_review(
            lightning_name=lightning_name,
            target_error_id=target_error_id,
            decision=decision,
            reason=str(meta.get("reason") if isinstance(meta, dict) else "validation_failed"),
            meta=meta,
        )
        self._state("NEEDS_HUMAN_REVIEW_RETURN")
        return needs

    # End of run_sync
    async def run_async(self, lightning_name: str, ctx: dict, target_error: dict, base_related_events: list, max_iters: Optional[int] = None):
        return await asyncio.to_thread(self.run_sync, lightning_name, ctx, target_error, base_related_events, max_iters)
