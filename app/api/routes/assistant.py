from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.agent.assistant_orchestrator import AssistantOrchestrator
from app.agent.action_models import AssistantStatus
from app.agent.confirmed_action_executor import ConfirmedActionExecutor
from app.api.dependencies.auth import get_current_user, require_csrf
from app.api.dependencies.services import (
    get_assistant_orchestrator,
    get_confirmed_action_executor,
    get_required_request_id,
)
from app.api.schemas.assistant import (
    AssistantMessageRequest,
    AssistantMessageResponse,
    ConfirmedAssistantActionRequest,
)
from app.application.dto.assistant import PageManifestDTO
from app.domain.entities.user import User


router = APIRouter(prefix="/api", tags=["assistant"])

CurrentUser = Annotated[User, Depends(get_current_user)]
Orchestrator = Annotated[AssistantOrchestrator, Depends(get_assistant_orchestrator)]
RequestID = Annotated[str, Depends(get_required_request_id)]
ConfirmedExecutor = Annotated[
    ConfirmedActionExecutor, Depends(get_confirmed_action_executor)
]
CSRF = Annotated[None, Depends(require_csrf)]


@router.post("/assistant/messages", response_model=AssistantMessageResponse)
async def handle_assistant_message(
    request: AssistantMessageRequest,
    response: Response,
    current_user: CurrentUser,
    orchestrator: Orchestrator,
    request_id: RequestID,
) -> AssistantMessageResponse:
    manifest = PageManifestDTO(
        page_id=request.page_manifest.page_id.value,
        active_meeting_id=request.page_manifest.active_meeting_id,
        visible_meeting_ids=tuple(request.page_manifest.visible_meeting_ids),
    )
    result = await orchestrator.handle_message(
        user_message=request.message,
        page_manifest=manifest,
        authenticated_user=current_user,
        request_id=request_id,
    )
    if result.status is AssistantStatus.ACCESS_DENIED:
        response.status_code = 403
    return AssistantMessageResponse.model_validate(result.model_dump())


@router.post(
    "/assistant/actions/confirm",
    response_model=AssistantMessageResponse,
)
async def confirm_assistant_action(
    request: ConfirmedAssistantActionRequest,
    response: Response,
    current_user: CurrentUser,
    executor: ConfirmedExecutor,
    request_id: RequestID,
    csrf_valid: CSRF,
) -> AssistantMessageResponse:
    result = await executor.execute(
        action_id=request.action_id,
        raw_parameters=request.parameters,
        authenticated_user=current_user,
        request_id=request_id,
    )
    if result.status is AssistantStatus.ACCESS_DENIED:
        response.status_code = 403
    return AssistantMessageResponse.model_validate(result.model_dump())
