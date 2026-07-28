from collections.abc import Mapping, Sequence
import hashlib
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = frozenset(
    {
        "audio",
        "authorization",
        "body",
        "confidential",
        "content",
        "cookie",
        "image",
        "media_bytes",
        "message",
        "note",
        "password",
        "prompt",
        "raw",
        "secret",
        "token",
        "transcript",
    }
)


def media_fingerprint(content: bytes) -> tuple[str, int]:
    return hashlib.sha256(content).hexdigest(), len(content)


def redact_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    normalized_key = key.casefold() if key is not None else ""
    if _is_sensitive_key(normalized_key):
        if isinstance(value, bytes):
            media_hash, media_size = media_fingerprint(value)
            return {
                "redacted": True,
                "media_hash": media_hash,
                "media_size": media_size,
            }
        return REDACTED
    if isinstance(value, bytes):
        media_hash, media_size = media_fingerprint(value)
        return {
            "redacted": True,
            "media_hash": media_hash,
            "media_size": media_size,
        }
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_sensitive_data(
                child_value,
                key=str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return f"<{type(value).__name__}>"


def _is_sensitive_key(key: str) -> bool:
    return any(part in key for part in SENSITIVE_KEY_PARTS)
