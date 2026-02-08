import logging
from pymongo import MongoClient, InsertOne
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
from schema_config import get_allowed_collections, get_unique_keys

load_dotenv()
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "medical_db")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

ALLOWED = set(get_allowed_collections())

class Collections:
    Procedures = "Procedures"
    Errors = "Errors"
    Catheter = "Catheter"
    Events = "Events"

def now_utc():
    return datetime.now(timezone.utc)

def _normalize_event_ids(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value.strip()]
    return [str(value)]

def _make_event_key(event_ids):
    ids = _normalize_event_ids(event_ids)
    return ",".join(sorted(ids))

def _ensure_allowed(col):
    if col not in ALLOWED:
        raise ValueError(f"Collection '{col}' is not allowed. Run init_schema.py to add it.")

def _timestamps(doc):
    now = now_utc()
    doc.setdefault("created_at", now)
    doc["updated_at"] = now

def save_document(doc: dict):
    col = doc.get("_collection")
    if not col:
        raise ValueError("Missing _collection in document")
    _ensure_allowed(col)

    payload = {k: v for k, v in doc.items() if k != "_collection"}
    _timestamps(payload)

    if col == Collections.Events:
        payload["event_ids"] = _normalize_event_ids(payload.get("event_ids"))
        payload["error_ids"] = _normalize_event_ids(payload.get("error_ids"))
        payload["event_key"] = _make_event_key(payload.get("event_ids"))

    unique_keys = get_unique_keys(col)
    if unique_keys:
        flt = {k: payload.get(k) for k in unique_keys}
        db[col].update_one(flt, {"$set": payload}, upsert=True)
        return

    db[col].insert_one(payload)

def bulk_save_events(docs):
    if not docs:
        return
    ops = []
    for d in docs:
        if d.get("_collection") != Collections.Events:
            continue
        payload = {k: v for k, v in d.items() if k != "_collection"}
        _timestamps(payload)
        payload["event_ids"] = _normalize_event_ids(payload.get("event_ids"))
        payload["error_ids"] = _normalize_event_ids(payload.get("error_ids"))
        payload["event_key"] = _make_event_key(payload.get("event_ids"))
        flt = {
            "lightning_name": payload.get("lightning_name"),
            "event_key": payload.get("event_key")
        }
        ops.append(("upsert", flt, payload))
    if not ops:
        return
    requests = []
    for typ, flt, payload in ops:
        requests.append(
            InsertOne(payload)
        )
    try:
        db[Collections.Events].bulk_write(requests, ordered=False)
    except Exception:
        for _, flt, payload in ops:
            db[Collections.Events].update_one(flt, {"$set": payload}, upsert=True)
