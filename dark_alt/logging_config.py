import json
import logging
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload={"timestamp":datetime.now(timezone.utc).isoformat(),"level":record.levelname,"logger":record.name,"message":record.getMessage()}
        for field in ("request_id","method","path","status_code","duration_ms"):
            if hasattr(record,field): payload[field]=getattr(record,field)
        return json.dumps(payload,ensure_ascii=False)

def configure_logging(level: str="INFO"):
    handler=logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    root=logging.getLogger(); root.handlers.clear(); root.addHandler(handler); root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return logging.getLogger("dark_alt")
