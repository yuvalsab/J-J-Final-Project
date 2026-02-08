import json
import logging
from datetime import datetime

import json
import logging
from datetime import datetime

# JSON-based structured logger for the RCA Agent.
# Emits machine-readable log events with timestamps and contextual metadata
# to support debugging, tracing, and auditability.

class JsonLogger:
    def __init__(self, name: str = "rca_agent", level: str = "INFO"):
        self.logger = logging.getLogger(name) # Get or create logger
        if self.logger.handlers: # Avoid adding multiple handlers
            return
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        h = logging.StreamHandler()
        h.setLevel(getattr(logging, level.upper(), logging.INFO))
        h.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(h)

    def log(self, level: str, event: str, **kvs):
        payload = {
            "ts_utc": datetime.utcnow().isoformat(),
            "level": level.upper(),
            "event": event,
            **kvs,
        }
        msg = json.dumps(payload, ensure_ascii=False, default=str)
        getattr(self.logger, level.lower(), self.logger.info)(msg)


