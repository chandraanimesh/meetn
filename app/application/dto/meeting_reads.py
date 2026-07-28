from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.meeting import MeetingStatus, ParticipantRole


@dataclass(frozen=True, slots=True)
class MeetingSummaryDTO:
    id: str
    title: str
    organizer_id: str
    start_time: datetime
    end_time: datetime
    status: MeetingStatus
    place: str
    purpose: str
    personal_gift: str


@dataclass(frozen=True, slots=True)
class MeetingListDTO:
    items: tuple[MeetingSummaryDTO, ...]


@dataclass(frozen=True, slots=True)
class MeetingParticipantDTO:
    user_id: str
    role: ParticipantRole


@dataclass(frozen=True, slots=True)
class MeetingDetailsDTO:
    id: str
    title: str
    organizer_id: str
    start_time: datetime
    end_time: datetime
    status: MeetingStatus
    place: str
    purpose: str
    personal_gift: str
    participants: tuple[MeetingParticipantDTO, ...]


@dataclass(frozen=True, slots=True)
class TranscriptDTO:
    id: str
    meeting_id: str
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConfidentialNoteDTO:
    id: str
    meeting_id: str
    created_by: str
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ConfidentialNotesDTO:
    meeting_id: str
    items: tuple[ConfidentialNoteDTO, ...]
