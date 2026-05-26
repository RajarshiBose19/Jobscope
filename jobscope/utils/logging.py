"""Structured JSONL logging."""
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

class JsonlFormatter(logging.Formatter):
    RESERVED = {
        "name","msg","args","levelname","levelno","pathname","filename",
        "module","exc_info","exc_text","stack_info","lineno","funcName",
        "created","msecs","relativeCreated","thread","threadName",
        "processName","process","message","asctime","taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self.RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

def configure_logging(log_path: Path, level: int = logging.INFO) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    file_h = RotatingFileHandler(
        log_path, maxBytes=10_000_000, backupCount=3, encoding="utf-8"
    )
    file_h.setFormatter(JsonlFormatter())
    root.addHandler(file_h)
    stderr_h = logging.StreamHandler()
    stderr_h.setFormatter(JsonlFormatter())
    root.addHandler(stderr_h)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
