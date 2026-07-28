from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.application.dto.meeting_scheduling import normalize_start_time
from app.application.services.transcript_management_service import (
    MAX_TRANSCRIPT_CHARACTERS,
)
from app.domain.entities.meeting import MeetingStatus, ParticipantRole


class MeetingAPIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MeetingSummaryResponse(MeetingAPIModel):
    id: str
    title: str
    organizer_id: str
    start_time: datetime
    end_time: datetime
    status: MeetingStatus
    place: str
    purpose: str
    personal_gift: str


class MeetingScheduleRequest(MeetingAPIModel):
    model_config = ConfigDict(extra="forbid")

    start_time: datetime
    duration_minutes: StrictInt = Field(ge=15, le=480)

    @field_validator("start_time")
    @classmethod
    def require_aware_start_time(cls, value: datetime) -> datetime:
        return normalize_start_time(value)


class MeetingCreateRequest(MeetingScheduleRequest):
    title: str = Field(min_length=1, max_length=160)
    place: str = Field(min_length=1, max_length=255)
    purpose: str = Field(min_length=1, max_length=1_000)
    personal_gift: str = Field(default="", max_length=255)

    @field_validator("title", "place", "purpose")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Meeting text fields cannot be blank")
        return normalized

    @field_validator("personal_gift")
    @classmethod
    def normalize_personal_gift(cls, value: str) -> str:
        return value.strip()


class MeetingRescheduleRequest(MeetingScheduleRequest):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    place: str | None = Field(default=None, min_length=1, max_length=255)
    purpose: str | None = Field(default=None, min_length=1, max_length=1_000)
    personal_gift: str | None = Field(default=None, max_length=255)

    @field_validator("title", "place", "purpose")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Meeting text fields cannot be blank")
        return normalized

    @field_validator("personal_gift")
    @classmethod
    def normalize_optional_gift(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class MeetingListResponse(MeetingAPIModel):
    items: list[MeetingSummaryResponse]


class MeetingParticipantResponse(MeetingAPIModel):
    user_id: str
    role: ParticipantRole


class MeetingDetailsResponse(MeetingSummaryResponse):
    participants: list[MeetingParticipantResponse]


class TranscriptResponse(MeetingAPIModel):
    id: str
    meeting_id: str
    content: str
    created_at: datetime


class TranscriptCreateRequest(MeetingAPIModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    content: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARACTERS)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Transcript content cannot be blank")
        if "\x00" in normalized:
            raise ValueError("Transcript content contains unsupported characters")
        return normalized


class ConfidentialNoteResponse(MeetingAPIModel):
    id: str
    meeting_id: str
    created_by: str
    content: str
    created_at: datetime


class ConfidentialNotesResponse(MeetingAPIModel):
    meeting_id: str
    items: list[ConfidentialNoteResponse]
