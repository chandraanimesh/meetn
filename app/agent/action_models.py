from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


URL_PATTERN = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|mailto:|www\.|//|(?:^|\s)/[a-z0-9])"
)


class AssistantStatus(str, Enum):
    SUCCESS = "success"
    CLARIFICATION_REQUIRED = "clarification_required"
    CONFIRMATION_REQUIRED = "confirmation_required"
    ACTION_DENIED = "action_denied"
    ACCESS_DENIED = "access_denied"
    NOT_FOUND = "not_found"
    INVALID_OUTPUT = "invalid_output"


class PresentationTheme(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
    SOOTHING = "soothing"
    HAPPY = "happy"


class AgentDecision(BaseModel):
    """Strict structured output accepted from the LLM boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intent: str = Field(min_length=1, max_length=64)
    action_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=500)
    requires_confirmation: StrictBool
    parameters: dict[str, str | int | bool] = Field(default_factory=dict)

    @field_validator("intent", "action_id", "message")
    @classmethod
    def reject_urls(cls, value: str) -> str:
        if URL_PATTERN.search(value):
            raise ValueError("LLM output cannot contain URLs")
        return value

    @field_validator("parameters")
    @classmethod
    def reject_url_parameters(
        cls, parameters: dict[str, str | int | bool]
    ) -> dict[str, str | int | bool]:
        for key, value in parameters.items():
            if "url" in key.casefold():
                raise ValueError("LLM output cannot contain URL parameters")
            if isinstance(value, str) and URL_PATTERN.search(value):
                raise ValueError("LLM output cannot contain URLs")
        return parameters


class NavigationDirective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    method: str = "GET"

    @field_validator("path")
    @classmethod
    def require_safe_same_origin_path(cls, value: str) -> str:
        if not value.startswith("/") or value.startswith("//") or "\\" in value:
            raise ValueError("Navigation must use a same-origin path")
        return value


class PresentationDirective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    theme: PresentationTheme
    reason: str = "stress_detected"


class AssistantResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: AssistantStatus
    intent: str | None = None
    action_id: str | None = None
    message: str
    requires_confirmation: bool = False
    parameters: dict[str, str | int | bool] = Field(default_factory=dict)
    navigation: NavigationDirective | None = None
    focus_target: str | None = None
    presentation: PresentationDirective | None = None
    request_id: str
