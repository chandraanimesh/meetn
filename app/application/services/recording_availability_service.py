from dataclasses import dataclass

from app.application.dto.recording_availability import (
    RecordingAlternativeActionID,
    RecordingAvailabilityDTO,
)
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.ports.membership_repository import MembershipRepositoryPort
from app.application.ports.recording_repository import RecordingRepositoryPort
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.entitlement_service import EntitlementService
from app.domain.entities.recording import (
    MembershipPlan,
    RecordingAvailabilityReason,
    RecordingProcessingStatus,
)
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


@dataclass(slots=True)
class RecordingAvailabilityService:
    meeting_repository: MeetingRepositoryPort
    recording_repository: RecordingRepositoryPort
    membership_repository: MembershipRepositoryPort
    authorization_service: AuthorizationService
    entitlement_service: EntitlementService
    audit_service: AuditService

    async def get_availability(
        self,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
    ) -> RecordingAvailabilityDTO:
        meeting = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if meeting is None:
            return await self._result(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                reason=RecordingAvailabilityReason.UNAUTHORIZED,
            )

        authorization = self.authorization_service.can_list_meeting(
            principal, meeting
        )
        if not authorization.allowed:
            return await self._result(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                reason=RecordingAvailabilityReason.UNAUTHORIZED,
            )

        transcript_available = await self.meeting_repository.transcript_exists(
            meeting_id
        )
        recording = await self.recording_repository.get_by_meeting(meeting_id)
        if recording is None:
            return await self._result(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                reason=RecordingAvailabilityReason.NOT_CREATED,
                transcript_available=transcript_available,
            )
        if recording.processing_status is RecordingProcessingStatus.PROCESSING:
            return await self._result(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                reason=RecordingAvailabilityReason.PROCESSING,
                transcript_available=transcript_available,
            )

        membership = await self.membership_repository.get_by_user(principal.user_id)
        entitlement = self.entitlement_service.can_access_recording(
            membership, recording.required_plan
        )
        if not entitlement.allowed:
            return await self._result(
                principal=principal,
                meeting_id=meeting_id,
                request_id=request_id,
                reason=RecordingAvailabilityReason.PLAN_RESTRICTION,
                required_plan=recording.required_plan,
                transcript_available=transcript_available,
            )
        return await self._result(
            principal=principal,
            meeting_id=meeting_id,
            request_id=request_id,
            reason=RecordingAvailabilityReason.AVAILABLE,
        )

    async def _result(
        self,
        *,
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        request_id: str,
        reason: RecordingAvailabilityReason,
        required_plan: MembershipPlan | None = None,
        transcript_available: bool = False,
    ) -> RecordingAvailabilityDTO:
        alternatives: list[RecordingAlternativeActionID] = []
        if transcript_available:
            alternatives.append(RecordingAlternativeActionID.OPEN_TRANSCRIPT)
        if reason is RecordingAvailabilityReason.PLAN_RESTRICTION:
            alternatives.append(
                RecordingAlternativeActionID.OPEN_MEMBERSHIP_PLANS
            )

        available = reason is RecordingAvailabilityReason.AVAILABLE
        authorized = reason not in {
            RecordingAvailabilityReason.UNAUTHORIZED,
            RecordingAvailabilityReason.PLAN_RESTRICTION,
        }
        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=principal.user_id,
            event_type="recording.availability_checked",
            resource_type="recording_availability",
            resource_id=meeting_id,
            action_id="recording.availability.check",
            allowed=authorized,
            reason=reason.value,
        )
        return RecordingAvailabilityDTO(
            meeting_id=meeting_id,
            availability=available,
            verified_reason=reason,
            required_plan=required_plan,
            allowed_alternative_action_ids=tuple(alternatives),
        )
