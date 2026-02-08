from typing import List, Optional, Tuple

from .utils import normalize_error_id, parse_duration_seconds, parse_occurrence_dt

# Scoring functions to evaluate and rank errors and events
# based on frequency, duration, recency, and extra metadata.    
def score_error(e: dict, weight_freq: float, weight_dur: float, weight_recency: float) -> float:
    freq = e.get("error_frequency")
    try:
        freq = float(freq)
    except Exception:
        freq = 0.0

    dur = parse_duration_seconds(e.get("total_duration"))
    last_dt = parse_occurrence_dt(e.get("last_occurrence"))

    recency_bonus = 0.0
    if last_dt:
        recency_bonus = (last_dt.timestamp() / 1e12) * weight_recency

    return (freq * weight_freq) + (dur * weight_dur) + recency_bonus


def score_event(ev: dict) -> float:
    total_events = ev.get("total_events")
    try:
        total_events = float(total_events)
    except Exception:
        total_events = 0.0

    dur = parse_duration_seconds(ev.get("total_duration"))
    last_dt = parse_occurrence_dt(ev.get("last_occurrence"))

    recency_bonus = 0.0
    if last_dt:
        recency_bonus = last_dt.timestamp() / 1e12

    has_extra_bonus = 0.2 if ev.get("extra") else 0.0
    return total_events * 5.0 + dur / 30.0 + recency_bonus + has_extra_bonus


def pick_two_distinct_errors(
    errors: list,
    weight_freq: float,
    weight_dur: float,
    weight_recency: float,
) -> Tuple[Optional[dict], Optional[dict]]:
    scored = []
    for e in errors:
        eid = normalize_error_id(e.get("error_id"))
        if not eid:
            continue
        scored.append((score_error(e, weight_freq, weight_dur, weight_recency), eid, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None, None
    first = scored[0][2] 
    first_id = normalize_error_id(first.get("error_id"))
    second = None
    for _, eid, e in scored[1:]:
        if eid != first_id:
            second = e
            break
    return first, second
