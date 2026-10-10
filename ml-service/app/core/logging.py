import contextvars
import json
import logging
from datetime import datetime, timezone
from typing import Any

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
        }
        event = getattr(record, "event", None)
        if isinstance(event, str):
            entry["event"] = event
        error_type = getattr(record, "error_type", None)
        if isinstance(error_type, str):
            entry["error_type"] = error_type
        for field in (
            "failure_code",
            "model_load_time_ms",
            "startup_elapsed_ms",
            "process_memory_bytes",
            "model_loaded",
            "model_version",
            "previous_model_retained",
        ):
            value = getattr(record, field, None)
            if isinstance(value, (str, int, float, bool)) or value is None:
                if hasattr(record, field):
                    entry[field] = value
        return json.dumps(entry, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(value: str) -> contextvars.Token[str]:
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token[str]) -> None:
    _request_id.reset(token)
