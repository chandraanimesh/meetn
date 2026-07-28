from dataclasses import dataclass

from app.application.dto.meeting_reads import (
    ConfidentialNoteDTO,
    ConfidentialNotesDTO,
    MeetingDetailsDTO,
    MeetingListDTO,
    MeetingParticipantDTO,
    MeetingSummaryDTO,
    TranscriptDTO,
)
from app.application.exceptions import (
    ResourceAccessDeniedError,
    ResourceNotFoundError,
)
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.domain.entities.meeting import ConfidentialNote, Meeting
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)


@dataclass(slots=True)
class MeetingReadService:
    meeting_repository: MeetingRepositoryPort
    authorization_service: AuthorizationService
    audit_service: AuditService

    async def list_meetings(
        self,
        principal: AuthenticatedPrincipal,
        request_id: str,
    ) -> MeetingListDTO:
        meetings = await self.meeting_repository.list_meetings_by_user(
            principal.user_id
        )
        visible_meetings = tuple(
            self._to_summary(meeting)
            for meeting in meetings
            if self.authorization_service.can_list_meeting(
                principal, self._facts_from_meeting(meeting)
            ).allowed
        )
        await self._audit_access(
            principal=principal,
            request_id=request_id,
            action_id="meetings.list",
            resource_type="meeting_collection",
            resource_id=principal.user_id,
            allowed=True,
            reason="authenticated_scope",
        )
        return MeetingListDTO(items=visible_meetings)

    async def get_meeting(
        self,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
    ) -> MeetingDetailsDTO:
        facts = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if facts is None:
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="meeting.read",
                resource_type="meeting",
                resource_id=meeting_id,
                allowed=False,
                reason="resource_not_found",
            )
            raise ResourceNotFoundError
        decision = self.authorization_service.can_list_meeting(principal, facts)
        if not decision.allowed:
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="meeting.read",
                resource_type="meeting",
                resource_id=meeting_id,
                allowed=False,
                reason=decision.reason,
            )
            raise ResourceAccessDeniedError(
                code="PARTICIPANT_ACCESS_REQUIRED",
                message="You are not authorized to access this meeting",
            )

        meeting = await self.meeting_repository.get_meeting_by_id(
            meeting_id, principal.user_id
        )
        if meeting is None:
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="meeting.read",
                resource_type="meeting",
                resource_id=meeting_id,
                allowed=False,
                reason="repository_scope_denied",
            )
            raise ResourceAccessDeniedError(
                code="PARTICIPANT_ACCESS_REQUIRED",
                message="You are not authorized to access this meeting",
            )
        await self._audit_access(
            principal=principal,
            request_id=request_id,
            action_id="meeting.read",
            resource_type="meeting",
            resource_id=meeting_id,
            allowed=True,
            reason=decision.reason,
        )
        return self._to_details(meeting)

    async def get_transcript(
        self,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
    ) -> TranscriptDTO:
        facts = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if facts is None:
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="transcript.read",
                resource_type="transcript",
                resource_id=meeting_id,
                allowed=False,
                reason="resource_not_found",
            )
            raise ResourceNotFoundError
        if not await self.meeting_repository.transcript_exists(meeting_id):
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="transcript.read",
                resource_type="transcript",
                resource_id=meeting_id,
                allowed=False,
                reason="resource_not_found",
            )
            raise ResourceNotFoundError
        decision = self.authorization_service.can_view_transcript(principal, facts)
        if not decision.allowed:
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="transcript.read",
                resource_type="transcript",
                resource_id=meeting_id,
                allowed=False,
                reason=decision.reason,
            )
            raise ResourceAccessDeniedError(
                code="PARTICIPANT_ACCESS_REQUIRED",
                message="You are not authorized to access this transcript",
            )

        transcript = await self.meeting_repository.get_transcript(
            meeting_id, principal.user_id
        )
        if transcript is None:
            await self._audit_access(
                principal=principal,
                request_id=request_id,
                action_id="transcript.read",
                resource_type="transcript",
                resource_id=meeting_id,
                allowed=False,
                reason="repository_scope_denied",
            )
            raise ResourceNotFoundError
        await self._audit_access(
            principal=principal,
            request_id=request_id,
            action_id="transcript.read",
            resource_type="transcript",
            resource_id=meeting_id,
            allowed=True,
            reason=decision.reason,
        )
        return TranscriptDTO(
            id=transcript.id,
            meeting_id=transcript.meeting_id,
            content=transcript.content,
            created_at=transcript.created_at,
        )

    async def get_confidential_notes(
        self,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
    ) -> ConfidentialNotesDTO:
        facts = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if facts is None:
            await self._audit_confidential_access(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                allowed=False,
                reason="resource_not_found",
            )
            raise ResourceNotFoundError

        meeting_decision = self.authorization_service.can_list_meeting(
            principal, facts
        )
        if not meeting_decision.allowed:
            await self._audit_confidential_access(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                allowed=False,
                reason=meeting_decision.reason,
            )
            raise ResourceAccessDeniedError(
                code="CONFIDENTIAL_NOTE_ACCESS_DENIED",
                message="You are not authorized to access confidential notes",
            )

        notes = await self.meeting_repository.get_confidential_notes(
            meeting_id, principal.user_id
        )
        allowed_notes: list[ConfidentialNoteDTO] = []
        allow_reasons: set[str] = set()
        for note in notes:
            note_decision = self.authorization_service.can_view_confidential_note(
                principal,
                facts,
                self._note_access_facts(note),
            )
            if note_decision.allowed:
                allowed_notes.append(self._to_confidential_note(note))
                allow_reasons.add(note_decision.reason)

        audit_reason = self._confidential_audit_reason(
            meeting_decision.reason, allow_reasons
        )
        await self._audit_confidential_access(
            principal=principal,
            meeting_id=meeting_id,
            request_id=request_id,
            allowed=True,
            reason=audit_reason,
        )
        return ConfidentialNotesDTO(
            meeting_id=meeting_id,
            items=tuple(allowed_notes),
        )

    async def _audit_confidential_access(
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
            event_type="confidential_notes.read",
            resource_type="confidential_note_collection",
            resource_id=meeting_id,
            allowed=allowed,
            reason=reason,
            action_id="confidential_notes.read",
        )

    async def _audit_access(
        self,
        *,
        principal: AuthenticatedPrincipal,
        request_id: str,
        action_id: str,
        resource_type: str,
        resource_id: str,
        allowed: bool,
        reason: str,
    ) -> None:
        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=principal.user_id,
            event_type=action_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action_id=action_id,
            allowed=allowed,
            reason=reason,
        )

    @staticmethod
    def _facts_from_meeting(meeting: Meeting) -> MeetingAccessFacts:
        return MeetingAccessFacts(
            meeting_id=meeting.id,
            organizer_user_id=meeting.created_by,
            active_participant_user_ids=frozenset(
                participant.user_id
                for participant in meeting.participants
                if participant.is_active
            ),
        )

    @staticmethod
    def _note_access_facts(note: ConfidentialNote) -> ConfidentialNoteAccessFacts:
        return ConfidentialNoteAccessFacts(
            note_id=note.id,
            meeting_id=note.meeting_id,
            allowed_user_ids=frozenset(
                access.user_id for access in note.access_list if access.is_active
            ),
            is_deleted=note.deleted_at is not None,
        )

    @staticmethod
    def _confidential_audit_reason(
        meeting_reason: str, note_reasons: set[str]
    ) -> str:
        if meeting_reason == "organizer":
            return "organizer"
        if not note_reasons:
            return "no_accessible_notes"
        if len(note_reasons) == 1:
            return next(iter(note_reasons))
        return "multiple_access_grants"

    @staticmethod
    def _to_summary(meeting: Meeting) -> MeetingSummaryDTO:
        return MeetingSummaryDTO(
            id=meeting.id,
            title=meeting.title,
            organizer_id=meeting.created_by,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            status=meeting.status,
            place=meeting.place,
            purpose=meeting.purpose,
            personal_gift=meeting.personal_gift,
        )

    @staticmethod
    def _to_details(meeting: Meeting) -> MeetingDetailsDTO:
        return MeetingDetailsDTO(
            id=meeting.id,
            title=meeting.title,
            organizer_id=meeting.created_by,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            status=meeting.status,
            place=meeting.place,
            purpose=meeting.purpose,
            personal_gift=meeting.personal_gift,
            participants=tuple(
                MeetingParticipantDTO(
                    user_id=participant.user_id,
                    role=participant.role,
                )
                for participant in meeting.participants
                if participant.is_active
            ),
        )

    @staticmethod
    def _to_confidential_note(note: ConfidentialNote) -> ConfidentialNoteDTO:
        return ConfidentialNoteDTO(
            id=note.id,
            meeting_id=note.meeting_id,
            created_by=note.created_by,
            content=note.content,
            created_at=note.created_at,
        )
