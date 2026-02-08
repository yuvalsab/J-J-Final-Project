import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

# Utility functions for the RCA Agent: text clipping, evidence map building,
# safe JSON extraction, error ID normalization, filters, duration and datetime parsing,
def safe_json(text: str) -> Dict[str, Any]:
    t = (text or "").strip()

    m = re.search(r"```json\s*(\{.*?\})\s*```", t, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    i = t.find("{")
    j = t.rfind("}")
    if i != -1 and j != -1 and j > i:
        cand = t[i : j + 1]
        try:
            return json.loads(cand)
        except Exception:
            pass

    objs = re.findall(r"\{.*\}", t, flags=re.DOTALL)
    for cand in reversed(objs):
        try:
            return json.loads(cand)
        except Exception:
            continue
    return {"raw": text, "json_error": "no_json_found"}


def normalize_error_id(x):
    if x is None:
        return None
    if isinstance(x, int):
        return str(x)
    if isinstance(x, str):
        return x.strip()
    return str(x).strip()


def error_id_filter(target_error_id: str):
    tid = normalize_error_id(target_error_id)
    if tid and tid.isdigit():
        return {"$in": [tid, int(tid)]}
    return tid


def parse_duration_seconds(v):
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return 0.0
    s = v.strip()
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", s)
    if m:
        h, mi, se = m.groups()
        return int(h) * 3600 + int(mi) * 60 + int(se)
    return 0.0


def parse_occurrence_dt(v):
    if isinstance(v, datetime):
        return v
    if not isinstance(v, str):
        return None
    s = v.strip()
    for fmt in ("%Y.%m.%d_%H.%M.%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def ensure_sentence(s: str, max_len: int = 140) -> str:
    x = (s or "").strip()
    x = re.sub(r"\s+", " ", x)
    x = x.replace("...", ".")
    x = x.replace("..", ".")
    if not x:
        return ""
    if len(x) <= max_len:
        return x if x.endswith((".", "!", "?")) else x + "."
    cut = x[:max_len].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    cut = cut.rstrip(".,;:-")
    return cut + "."


def safe_filename(s: str) -> str:
    x = (s or "").strip()
    x = re.sub(r"[^\w\-.]+", "_", x, flags=re.UNICODE)
    x = re.sub(r"_+", "_", x)
    x = x.strip("._")
    return x or "export"
