from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.action_models import AssistantResult


class PageID(str, Enum):
    DASHBOARD = "dashboard"
    MEETING_HISTORY = "meeting_history"
    MEETING_DETAIL = "meeting_detail"
    TRANSCRIPT = "transcript"
    CONFIDENTIAL_NOTES = "confidential_notes"
    MEMBERSHIP_PLANS = "membership_plans"


class SanitizedPageManifestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: PageID
    active_meeting_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    visible_meeting_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("visible_meeting_ids")
    @classmethod
    def validate_visible_meeting_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("visible_meeting_ids must be unique")
        for value in values:
            if not value or len(value) > 128:
                raise ValueError("Meeting IDs must contain 1 to 128 characters")
            if not value[0].isalnum() or any(
                not (character.isalnum() or character in "._-")
                for character in value
            ):
                raise ValueError("Meeting IDs contain unsupported characters")
        return values


class AssistantMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: str = Field(min_length=1, max_length=2_000)
    page_manifest: SanitizedPageManifestRequest


class ConfirmedAssistantActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action_id: str = Field(min_length=1, max_length=64)
    parameters: dict[str, str | int | bool] = Field(default_factory=dict)


class AssistantMessageResponse(AssistantResult):
    pass
