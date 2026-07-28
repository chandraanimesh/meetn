from pydantic import BaseModel, ConfigDict

from app.application.dto.recording_availability import (
    RecordingAlternativeActionID,
)
from app.domain.entities.recording import (
    MembershipPlan,
    RecordingAvailabilityReason,
)


class RecordingAvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    availability: bool
    verified_reason: RecordingAvailabilityReason
    required_plan: MembershipPlan | None
    allowed_alternative_action_ids: list[RecordingAlternativeActionID]
