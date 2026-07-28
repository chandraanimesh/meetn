from collections.abc import Callable, Iterator, Mapping
from io import BytesIO
import wave

import pytest

from app.api.dependencies.services import get_llm_provider
from app.infrastructure.llm.fake_deterministic import FakeDeterministicLLM
from app.main import app
from tests.conftest import MeetingAPITestContext


@pytest.fixture
def wav_bytes() -> Callable[[float], bytes]:
    def build(duration_seconds: float) -> bytes:
        sample_rate = 8_000
        buffer = BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(1)
            output.setframerate(sample_rate)
            output.writeframes(b"\x80" * round(duration_seconds * sample_rate))
        return buffer.getvalue()

    return build


@pytest.fixture
def png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (b"\x00" * 64)


@pytest.fixture
def set_security_llm_output() -> Iterator[
    Callable[[Mapping[str, object]], FakeDeterministicLLM]
]:
    previous = app.dependency_overrides.get(get_llm_provider)
    providers: list[FakeDeterministicLLM] = []

    def configure(
        output: Mapping[str, object],
    ) -> FakeDeterministicLLM:
        provider = FakeDeterministicLLM(fixed_output=output)
        providers.append(provider)
        app.dependency_overrides[get_llm_provider] = lambda: provider
        return provider

    try:
        yield configure
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_llm_provider, None)
        else:
            app.dependency_overrides[get_llm_provider] = previous


def media_headers(
    context: MeetingAPITestContext,
    *,
    filename: str,
    media_type: str,
    request_id: str,
) -> dict[str, str]:
    session = context.client.get("/api/v1/session")
    assert session.status_code == 200
    return {
        "Content-Type": media_type,
        "X-Media-Filename": filename,
        "X-Conversation-ID": "security-conversation",
        "X-CSRF-Token": session.json()["csrf_token"],
        "X-Request-ID": request_id,
    }
