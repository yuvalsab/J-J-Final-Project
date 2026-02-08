import json
from typing import Any, Dict, List

def prompt_analyze(payload: Dict[str, Any], evidence_map: List[Dict[str, Any]]) -> str:
    em_text = "\n".join([f'{x["id"]} [{x["label"]}]: {x["text"]}' for x in evidence_map])
    schema = {
        "issue_id": "string",
        "issue_title": "string",
        "severity": "1|2|3",
        "target_error_id": "string",
        "evidence": [
            {
                "evidence_id": "E#",
                "claim": "ONE complete sentence, max 170 chars, NO ellipsis (...)",
            }
        ],
        "probable_root_causes": ["ONE complete sentence, max 140 chars"],
        "suspect_catheters": ["catheter model/name strings (optional, if present in evidence)"],
        "proposed_fix_plan": ["ONE complete sentence, max 140 chars"],
        "verification_rule": "string",
        "requested_event_keys": ["string(optional)"],
        "requested_event_types": ["string(optional)"],
    }

    return f"""
You are an RCA automation agent for CARTO/ULS investigations.

CRITICAL RULES:
- Output MUST be STRICT JSON only (no markdown, no extra text).
- You MUST NOT invent facts.
- You MAY ONLY use information found in the EVIDENCE MAP items below.
- Every evidence item MUST be an object with keys: evidence_id, claim.
- claim MUST be ONE complete sentence, max 170 chars, NO ellipsis (...).
- If catheter model/name appears in the EVIDENCE MAP, you MUST:
  (1) mention the specific catheter model/name inside each probable_root_causes sentence (not generic "the catheter"),
  (2) populate suspect_catheters with those catheter model/name values.
- If no catheter model/name is present in evidence, do NOT guess; keep suspect_catheters empty.

If you cannot provide 2 valid evidence items, you must still provide probable_root_causes and proposed_fix_plan as hypothesis-only guidance and explicitly say so in verification_rule.

Return JSON in this schema (keys required):
{json.dumps(schema, ensure_ascii=False)}

PAYLOAD:
{json.dumps(payload, ensure_ascii=False, default=str)}

EVIDENCE MAP:
{em_text}
""".strip()
