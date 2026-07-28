import httpx
import pytest
from pydantic import SecretStr

from app.agent.action_models import AgentDecision
from app.application.exceptions import (
    LLMProviderResponseError,
    LLMProviderUnavailableError,
)
from app.infrastructure.llm.groq_provider import GroqLLMProvider


SAFE_CONTEXT = {
    "authenticated_user": {"display_name": "Security Test"},
    "page_manifest": {
        "page_id": "dashboard",
        "active_meeting_id": None,
        "visible_meeting_ids": (),
    },
    "registered_actions": (
        {
            "action_id": "open_dashboard",
            "required_parameters": ("meeting_id",),
        },
    ),
}


async def _decide(provider: GroqLLMProvider) -> object:
    return await provider.decide(
        instructions="Return structured output.",
        user_message="untrusted STT or OCR text",
        safe_context=SAFE_CONTEXT,
        output_schema=AgentDecision.model_json_schema(),
    )


@pytest.mark.asyncio
async def test_provider_timeout_fails_closed_without_sensitive_detail() -> None:
    secret = "raw-spoken-prompt-secret"

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(secret, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        provider = GroqLLMProvider(client, SecretStr("provider-secret"))
        with pytest.raises(LLMProviderUnavailableError) as error:
            await _decide(provider)

    assert secret not in str(error.value)
    assert "provider-secret" not in str(error.value)


@pytest.mark.asyncio
async def test_provider_malformed_json_is_rejected() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=b'{"choices":[{"message":{"content":"not-json"}}]}',
            )
        )
    ) as client:
        with pytest.raises(LLMProviderResponseError):
            await _decide(GroqLLMProvider(client, SecretStr("provider-secret")))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            429,
            json={"error": {"message": "raw-provider-rate-limit-detail"}},
        ),
        httpx.Response(200, json={"choices": []}),
    ],
)
async def test_provider_rate_limit_or_partial_failure_fails_closed(
    response: httpx.Response,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as client:
        error_type = (
            LLMProviderUnavailableError
            if response.status_code == 429
            else LLMProviderResponseError
        )
        with pytest.raises(error_type) as error:
            await _decide(GroqLLMProvider(client, SecretStr("provider-secret")))

    assert "raw-provider-rate-limit-detail" not in str(error.value)
    assert "provider-secret" not in str(error.value)
