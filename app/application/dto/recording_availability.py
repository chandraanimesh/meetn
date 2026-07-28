from dataclasses import dataclass
from enum import Enum

from app.domain.entities.recording import (
    MembershipPlan,
    RecordingAvailabilityReason,
)


class RecordingAlternativeActionID(str, Enum):
    OPEN_TRANSCRIPT = "open_transcript"
    OPEN_MEMBERSHIP_PLANS = "open_membership_plans"


@dataclass(frozen=True, slots=True)
class RecordingAvailabilityDTO:
    meeting_id: str
    availability: bool
    verified_reason: RecordingAvailabilityReason
    required_plan: MembershipPlan | None
    allowed_alternative_action_ids: tuple[RecordingAlternativeActionID, ...]
