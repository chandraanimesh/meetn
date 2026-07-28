from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

from app.core.redaction import redact_sensitive_data
from app.core.request_context import (
    get_authenticated_user_id,
    get_request_id,
)


SAFE_EVENT_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
SAFE_EXTRA_FIELDS = (
    "request_id",
    "route",
    "method",
    "authenticated_user_id",
    "actor_user_id",
    "conversation_id",
    "input_modality",
    "media_hash",
    "media_type",
    "media_size",
    "provider",
    "model_name",
    "prompt_version",
    "selected_action_id",
    "action_id",
    "resource_id",
    "authorization_decision",
    "entitlement_decision",
    "tts_allowed",
    "duration_ms",
    "latency_ms",
    "status",
    "status_code",
    "error_code",
    "exception_type",
)


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or getattr(record, "request_id", "-")
        authenticated_user_id = get_authenticated_user_id()
        if authenticated_user_id is not None:
            record.authenticated_user_id = authenticated_user_id
        return True


class SafeStructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        raw_event = record.getMessage()
        event = (
            raw_event
            if SAFE_EVENT_PATTERN.fullmatch(raw_event)
            else "redacted_log_message"
        )
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": event,
        }
        for field_name in SAFE_EXTRA_FIELDS:
            if hasattr(record, field_name):
                payload[field_name] = redact_sensitive_data(
                    getattr(record, field_name),
                    key=field_name,
                )
        if record.exc_info is not None:
            exception_type = record.exc_info[0]
            payload["exception_type"] = (
                exception_type.__name__ if exception_type is not None else "Exception"
            )
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def configure_logging() -> None:
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    for handler in logger.handlers:
        handler.setFormatter(SafeStructuredFormatter())
        if not any(
            isinstance(existing_filter, RequestIDFilter)
            for existing_filter in handler.filters
        ):
            handler.addFilter(RequestIDFilter())
