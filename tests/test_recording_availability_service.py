from unittest.mock import AsyncMock

import pytest

from app.application.dto.recording_availability import (
    RecordingAlternativeActionID,
)
from app.application.ports.audit_repository import AuditRepositoryPort
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.ports.membership_repository import MembershipRepositoryPort
from app.application.ports.recording_repository import RecordingRepositoryPort
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.entitlement_service import EntitlementService
from app.application.services.recording_availability_service import (
    RecordingAvailabilityService,
)
from app.domain.entities.audit_event import AuditDecision, AuditEvent
from app.domain.entities.recording import (
    Membership,
    MembershipPlan,
    Recording,
    RecordingAvailabilityReason,
    RecordingProcessingStatus,
)
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    MeetingAccessFacts,
)

MEETING_ID = "meeting-1"
ORGANIZER_ID = "organizer"
PARTICIPANT_ID = "participant"
OUTSIDER_ID = "outsider"


class InMemoryAuditRepository(AuditRepositoryPort):
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


def build_service(
    *,
    meeting: MeetingAccessFacts | None,
    recording: Recording | None,
    membership: Membership | None = None,
    transcript_exists: bool = True,
) -> tuple[
    RecordingAvailabilityService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    InMemoryAuditRepository,
]:
    meeting_repository = AsyncMock(spec=MeetingRepositoryPort)
    meeting_repository.get_meeting_access_facts.return_value = meeting
    meeting_repository.transcript_exists.return_value = transcript_exists
    recording_repository = AsyncMock(spec=RecordingRepositoryPort)
    recording_repository.get_by_meeting.return_value = recording
    membership_repository = AsyncMock(spec=MembershipRepositoryPort)
    membership_repository.get_by_user.return_value = membership
    audit_repository = InMemoryAuditRepository()
    return (
        RecordingAvailabilityService(
            meeting_repository=meeting_repository,
            recording_repository=recording_repository,
            membership_repository=membership_repository,
            authorization_service=AuthorizationService(),
            entitlement_service=EntitlementService(),
            audit_service=AuditService(audit_repository),
        ),
        meeting_repository,
        recording_repository,
        membership_repository,
        audit_repository,
    )


def meeting_facts() -> MeetingAccessFacts:
    return MeetingAccessFacts(
        meeting_id=MEETING_ID,
        organizer_user_id=ORGANIZER_ID,
        active_participant_user_ids=frozenset(
            {ORGANIZER_ID, PARTICIPANT_ID}
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("recording", "reason", "transcript_exists", "alternatives"),
    [
        (
            None,
            RecordingAvailabilityReason.NOT_CREATED,
            False,
            (),
        ),
        (
            None,
            RecordingAvailabilityReason.NOT_CREATED,
            True,
            (RecordingAlternativeActionID.OPEN_TRANSCRIPT,),
        ),
        (
            Recording(
                meeting_id=MEETING_ID,
                processing_status=RecordingProcessingStatus.PROCESSING,
            ),
            RecordingAvailabilityReason.PROCESSING,
            True,
            (RecordingAlternativeActionID.OPEN_TRANSCRIPT,),
        ),
    ],
)
async def test_backend_verifies_non_available_recording_states(
    recording: Recording | None,
    reason: RecordingAvailabilityReason,
    transcript_exists: bool,
    alternatives: tuple[RecordingAlternativeActionID, ...],
) -> None:
    service, _, _, membership_repository, audit_repository = build_service(
        meeting=meeting_facts(),
        recording=recording,
        transcript_exists=transcript_exists,
    )

    result = await service.get_availability(
        AuthenticatedPrincipal(ORGANIZER_ID), MEETING_ID, "request-1"
    )

    assert result.availability is False
    assert result.verified_reason is reason
    assert result.required_plan is None
    assert result.allowed_alternative_action_ids == alternatives
    membership_repository.get_by_user.assert_not_awaited()
    assert audit_repository.events[-1].decision_reason == reason.value


@pytest.mark.asyncio
async def test_entitled_membership_returns_available() -> None:
    recording = Recording(
        meeting_id=MEETING_ID,
        processing_status=RecordingProcessingStatus.AVAILABLE,
    )
    membership = Membership(
        user_id=PARTICIPANT_ID,
        plan=MembershipPlan.ORGANIZATION,
    )
    service, _, _, _, audit_repository = build_service(
        meeting=meeting_facts(), recording=recording, membership=membership
    )

    result = await service.get_availability(
        AuthenticatedPrincipal(PARTICIPANT_ID), MEETING_ID, "request-available"
    )

    assert result.availability is True
    assert result.verified_reason is RecordingAvailabilityReason.AVAILABLE
    assert result.required_plan is None
    assert result.allowed_alternative_action_ids == ()
    assert audit_repository.events == [
        AuditEvent(
            request_id="request-available",
            actor_user_id=PARTICIPANT_ID,
            event_type="recording.availability_checked",
                resource_type="recording_availability",
                resource_id=MEETING_ID,
                action_id="recording.availability.check",
                authorization_decision=AuditDecision.ALLOWED,
            decision_reason="available",
            id=audit_repository.events[0].id,
            created_at=audit_repository.events[0].created_at,
        )
    ]


@pytest.mark.asyncio
async def test_plan_restriction_supplies_required_plan_and_safe_alternatives() -> None:
    recording = Recording(
        meeting_id=MEETING_ID,
        processing_status=RecordingProcessingStatus.AVAILABLE,
        required_plan=MembershipPlan.PROFESSIONAL,
    )
    service, _, _, _, audit_repository = build_service(
        meeting=meeting_facts(), recording=recording, membership=None
    )

    result = await service.get_availability(
        AuthenticatedPrincipal(PARTICIPANT_ID), MEETING_ID, "request-restricted"
    )

    assert result.availability is False
    assert result.verified_reason is RecordingAvailabilityReason.PLAN_RESTRICTION
    assert result.required_plan is MembershipPlan.PROFESSIONAL
    assert result.allowed_alternative_action_ids == (
        RecordingAlternativeActionID.OPEN_TRANSCRIPT,
        RecordingAlternativeActionID.OPEN_MEMBERSHIP_PLANS,
    )
    assert audit_repository.events[-1].authorization_decision is AuditDecision.DENIED
    assert audit_repository.events[-1].decision_reason == "plan_restriction"


@pytest.mark.asyncio
@pytest.mark.parametrize("meeting", [None, meeting_facts()])
async def test_missing_and_unauthorized_meetings_fail_closed_without_state_leaks(
    meeting: MeetingAccessFacts | None,
) -> None:
    service, meeting_repository, recording_repository, membership_repository, audit = (
        build_service(
            meeting=meeting,
            recording=Recording(
                meeting_id=MEETING_ID,
                processing_status=RecordingProcessingStatus.AVAILABLE,
            ),
            membership=Membership(
                user_id=OUTSIDER_ID,
                plan=MembershipPlan.ORGANIZATION,
            ),
        )
    )

    result = await service.get_availability(
        AuthenticatedPrincipal(OUTSIDER_ID), MEETING_ID, "request-denied"
    )

    assert result.availability is False
    assert result.verified_reason is RecordingAvailabilityReason.UNAUTHORIZED
    assert result.required_plan is None
    assert result.allowed_alternative_action_ids == ()
    meeting_repository.transcript_exists.assert_not_awaited()
    recording_repository.get_by_meeting.assert_not_awaited()
    membership_repository.get_by_user.assert_not_awaited()
    assert audit.events[-1].authorization_decision is AuditDecision.DENIED
    assert audit.events[-1].decision_reason == "unauthorized"
