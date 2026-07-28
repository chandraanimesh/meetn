import pytest

from app.domain.policies.tts_access_policy import (
    TTSAccessPolicy,
    TTSContentSource,
)


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (
            TTSContentSource.CONFIDENTIAL_NOTE,
            "confidential_content_forbidden",
        ),
        (TTSContentSource.TRANSCRIPT, "transcript_content_forbidden"),
        (TTSContentSource.RAW_MODEL_OUTPUT, "untrusted_model_output"),
        (TTSContentSource.UNKNOWN, "unsupported_tts_source"),
    ],
)
def test_sensitive_or_untrusted_content_cannot_be_sent_to_tts(
    source: TTSContentSource,
    reason: str,
) -> None:
    decision = TTSAccessPolicy().can_synthesize(source)

    assert decision.allowed is False
    assert decision.reason == reason


def test_only_safe_backend_response_is_allowed_for_future_tts() -> None:
    decision = TTSAccessPolicy().can_synthesize(
        TTSContentSource.SAFE_ASSISTANT_RESPONSE
    )

    assert decision.allowed is True
    assert decision.reason == "safe_assistant_response"
