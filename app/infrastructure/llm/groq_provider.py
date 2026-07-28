import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass

import httpx
from pydantic import SecretStr

from app.application.exceptions import (
    LLMProviderResponseError,
    LLMProviderUnavailableError,
)


GROQ_CHAT_COMPLETIONS_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)


@dataclass(slots=True)
class GroqLLMProvider:
    """Groq adapter that returns structured output for backend validation."""

    client: httpx.AsyncClient
    api_key: SecretStr
    model: str = "openai/gpt-oss-20b"
    max_completion_tokens: int = 1_024
    reasoning_effort: str = "low"

    async def decide(
        self,
        *,
        instructions: str,
        user_message: str,
        safe_context: Mapping[str, object],
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        strict_schema = _build_strict_schema(
            output_schema=output_schema,
            safe_context=safe_context,
        )
        try:
            user_content = json.dumps(
                {
                    "user_message": user_message,
                    "safe_context": dict(safe_context),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise LLMProviderResponseError(
                "The safe assistant context is not JSON serializable"
            ) from exc

        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{instructions}\n"
                        "Set unused or unavailable parameter fields to null."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "assistant_decision",
                    "strict": True,
                    "schema": strict_schema,
                },
            },
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": self.max_completion_tokens,
        }
        try:
            response = await self.client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": (
                        f"Bearer {self.api_key.get_secret_value()}"
                    ),
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
        except httpx.RequestError as exc:
            raise LLMProviderUnavailableError(
                "The Groq API could not be reached"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderUnavailableError(
                "The Groq API rejected the assistant request"
            ) from exc

        return _decode_decision(response)


def _decode_decision(response: httpx.Response) -> dict[str, object]:
    try:
        response_body = response.json()
        if not isinstance(response_body, Mapping):
            raise TypeError("Response body is not an object")

        choices = response_body.get("choices")
        if not isinstance(choices, Sequence) or isinstance(
            choices, (str, bytes)
        ):
            raise TypeError("Response choices are missing")
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise TypeError("Response choice is not an object")

        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise TypeError("Response message is missing")
        content = message.get("content")
        if not isinstance(content, str):
            raise TypeError("Response content is missing")

        decision = json.loads(content)
        if not isinstance(decision, dict):
            raise TypeError("Structured decision is not an object")
        parameters = decision.get("parameters")
        if isinstance(parameters, Mapping):
            decision["parameters"] = {
                key: value
                for key, value in parameters.items()
                if value is not None
            }
        return decision
    except (IndexError, TypeError, ValueError) as exc:
        raise LLMProviderResponseError(
            "The Groq API returned an invalid structured response"
        ) from exc


def _build_strict_schema(
    *,
    output_schema: Mapping[str, object],
    safe_context: Mapping[str, object],
) -> dict[str, object]:
    """Close dynamic parameter objects for Groq strict schema decoding."""

    schema = deepcopy(dict(output_schema))
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise LLMProviderResponseError("The decision schema has no properties")

    parameter_schema = properties.get("parameters")
    if not isinstance(parameter_schema, Mapping):
        raise LLMProviderResponseError(
            "The decision schema has no parameters property"
        )
    parameter_value_schema = parameter_schema.get("additionalProperties")
    if not isinstance(parameter_value_schema, Mapping):
        raise LLMProviderResponseError(
            "The parameters schema has no value definition"
        )

    parameter_names = _registered_parameter_names(safe_context)
    if not parameter_names:
        raise LLMProviderResponseError(
            "Groq strict output requires at least one registered parameter"
        )
    nullable_value_schema = _make_nullable(parameter_value_schema)
    properties["parameters"] = {
        "type": "object",
        "properties": {
            name: deepcopy(nullable_value_schema) for name in parameter_names
        },
        "required": list(parameter_names),
        "additionalProperties": False,
    }

    required = schema.get("required")
    schema_required_names = (
        list(required) if isinstance(required, list) else []
    )
    for property_name in properties:
        if property_name not in schema_required_names:
            schema_required_names.append(property_name)
    schema["required"] = schema_required_names
    schema["additionalProperties"] = False
    return schema


def _registered_parameter_names(
    safe_context: Mapping[str, object],
) -> tuple[str, ...]:
    registered_actions = safe_context.get("registered_actions")
    if not isinstance(registered_actions, Sequence) or isinstance(
        registered_actions, (str, bytes)
    ):
        return ()

    parameter_names: set[str] = set()
    for descriptor in registered_actions:
        if not isinstance(descriptor, Mapping):
            continue
        raw_names = descriptor.get("parameter_names")
        if raw_names is None:
            raw_names = descriptor.get("required_parameters")
        if not isinstance(raw_names, Sequence) or isinstance(
            raw_names, (str, bytes)
        ):
            continue
        parameter_names.update(
            name for name in raw_names if isinstance(name, str)
        )
    return tuple(sorted(parameter_names))


def _make_nullable(value_schema: Mapping[str, object]) -> dict[str, object]:
    schema = deepcopy(dict(value_schema))
    variants = schema.get("anyOf")
    if isinstance(variants, list):
        return {"anyOf": [*variants, {"type": "null"}]}
    return {"anyOf": [schema, {"type": "null"}]}
