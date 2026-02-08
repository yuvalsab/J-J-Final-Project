# Builds a controlled Evidence Map for the LLM by collecting, labeling, and token-limiting
# all relevant procedure data, ensuring only verified and bounded context is used for RCA.

import json
import re
from typing import Any, Dict, List, Optional

def _clip_text_tokens_head_tail(text: str, max_tokens: int, head_ratio: float) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    tail_ratio = max(0.0, 1.0 - head_ratio)

    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base") #Give the suitable encoding for Llama3 (tokenizer)
        ids = enc.encode(t) #The token ids (list of integers)
        if len(ids) <= max_tokens:
            return t
        head_n = max(1, int(max_tokens * head_ratio))
        tail_n = max(1, int(max_tokens * tail_ratio))
        head = enc.decode(ids[:head_n])
        tail = enc.decode(ids[-tail_n:])
        return (head + "\n...[TRUNCATED_MIDDLE]...\n" + tail).strip()
    except Exception: #Fallback if tiktoken is not available
        parts = re.findall(r"\w+|[^\w\s]", t, flags=re.UNICODE) #Tokenize by words and punctuation
        if len(parts) <= max_tokens:
            return t
        head_n = max(1, int(max_tokens * head_ratio))
        tail_n = max(1, int(max_tokens * tail_ratio))
        head = " ".join(parts[:head_n]).replace("  ", " ").strip()
        tail = " ".join(parts[-tail_n:]).replace("  ", " ").strip()
        return (head + "\n...[TRUNCATED_MIDDLE]...\n" + tail).strip()


def build_evidence_map(
    proc: Dict[str, Any],
    err: Dict[str, Any],
    catheters: List[Dict[str, Any]],
    related_events: List[Dict[str, Any]],
    cross: Dict[str, Any],
    max_items: int,
    evidence_item_max_tokens: int,
    evidence_head_ratio: float,
    related_events_limit: int,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def add(obj: Any, label: str):
        if len(items) >= max_items:
            return
        items.append({"label": label, "data": obj})

    add(proc, "procedure")
    add(err, "target_error")

    for i, c in enumerate((catheters or [])[:10], start=1):
        add(c, f"catheter_{i}")

    for i, ev in enumerate((related_events or [])[:related_events_limit], start=1):
        add(ev, f"related_event_{i}")

    se = (cross or {}).get("similar_errors_other_cases") or []
    sv = (cross or {}).get("similar_events_other_cases") or []
    pa = (cross or {}).get("prior_agent_actions_for_error") or []

    for i, x in enumerate(se[:6], start=1):
        add(x, f"cross_error_{i}")
    for i, x in enumerate(sv[:6], start=1):
        add(x, f"cross_event_{i}")
    for i, x in enumerate(pa[:6], start=1):
        add(x, f"prior_action_{i}")

    evidence_map: List[Dict[str, Any]] = []
    for idx, it in enumerate(items, start=1):
        raw = json.dumps(it["data"], ensure_ascii=False, default=str)
        clipped = _clip_text_tokens_head_tail(raw, evidence_item_max_tokens, evidence_head_ratio)
        evidence_map.append({"id": f"E{idx}", "label": it["label"], "text": clipped})

    return evidence_map
