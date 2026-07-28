from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid
from enum import Enum

from app.domain.time import utc_now_naive

class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ParticipantRole(str, Enum):
    HOST = "host"
    ATTENDEE = "attendee"


class ParticipantMembershipStatus(str, Enum):
    ACTIVE = "active"
    REMOVED = "removed"
    REVOKED = "revoked"


@dataclass
class MeetingParticipant:
    meeting_id: str
    user_id: str
    role: ParticipantRole
    joined_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    membership_status: ParticipantMembershipStatus = ParticipantMembershipStatus.ACTIVE
    removed_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        return self.membership_status is ParticipantMembershipStatus.ACTIVE

@dataclass
class Transcript:
    meeting_id: str
    content: str
    created_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class ConfidentialNoteAccess:
    note_id: str
    user_id: str
    granted_by: str
    granted_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    revoked_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

@dataclass
class ConfidentialNote:
    meeting_id: str
    created_by: str
    content: str
    created_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    access_list: List[ConfidentialNoteAccess] = field(default_factory=list)
    deleted_at: Optional[datetime] = None

@dataclass
class Meeting:
    title: str
    created_by: str
    start_time: datetime
    end_time: datetime
    status: MeetingStatus = MeetingStatus.SCHEDULED
    place: str = ""
    purpose: str = ""
    personal_gift: str = ""
    created_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    participants: List[MeetingParticipant] = field(default_factory=list)
    transcript: Optional[Transcript] = None
    confidential_notes: List[ConfidentialNote] = field(default_factory=list)
