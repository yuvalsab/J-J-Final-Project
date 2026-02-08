# Utilities for cleaning/coercing the LLM "decision" JSON and determining whether
# the output is good enough or should be marked as NEEDS_HUMAN_REVIEW.

from typing import Any, Dict, List, Tuple
from .utils import ensure_sentence, normalize_error_id

def clean_placeholders(xs: Any) -> List[str]:
    if not isinstance(xs, list):
        return []
    out: List[str] = []
    for x in xs:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if not s:
            continue
        if s.lower() in {"string", "n/a", "na", "none", "null"}:
            continue
        if s == "...":
            continue
        out.append(s)
    return out


def coerce_decision_lists(d: Dict[str, Any]) -> Dict[str, Any]:
    plan = d.get("proposed_fix_plan")
    if isinstance(plan, list):
        d["proposed_fix_plan"] = [str(x).strip() for x in plan if str(x).strip()]
    elif isinstance(plan, str) and plan.strip():
        d["proposed_fix_plan"] = [plan.strip()]
    else:
        d["proposed_fix_plan"] = []

    rc = d.get("probable_root_causes")
    if isinstance(rc, list):
        d["probable_root_causes"] = [str(x).strip() for x in rc if str(x).strip()]
    elif isinstance(rc, str) and rc.strip():
        d["probable_root_causes"] = [rc.strip()]
    else:
        d["probable_root_causes"] = []

    ev = d.get("evidence")
    if isinstance(ev, list):
        fixed = []
        for x in ev:
            if isinstance(x, dict):
                eid = x.get("evidence_id")
                claim = x.get("claim")
                if isinstance(eid, str) and isinstance(claim, str):
                    s = claim.strip()
                    if s and s.lower() not in {"string", "n/a", "none"} and s != "...":
                        fixed.append({"evidence_id": eid.strip(), "claim": ensure_sentence(s, 170)})
        d["evidence"] = fixed
    else:
        d["evidence"] = []
    sc = d.get("suspect_catheters")
    if isinstance(sc, list):
        d["suspect_catheters"] = [str(x).strip() for x in sc if str(x).strip()]
    elif isinstance(sc, str) and sc.strip():
        d["suspect_catheters"] = [sc.strip()]
    else:
        d["suspect_catheters"] = []    

    return d


def validate_decision_quality(
    decision: Dict[str, Any],
    evidence_map: List[Dict[str, Any]],
    min_evidence: int,
    require_plan_steps: int,
    require_root_causes: int,
) -> Tuple[bool, Any]:
    em_ids = {x.get("id") for x in (evidence_map or []) if isinstance(x, dict)}
    ev = decision.get("evidence")
    if not isinstance(ev, list) or not ev:
        return False, {"reason": "no_evidence_array"}

    used_ok = []
    for item in ev:
        if not isinstance(item, dict):
            continue
        eid = item.get("evidence_id")
        if isinstance(eid, str) and eid in em_ids:
            used_ok.append(eid)

    if len(used_ok) < min_evidence:
        return False, {"reason": "insufficient_valid_evidence_refs", "used_ok": used_ok, "min": min_evidence}

    if len(decision.get("proposed_fix_plan", [])) < require_plan_steps:
        return False, {"reason": "missing_plan_steps", "have": len(decision.get("proposed_fix_plan", [])), "need": require_plan_steps}

    if len(decision.get("probable_root_causes", [])) < require_root_causes:
        return False, {"reason": "missing_root_causes", "have": len(decision.get("probable_root_causes", [])), "need": require_root_causes}

    return True, {"used_ok": used_ok, "evidence_count": len(used_ok)}


def make_needs_human_review(
    lightning_name: str,
    target_error_id: str,
    decision: Dict[str, Any],
    reason: str,
    meta: Any,
) -> Dict[str, Any]:
    me = clean_placeholders(decision.get("missing_evidence"))
    sq = clean_placeholders(decision.get("suggested_next_queries"))

    if not sq:
        sq = [
            "Fetch raw log snippets around first and last occurrences for this error_id.",
            "Extract nearest events before/after each occurrence with subsystem, ULS mode, and catheter markers.",
            "Compare patterns across similar cases where the same error_id appears.",
        ]

    out = {
        "status": "NEEDS_HUMAN_REVIEW",
        "human_alert": True,
        "issue_id": f"{lightning_name}-ERR-{target_error_id}",
        "issue_title": f"Target Error {target_error_id}",
        "severity": 2,
        "target_error_id": normalize_error_id(target_error_id),
        "evidence": decision.get("evidence", []),
        "suspect_catheters": decision.get("suspect_catheters") if isinstance(decision.get("suspect_catheters"), list) else [],
        "probable_root_causes": decision.get("probable_root_causes", []),
        "proposed_fix_plan": decision.get("proposed_fix_plan", []),
        "verification_rule": ensure_sentence(
            f"NEEDS_HUMAN_REVIEW: insufficient evidence for verified RCA (reason={reason}).",
            200,
        ),
        "missing_evidence": me,
        "suggested_next_queries": [ensure_sentence(x, 160) for x in sq][:8],
        "verified_findings": [],
        "requested_event_keys": decision.get("requested_event_keys") if isinstance(decision.get("requested_event_keys"), list) else [],
        "requested_event_types": decision.get("requested_event_types") if isinstance(decision.get("requested_event_types"), list) else [],
        "quality_meta": meta,
    }
    return out
