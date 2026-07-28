from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.dependencies.auth import get_authenticated_principal
from app.api.dependencies.services import (
    get_recording_availability_service,
    get_required_request_id,
)
from app.api.schemas.recordings import RecordingAvailabilityResponse
from app.application.services.recording_availability_service import (
    RecordingAvailabilityService,
)
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


router = APIRouter(prefix="/api", tags=["recordings"])

Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
RecordingAvailability = Annotated[
    RecordingAvailabilityService,
    Depends(get_recording_availability_service),
]
RequestID = Annotated[str, Depends(get_required_request_id)]
MeetingID = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]


@router.get(
    "/meetings/{meeting_id}/recording-availability",
    response_model=RecordingAvailabilityResponse,
)
async def get_recording_availability(
    meeting_id: MeetingID,
    principal: Principal,
    service: RecordingAvailability,
    request_id: RequestID,
) -> RecordingAvailabilityResponse:
    result = await service.get_availability(
        principal=principal,
        meeting_id=meeting_id,
        request_id=request_id,
    )
    return RecordingAvailabilityResponse.model_validate(result)
