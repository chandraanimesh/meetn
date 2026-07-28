from dataclasses import dataclass
from datetime import timedelta

from app.application.dto.meeting_reads import MeetingSummaryDTO
from app.application.dto.meeting_scheduling import (
    MAXIMUM_MEETING_DURATION_MINUTES,
    MINIMUM_MEETING_DURATION_MINUTES,
    MeetingCreateCommand,
    MeetingRescheduleCommand,
)
from app.application.exceptions import (
    ResourceAccessDeniedError,
    ResourceNotFoundError,
)
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.domain.entities.meeting import Meeting, MeetingStatus
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


@dataclass(slots=True)
class MeetingSchedulingService:
    meeting_repository: MeetingRepositoryPort
    authorization_service: AuthorizationService
    audit_service: AuditService

    async def create_meeting(
        self,
        principal: AuthenticatedPrincipal,
        command: MeetingCreateCommand,
        request_id: str,
    ) -> MeetingSummaryDTO:
        self._validate_duration(command.duration_minutes)
        if not principal.is_active:
            await self._audit(
                principal=principal,
                request_id=request_id,
                action_id="meeting.create",
                resource_id="pending",
                allowed=False,
                reason="inactive_user",
            )
            raise ResourceAccessDeniedError(
                code="ACTIVE_USER_REQUIRED",
                message="An active account is required to create a meeting",
            )

        meeting = Meeting(
            title=self._required_text(command.title, "title"),
            created_by=principal.user_id,
            start_time=command.start_time,
            end_time=command.start_time
            + timedelta(minutes=command.duration_minutes),
            place=self._required_text(command.place, "place"),
            purpose=self._required_text(command.purpose, "purpose"),
            personal_gift=command.personal_gift.strip(),
        )
        created = await self.meeting_repository.create_meeting(meeting)
        await self._audit(
            principal=principal,
            request_id=request_id,
            action_id="meeting.create",
            resource_id=created.id,
            allowed=True,
            reason="organizer",
        )
        return self._to_summary(created)

    async def reschedule_meeting(
        self,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        command: MeetingRescheduleCommand,
        request_id: str,
    ) -> MeetingSummaryDTO:
        self._validate_duration(command.duration_minutes)
        facts = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if facts is None:
            await self._audit(
                principal=principal,
                request_id=request_id,
                action_id="meeting.reschedule",
                resource_id=meeting_id,
                allowed=False,
                reason="resource_not_found",
            )
            raise ResourceNotFoundError

        decision = self.authorization_service.can_manage_meeting(principal, facts)
        if not decision.allowed:
            await self._audit(
                principal=principal,
                request_id=request_id,
                action_id="meeting.reschedule",
                resource_id=meeting_id,
                allowed=False,
                reason=decision.reason,
            )
            raise ResourceAccessDeniedError(
                code="MEETING_ORGANIZER_REQUIRED",
                message="Only the meeting organizer may reschedule this meeting",
            )

        meeting = await self.meeting_repository.get_meeting_by_id(
            meeting_id, principal.user_id
        )
        if meeting is None:
            await self._audit(
                principal=principal,
                request_id=request_id,
                action_id="meeting.reschedule",
                resource_id=meeting_id,
                allowed=False,
                reason="repository_scope_denied",
            )
            raise ResourceAccessDeniedError(
                code="MEETING_ORGANIZER_REQUIRED",
                message="Only the meeting organizer may reschedule this meeting",
            )

        meeting.title = self._updated_text(command.title, meeting.title, "title")
        meeting.place = self._updated_text(command.place, meeting.place, "place")
        meeting.purpose = self._updated_text(
            command.purpose, meeting.purpose, "purpose"
        )
        if command.personal_gift is not None:
            meeting.personal_gift = command.personal_gift.strip()
        meeting.start_time = command.start_time
        meeting.end_time = command.start_time + timedelta(
            minutes=command.duration_minutes
        )
        meeting.status = MeetingStatus.RESCHEDULED

        try:
            updated = await self.meeting_repository.update_meeting(
                meeting, actor_user_id=principal.user_id
            )
        except PermissionError as exc:
            await self._audit(
                principal=principal,
                request_id=request_id,
                action_id="meeting.reschedule",
                resource_id=meeting_id,
                allowed=False,
                reason="repository_scope_denied",
            )
            raise ResourceAccessDeniedError(
                code="MEETING_ORGANIZER_REQUIRED",
                message="Only the meeting organizer may reschedule this meeting",
            ) from exc

        await self._audit(
            principal=principal,
            request_id=request_id,
            action_id="meeting.reschedule",
            resource_id=meeting_id,
            allowed=True,
            reason=decision.reason,
        )
        return self._to_summary(updated)

    async def _audit(
        self,
        *,
        principal: AuthenticatedPrincipal,
        request_id: str,
        action_id: str,
        resource_id: str,
        allowed: bool,
        reason: str,
    ) -> None:
        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=principal.user_id,
            event_type=action_id,
            resource_type="meeting",
            resource_id=resource_id,
            action_id=action_id,
            allowed=allowed,
            reason=reason,
        )

    @staticmethod
    def _validate_duration(duration_minutes: int) -> None:
        if not (
            MINIMUM_MEETING_DURATION_MINUTES
            <= duration_minutes
            <= MAXIMUM_MEETING_DURATION_MINUTES
        ):
            raise ValueError("Meeting duration is outside the supported range")

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"Meeting {field_name} is required")
        return normalized

    @classmethod
    def _updated_text(
        cls, value: str | None, current: str, field_name: str
    ) -> str:
        if value is None:
            return current
        return cls._required_text(value, field_name)

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
