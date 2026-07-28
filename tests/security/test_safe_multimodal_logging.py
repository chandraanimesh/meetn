import json
import logging

from app.core.logging import SafeStructuredFormatter
from app.core.redaction import media_fingerprint, redact_sensitive_data


def test_raw_media_and_sensitive_text_cannot_appear_in_structured_logs() -> None:
    raw_media = b"\x89PNG\r\n\x1a\nraw-media-secret"
    transcript = "raw STT transcript secret"
    note = "confidential note secret"
    record = logging.LogRecord(
        name="app.security",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="media_validation_rejected",
        args=(),
        exc_info=None,
    )
    record.request_id = "safe-log-request"
    record.route = "/api/multimodal/media/validate"
    record.method = "POST"
    expected_hash, _ = media_fingerprint(raw_media)
    record.media_hash = expected_hash
    record.media_size = len(raw_media)
    record.raw_audio = raw_media
    record.raw_image = raw_media
    record.transcript = transcript
    record.confidential_note = note

    rendered = SafeStructuredFormatter().format(record)
    payload = json.loads(rendered)

    assert payload["request_id"] == "safe-log-request"
    assert payload["route"] == "/api/multimodal/media/validate"
    assert payload["media_size"] == len(raw_media)
    assert raw_media.hex() not in rendered
    assert "raw-media-secret" not in rendered
    assert transcript not in rendered
    assert note not in rendered


def test_redaction_replaces_binary_and_sensitive_mapping_values() -> None:
    raw_media = b"binary-secret"
    redacted = redact_sensitive_data(
        {
            "audio": raw_media,
            "transcript": "protected transcript",
            "request_id": "request-1",
        }
    )

    expected_hash, expected_size = media_fingerprint(raw_media)
    assert redacted["audio"]["media_hash"] == expected_hash
    assert redacted["audio"]["media_size"] == expected_size
    assert redacted["transcript"] == "[REDACTED]"
    assert redacted["request_id"] == "request-1"
