from pydantic import SecretStr

from app.core.config import GroqSettings


def test_groq_api_key_is_optional_and_masked() -> None:
    unconfigured = GroqSettings(groq_api_key=None)
    configured = GroqSettings(
        groq_api_key=SecretStr("test-groq-key"),
    )

    assert unconfigured.groq_api_key is None
    assert isinstance(configured.groq_api_key, SecretStr)
    assert configured.groq_api_key.get_secret_value() == "test-groq-key"
    assert "test-groq-key" not in repr(configured)
    assert configured.groq_model == "openai/gpt-oss-20b"
    assert configured.groq_timeout_seconds == 30.0
    assert configured.groq_max_completion_tokens == 1_024
    assert configured.groq_reasoning_effort == "low"
