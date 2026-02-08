import json
from typing import List, Tuple

from .scoring import score_event
from .utils import normalize_error_id

# Selector functions to pick relevant errors and events
# from cross-case data based on target error IDs and related event metadata.
def compress_error(e: dict):
    return {
        "error_id": normalize_error_id(e.get("error_id")),
        "event_type": e.get("event_type"),
        "error_frequency": e.get("error_frequency"),
        "total_events": e.get("total_events"),
        "total_duration": e.get("total_duration"),
        "first_occurrence": e.get("first_occurrence"),
        "last_occurrence": e.get("last_occurrence"),
        "extra": e.get("extra"),
    }


def compress_event(ev: dict):
    return {
        "event_key": ev.get("event_key"),
        "event_type": ev.get("event_type"),
        "total_events": ev.get("total_events"),
        "total_duration": ev.get("total_duration"),
        "first_occurrence": ev.get("first_occurrence"),
        "last_occurrence": ev.get("last_occurrence"),
        "extra": ev.get("extra"),
    }


def compress_catheter(c: dict):
    return {
        "part_number": c.get("part_number"),
        "clinical_category": c.get("clinical_category"),
        "capabilities": c.get("capabilities"),
        "electrodes": c.get("electrodes"),
        "thermocouples": c.get("thermocouples"),
        "first_occurrence": c.get("first_occurrence"),
        "last_occurrence": c.get("last_occurrence"),
        "total_events": c.get("total_events"),
        "total_duration": c.get("total_duration"),
        "extra": c.get("extra"),
    }


def compress_procedure(p: dict):
    if not isinstance(p, dict):
        return {}
    extra = p.get("extra") if isinstance(p.get("extra"), dict) else {}
    return {
        "procedure_id": p.get("procedure_id") or p.get("procedureId"),
        "start_time": p.get("start_time") or extra.get("start_time"),
        "end_time": p.get("end_time") or extra.get("end_time"),
        "system_versions": p.get("system_versions") or extra.get("versions") or p.get("versions"),
        "uls_mode": p.get("uls_mode") or extra.get("uls_mode"),
        "cpu_gpu": p.get("cpu_gpu") or extra.get("cpu_gpu"),
        "notes": p.get("notes") or extra.get("notes"),
    }


def event_keys_from_related_events(related_events: list) -> Tuple[List[str], List[str]]:
    keys = []
    types = []
    for ev in related_events:
        k = ev.get("event_key")
        t = ev.get("event_type")
        if k:
            keys.append(str(k))
        if t:
            types.append(str(t))
    keys = list(dict.fromkeys(keys))[:6]
    types = list(dict.fromkeys(types))[:6]
    return keys, types


def select_top_events_for_error(events: list, target_error_id: str, limit: int):
    tid = normalize_error_id(target_error_id)
    related = []
    for ev in events:
        ids = ev.get("error_ids")
        if not isinstance(ids, list):
            continue
        ids_norm = {normalize_error_id(x) for x in ids}
        if tid in ids_norm:
            related.append(ev)
    scored = [(score_event(ev), ev) for ev in related]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [compress_event(ev) for _, ev in scored[:limit]]


def select_events_by_keys_types(events: list, keys: list, types: list, limit: int):
    keys_set = set(str(x) for x in (keys or []))
    types_set = set(str(x) for x in (types or []))

    matched = []
    for ev in events:
        k = ev.get("event_key")
        t = ev.get("event_type")
        if (k and str(k) in keys_set) or (t and str(t) in types_set):
            matched.append(ev)

    scored = [(score_event(ev), ev) for ev in matched]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [compress_event(ev) for _, ev in scored[:limit]]


def merge_unique(a: list, b: list) -> list:
    merged = {}
    for x in (a or []) + (b or []):
        merged[json.dumps(x, sort_keys=True, default=str)] = x
    return list(merged.values())
