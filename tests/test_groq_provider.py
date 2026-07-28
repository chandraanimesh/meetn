import json
from typing import Any

import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.agent.action_models import AgentDecision
from app.api.dependencies.services import get_llm_provider
from app.application.exceptions import (
    LLMProviderResponseError,
    LLMProviderUnavailableError,
)
from app.core.config import settings
from app.infrastructure.llm.groq_provider import GroqLLMProvider
from app.main import create_app


def _safe_context() -> dict[str, object]:
    return {
        "authenticated_user": {"display_name": "Test User"},
        "page_manifest": {
            "page_id": "dashboard",
            "active_meeting_id": None,
            "visible_meeting_ids": (),
        },
        "registered_actions": (
            {
                "action_id": "open_meeting_history",
                "description": "Open meeting history.",
                "required_parameters": (),
            },
            {
                "action_id": "open_meeting_detail",
                "description": "Open meeting detail.",
                "required_parameters": ("meeting_id",),
            },
        ),
    }


@pytest.mark.asyncio
async def test_groq_provider_requests_strict_structured_output() -> None:
    captured: dict[str, Any] = {}
    decision = {
        "intent": "navigate",
        "action_id": "open_meeting_history",
        "message": "I can open your meeting history.",
        "requires_confirmation": False,
        "parameters": {},
    }

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(decision)}}
                ]
            },
        )

    transport = httpx.MockTransport(handle_request)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqLLMProvider(
            client=client,
            api_key=SecretStr("test-groq-key"),
        )
        result = await provider.decide(
            instructions="Return only structured output.",
            user_message="Show my meeting history",
            safe_context=_safe_context(),
            output_schema=AgentDecision.model_json_schema(),
        )

    assert result == decision
    assert captured["authorization"] == "Bearer test-groq-key"
    body = captured["body"]
    assert body["model"] == "openai/gpt-oss-20b"
    assert body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] == 1_024

    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert "parameters" in schema["required"]
    parameters_schema = schema["properties"]["parameters"]
    assert parameters_schema == {
        "type": "object",
        "properties": {
            "meeting_id": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "boolean"},
                    {"type": "null"},
                ]
            }
        },
        "required": ["meeting_id"],
        "additionalProperties": False,
    }
    assert (
        body["messages"][0]["content"]
        .endswith("Set unused or unavailable parameter fields to null.")
    )

    user_message = json.loads(body["messages"][1]["content"])
    assert user_message["user_message"] == "Show my meeting history"
    assert "transcript" not in user_message
    assert "confidential_note" not in user_message


@pytest.mark.asyncio
async def test_groq_provider_fails_closed_on_http_error() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "provider-internal-detail"}},
        )

    transport = httpx.MockTransport(handle_request)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqLLMProvider(
            client=client,
            api_key=SecretStr("test-groq-key"),
        )
        with pytest.raises(LLMProviderUnavailableError) as error:
            await provider.decide(
                instructions="Return structured output.",
                user_message="Open meetings",
                safe_context=_safe_context(),
                output_schema=AgentDecision.model_json_schema(),
            )

    assert "provider-internal-detail" not in str(error.value)
    assert "test-groq-key" not in str(error.value)


@pytest.mark.asyncio
async def test_groq_provider_rejects_malformed_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqLLMProvider(
            client=client,
            api_key=SecretStr("test-groq-key"),
        )
        with pytest.raises(LLMProviderResponseError):
            await provider.decide(
                instructions="Return structured output.",
                user_message="Open meetings",
                safe_context=_safe_context(),
                output_schema=AgentDecision.model_json_schema(),
            )


@pytest.mark.asyncio
async def test_groq_provider_removes_null_parameter_placeholders() -> None:
    decision = {
        "intent": "navigate",
        "action_id": "open_meeting_history",
        "message": "I can open your meeting history.",
        "requires_confirmation": False,
        "parameters": {"meeting_id": None},
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(decision)}}
                ]
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GroqLLMProvider(
            client=client,
            api_key=SecretStr("test-groq-key"),
        )
        result = await provider.decide(
            instructions="Return structured output.",
            user_message="Open meetings",
            safe_context=_safe_context(),
            output_schema=AgentDecision.model_json_schema(),
        )

    assert result["parameters"] == {}


def test_lifespan_wires_real_provider_when_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings.groq,
        "groq_api_key",
        SecretStr("test-groq-key"),
    )

    local_app = create_app()
    with TestClient(local_app) as client:
        request = Request({"type": "http", "app": client.app})
        provider = get_llm_provider(request)

    assert isinstance(provider, GroqLLMProvider)
    assert provider.model == "openai/gpt-oss-20b"


def test_missing_key_keeps_app_live_and_assistant_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.groq, "groq_api_key", None)

    local_app = create_app()
    with TestClient(local_app) as client:
        assert client.get("/health/live").status_code == 200
        request = Request({"type": "http", "app": client.app})
        with pytest.raises(LLMProviderUnavailableError):
            get_llm_provider(request)
