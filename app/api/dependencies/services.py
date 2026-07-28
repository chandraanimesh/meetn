from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.action_dispatcher import ActionDispatcher
from app.agent.action_registry import BackendActionRegistry
from app.agent.assistant_orchestrator import AssistantOrchestrator
from app.agent.confirmed_action_executor import ConfirmedActionExecutor
from app.agent.context_builder import SafeContextBuilder
from app.api.dependencies.database import get_db_session
from app.application.ports.llm_provider import LLMProviderPort
from app.application.exceptions import LLMProviderUnavailableError
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.meeting_read_service import MeetingReadService
from app.application.services.meeting_scheduling_service import (
    MeetingSchedulingService,
)
from app.application.services.media_validation_service import (
    MediaValidationService,
)
from app.application.services.transcript_management_service import (
    TranscriptManagementService,
)
from app.application.services.entitlement_service import EntitlementService
from app.application.services.recording_availability_service import (
    RecordingAvailabilityService,
)
from app.application.services.readiness_service import ReadinessService
from app.core.request_context import get_request_id
from app.infrastructure.database.readiness import SQLAlchemyReadinessProbe
from app.infrastructure.database.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
)
from app.infrastructure.database.repositories.meeting_repository import (
    SQLAlchemyMeetingRepository,
)
from app.infrastructure.database.repositories.membership_repository import (
    SQLAlchemyMembershipRepository,
)
from app.infrastructure.database.repositories.recording_repository import (
    SQLAlchemyRecordingRepository,
)
from app.infrastructure.database.session import engine
from app.infrastructure.media_inspector import StandardLibraryMediaInspector


def get_readiness_service() -> ReadinessService:
    return ReadinessService(database_probe=SQLAlchemyReadinessProbe(engine))


def get_meeting_read_service(
    session: AsyncSession = Depends(get_db_session),
) -> MeetingReadService:
    return MeetingReadService(
        meeting_repository=SQLAlchemyMeetingRepository(session),
        authorization_service=AuthorizationService(),
        audit_service=AuditService(SQLAlchemyAuditRepository(session)),
    )


def get_meeting_scheduling_service(
    session: AsyncSession = Depends(get_db_session),
) -> MeetingSchedulingService:
    return MeetingSchedulingService(
        meeting_repository=SQLAlchemyMeetingRepository(session),
        authorization_service=AuthorizationService(),
        audit_service=AuditService(SQLAlchemyAuditRepository(session)),
    )


def get_transcript_management_service(
    session: AsyncSession = Depends(get_db_session),
) -> TranscriptManagementService:
    return TranscriptManagementService(
        meeting_repository=SQLAlchemyMeetingRepository(session),
        authorization_service=AuthorizationService(),
        audit_service=AuditService(SQLAlchemyAuditRepository(session)),
    )


def get_recording_availability_service(
    session: AsyncSession = Depends(get_db_session),
) -> RecordingAvailabilityService:
    return RecordingAvailabilityService(
        meeting_repository=SQLAlchemyMeetingRepository(session),
        recording_repository=SQLAlchemyRecordingRepository(session),
        membership_repository=SQLAlchemyMembershipRepository(session),
        authorization_service=AuthorizationService(),
        entitlement_service=EntitlementService(),
        audit_service=AuditService(SQLAlchemyAuditRepository(session)),
    )


def get_media_validation_service(
    session: AsyncSession = Depends(get_db_session),
) -> MediaValidationService:
    return MediaValidationService(
        media_inspector=StandardLibraryMediaInspector(),
        audit_service=AuditService(SQLAlchemyAuditRepository(session)),
    )


def get_llm_provider(request: Request) -> LLMProviderPort:
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        raise LLMProviderUnavailableError("GROQ_API_KEY is not configured")
    return provider


@lru_cache
def get_action_registry() -> BackendActionRegistry:
    return BackendActionRegistry()


def get_assistant_orchestrator(
    session: AsyncSession = Depends(get_db_session),
    llm_provider: LLMProviderPort = Depends(get_llm_provider),
    registry: BackendActionRegistry = Depends(get_action_registry),
) -> AssistantOrchestrator:
    meeting_repository = SQLAlchemyMeetingRepository(session)
    authorization_service = AuthorizationService()
    return AssistantOrchestrator(
        llm_provider=llm_provider,
        registry=registry,
        context_builder=SafeContextBuilder(),
        dispatcher=ActionDispatcher(
            meeting_repository=meeting_repository,
            authorization_service=authorization_service,
        ),
        audit_service=AuditService(SQLAlchemyAuditRepository(session)),
    )


def get_confirmed_action_executor(
    session: AsyncSession = Depends(get_db_session),
    registry: BackendActionRegistry = Depends(get_action_registry),
) -> ConfirmedActionExecutor:
    meeting_repository = SQLAlchemyMeetingRepository(session)
    authorization_service = AuthorizationService()
    audit_service = AuditService(SQLAlchemyAuditRepository(session))
    scheduling_service = MeetingSchedulingService(
        meeting_repository=meeting_repository,
        authorization_service=authorization_service,
        audit_service=audit_service,
    )
    return ConfirmedActionExecutor(
        registry=registry,
        dispatcher=ActionDispatcher(
            meeting_repository=meeting_repository,
            authorization_service=authorization_service,
        ),
        scheduling_service=scheduling_service,
        audit_service=audit_service,
    )


def get_required_request_id() -> str:
    request_id = get_request_id()
    if request_id is None:
        raise RuntimeError("Request ID middleware is not active")
    return request_id
