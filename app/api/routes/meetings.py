from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_authenticated_principal, require_csrf
from app.api.dependencies.services import (
    get_meeting_read_service,
    get_meeting_scheduling_service,
    get_required_request_id,
    get_transcript_management_service,
)
from app.api.schemas.meetings import (
    ConfidentialNotesResponse,
    MeetingDetailsResponse,
    MeetingCreateRequest,
    MeetingListResponse,
    MeetingRescheduleRequest,
    MeetingSummaryResponse,
    TranscriptResponse,
    TranscriptCreateRequest,
)
from app.application.dto.meeting_scheduling import (
    MeetingCreateCommand,
    MeetingRescheduleCommand,
)
from app.application.services.meeting_read_service import MeetingReadService
from app.application.services.meeting_scheduling_service import (
    MeetingSchedulingService,
)
from app.application.services.transcript_management_service import (
    TranscriptManagementService,
)
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


router = APIRouter(prefix="/api", tags=["meetings"])

Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]
MeetingReads = Annotated[MeetingReadService, Depends(get_meeting_read_service)]
MeetingScheduling = Annotated[
    MeetingSchedulingService, Depends(get_meeting_scheduling_service)
]
TranscriptManagement = Annotated[
    TranscriptManagementService, Depends(get_transcript_management_service)
]
RequestID = Annotated[str, Depends(get_required_request_id)]
CSRF = Annotated[None, Depends(require_csrf)]


@router.post("/meetings", response_model=MeetingSummaryResponse, status_code=201)
async def create_meeting(
    request: MeetingCreateRequest,
    principal: Principal,
    service: MeetingScheduling,
    request_id: RequestID,
    csrf_valid: CSRF,
) -> MeetingSummaryResponse:
    result = await service.create_meeting(
        principal,
        MeetingCreateCommand(
            title=request.title,
            place=request.place,
            purpose=request.purpose,
            start_time=request.start_time,
            duration_minutes=request.duration_minutes,
            personal_gift=request.personal_gift,
        ),
        request_id,
    )
    return MeetingSummaryResponse.model_validate(result)


@router.patch(
    "/meetings/{id}/schedule",
    response_model=MeetingSummaryResponse,
)
async def reschedule_meeting(
    id: str,
    request: MeetingRescheduleRequest,
    principal: Principal,
    service: MeetingScheduling,
    request_id: RequestID,
    csrf_valid: CSRF,
) -> MeetingSummaryResponse:
    result = await service.reschedule_meeting(
        principal,
        id,
        MeetingRescheduleCommand(
            title=request.title,
            place=request.place,
            purpose=request.purpose,
            start_time=request.start_time,
            duration_minutes=request.duration_minutes,
            personal_gift=request.personal_gift,
        ),
        request_id,
    )
    return MeetingSummaryResponse.model_validate(result)


@router.get("/me/meetings", response_model=MeetingListResponse)
async def list_current_user_meetings(
    principal: Principal,
    service: MeetingReads,
    request_id: RequestID,
) -> MeetingListResponse:
    result = await service.list_meetings(principal, request_id)
    return MeetingListResponse.model_validate(result)


@router.get("/meetings/{id}", response_model=MeetingDetailsResponse)
async def get_meeting(
    id: str,
    principal: Principal,
    service: MeetingReads,
    request_id: RequestID,
) -> MeetingDetailsResponse:
    result = await service.get_meeting(principal, id, request_id)
    return MeetingDetailsResponse.model_validate(result)


@router.get(
    "/meetings/{id}/transcript",
    response_model=TranscriptResponse,
)
async def get_meeting_transcript(
    id: str,
    principal: Principal,
    service: MeetingReads,
    request_id: RequestID,
) -> TranscriptResponse:
    result = await service.get_transcript(principal, id, request_id)
    return TranscriptResponse.model_validate(result)


@router.post(
    "/meetings/{id}/transcript",
    response_model=TranscriptResponse,
    status_code=201,
)
async def create_meeting_transcript(
    id: str,
    request: TranscriptCreateRequest,
    principal: Principal,
    service: TranscriptManagement,
    request_id: RequestID,
    csrf_valid: CSRF,
) -> TranscriptResponse:
    result = await service.create_transcript(
        principal,
        id,
        request.content,
        request_id,
    )
    return TranscriptResponse.model_validate(result)


@router.get(
    "/meetings/{id}/confidential-notes",
    response_model=ConfidentialNotesResponse,
)
async def get_meeting_confidential_notes(
    id: str,
    principal: Principal,
    service: MeetingReads,
    request_id: RequestID,
) -> ConfidentialNotesResponse:
    result = await service.get_confidential_notes(principal, id, request_id)
    return ConfidentialNotesResponse.model_validate(result)
