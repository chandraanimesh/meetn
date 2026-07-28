from dataclasses import dataclass
from typing import NoReturn

from app.application.dto.meeting_reads import TranscriptDTO
from app.application.exceptions import (
    ResourceAccessDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.application.ports.meeting_repository import (
    MeetingRepositoryPort,
    TranscriptAlreadyExistsError,
)
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.domain.entities.meeting import Transcript
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


MAX_TRANSCRIPT_CHARACTERS = 200_000


@dataclass(slots=True)
class TranscriptManagementService:
    """Create the single transcript allowed for a meeting.

    The authenticated principal is supplied by the API dependency and is never
    accepted from transcript input. Repository scoping remains as defense in
    depth after the application authorization decision.
    """

    meeting_repository: MeetingRepositoryPort
    authorization_service: AuthorizationService
    audit_service: AuditService

    async def create_transcript(
        self,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        content: str,
        request_id: str,
    ) -> TranscriptDTO:
        normalized_content = self._normalize_content(content)
        facts = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if facts is None:
            await self._audit(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                allowed=False,
                reason="resource_not_found",
            )
            raise ResourceNotFoundError

        decision = self.authorization_service.can_manage_meeting(principal, facts)
        if not decision.allowed:
            await self._audit(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                allowed=False,
                reason=decision.reason,
            )
            raise ResourceAccessDeniedError(
                code="MEETING_ORGANIZER_REQUIRED",
                message="Only the meeting organizer may add a transcript",
            )

        if await self.meeting_repository.transcript_exists(meeting_id):
            await self._raise_conflict(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
            )

        try:
            created = await self.meeting_repository.add_transcript(
                Transcript(meeting_id=meeting_id, content=normalized_content),
                actor_user_id=principal.user_id,
            )
        except TranscriptAlreadyExistsError:
            await self._raise_conflict(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
            )

        await self._audit(
            principal=principal,
            meeting_id=meeting_id,
            request_id=request_id,
            allowed=True,
            reason=decision.reason,
        )
        return TranscriptDTO(
            id=created.id,
            meeting_id=created.meeting_id,
            content=created.content,
            created_at=created.created_at,
        )

    async def _raise_conflict(
        self,
        *,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
    ) -> NoReturn:
        await self._audit(
            principal=principal,
            meeting_id=meeting_id,
            request_id=request_id,
            allowed=False,
            reason="transcript_already_exists",
        )
        raise ResourceConflictError(
            code="TRANSCRIPT_ALREADY_EXISTS",
            message="This meeting already has a transcript",
        )

    async def _audit(
        self,
        *,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
        allowed: bool,
        reason: str,
    ) -> None:
        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=principal.user_id,
            event_type="transcript.create",
            resource_type="transcript",
            resource_id=meeting_id,
            action_id="transcript.create",
            allowed=allowed,
            reason=reason,
        )

    @staticmethod
    def _normalize_content(content: str) -> str:
        normalized = content.strip()
        if not normalized:
            raise ValueError("Transcript content is required")
        if len(normalized) > MAX_TRANSCRIPT_CHARACTERS:
            raise ValueError("Transcript content exceeds the supported size")
        if "\x00" in normalized:
            raise ValueError("Transcript content contains unsupported characters")
        return normalized
