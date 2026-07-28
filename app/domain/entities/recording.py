from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

from app.domain.time import utc_now_naive


class RecordingProcessingStatus(str, Enum):
    PROCESSING = "processing"
    AVAILABLE = "available"


class RecordingAvailabilityReason(str, Enum):
    AVAILABLE = "available"
    NOT_CREATED = "not_created"
    PROCESSING = "processing"
    PLAN_RESTRICTION = "plan_restriction"
    UNAUTHORIZED = "unauthorized"


class MembershipPlan(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ORGANIZATION = "organization"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class Recording:
    meeting_id: str
    processing_status: RecordingProcessingStatus
    required_plan: MembershipPlan = MembershipPlan.PROFESSIONAL
    created_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True, slots=True)
class Membership:
    user_id: str
    plan: MembershipPlan
    status: MembershipStatus = MembershipStatus.ACTIVE
    valid_until: datetime | None = None
    updated_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def is_active_at(self, evaluated_at: datetime) -> bool:
        if self.status is not MembershipStatus.ACTIVE:
            return False
        return self.valid_until is None or self.valid_until > evaluated_at
