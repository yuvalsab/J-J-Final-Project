# Defines the RCA agent configuration (defaults) and utilities to load/merge overrides from a JSON file.
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RcaConfig:
    max_iters: int = 3
    limit_errors: int = 250
    limit_events: int = 250
    limit_catheters: int = 50
    weight_freq: float = 10.0
    weight_dur: float = 1.0 / 60.0  # Converts seconds contribution to minutes scale for scoring.
    weight_recency: float = 1.0
    evidence_max_items: int = 40
    evidence_item_max_tokens: int = 420  # Caps per-evidence chunk size to avoid blowing the LLM context.
    evidence_head_ratio: float = 0.70    # Prefer the beginning of long evidence (usually has IDs/timestamps).
    related_events_limit: int = 25
    more_events_after_fail_limit: int = 45
    fetch_by_keys_types_limit: int = 35
    cross_case_limit: int = 6
    llm_timeout_s: int = 3600
    llm_retries: int = 2
    llm_temperature: float = 0.2
    llm_model: str = "llama3"
    parallelism: int = 20  # Max concurrent tasks/queries to speed up data retrieval/processing.

def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    if not config_path:
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f) if f.readable() else {}
    except Exception:
        return {}  # Fail-safe: config is optional; defaults will be used.

def config_from_dict(d: Dict[str, Any]) -> RcaConfig:
    cfg = RcaConfig()
    for k, v in d.items():
        if hasattr(cfg, k): # check if the field exists in the dataclass
            try:
                t = type(getattr(cfg, k))  # Cast overrides to the same type as the default field.
                setattr(cfg, k, t(v))
            except Exception:
                setattr(cfg, k, v)  # Fallback if casting fails (keeps system running).
    return cfg
