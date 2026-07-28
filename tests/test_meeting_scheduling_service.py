from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from app.application.dto.meeting_scheduling import (
    MeetingCreateCommand,
    MeetingRescheduleCommand,
)
from app.application.exceptions import (
    ResourceAccessDeniedError,
    ResourceNotFoundError,
)
from app.application.ports.audit_repository import AuditRepositoryPort
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.meeting_scheduling_service import (
    MeetingSchedulingService,
)
from app.domain.entities.audit_event import AuditEvent
from app.domain.entities.meeting import Meeting, MeetingStatus
from app.domain.time import utc_now_naive
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    MeetingAccessFacts,
)


pytestmark = pytest.mark.asyncio


@dataclass(slots=True)
class InMemoryAuditRepository(AuditRepositoryPort):
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


def build_service() -> tuple[
    MeetingSchedulingService,
    Mock,
    InMemoryAuditRepository,
]:
    repository = Mock(spec=MeetingRepositoryPort)
    repository.create_meeting = AsyncMock(side_effect=lambda meeting: meeting)
    repository.update_meeting = AsyncMock(side_effect=lambda meeting, **_: meeting)
    audit_repository = InMemoryAuditRepository()
    return (
        MeetingSchedulingService(
            meeting_repository=cast(MeetingRepositoryPort, repository),
            authorization_service=AuthorizationService(),
            audit_service=AuditService(audit_repository),
        ),
        repository,
        audit_repository,
    )


async def test_authenticated_user_creates_owned_scheduled_meeting() -> None:
    service, repository, audit_repository = build_service()
    start = utc_now_naive() + timedelta(days=1)

    result = await service.create_meeting(
        AuthenticatedPrincipal("creator"),
        MeetingCreateCommand(
            title=" Planning ",
            place=" Studio ",
            purpose=" Launch plan ",
            start_time=start,
            duration_minutes=90,
            personal_gift=" Coffee ",
        ),
        "create-request",
    )

    created: Meeting = repository.create_meeting.await_args.args[0]
    assert created.created_by == "creator"
    assert created.title == "Planning"
    assert created.place == "Studio"
    assert created.purpose == "Launch plan"
    assert created.personal_gift == "Coffee"
    assert created.end_time == start + timedelta(minutes=90)
    assert result.status is MeetingStatus.SCHEDULED
    assert audit_repository.events[0].action_id == "meeting.create"
    assert audit_repository.events[0].authorization_decision.value == "allowed"


async def test_only_organizer_can_reschedule_meeting() -> None:
    service, repository, audit_repository = build_service()
    repository.get_meeting_access_facts = AsyncMock(
        return_value=MeetingAccessFacts(
            meeting_id="meeting-1",
            organizer_user_id="organizer",
            active_participant_user_ids=frozenset({"participant"}),
        )
    )

    with pytest.raises(ResourceAccessDeniedError) as error:
        await service.reschedule_meeting(
            AuthenticatedPrincipal("participant"),
            "meeting-1",
            MeetingRescheduleCommand(
                start_time=utc_now_naive() + timedelta(days=2),
                duration_minutes=60,
            ),
            "denied-request",
        )

    assert error.value.code == "MEETING_ORGANIZER_REQUIRED"
    repository.get_meeting_by_id.assert_not_awaited()
    repository.update_meeting.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "not_authorized"


async def test_organizer_reschedule_updates_details_and_status() -> None:
    service, repository, audit_repository = build_service()
    original_start = utc_now_naive() + timedelta(days=1)
    meeting = Meeting(
        id="meeting-1",
        title="Original",
        created_by="organizer",
        start_time=original_start,
        end_time=original_start + timedelta(hours=1),
        place="Old place",
        purpose="Old purpose",
    )
    repository.get_meeting_access_facts = AsyncMock(
        return_value=MeetingAccessFacts(
            meeting_id=meeting.id,
            organizer_user_id="organizer",
        )
    )
    repository.get_meeting_by_id = AsyncMock(return_value=meeting)
    new_start = original_start + timedelta(days=2)

    result = await service.reschedule_meeting(
        AuthenticatedPrincipal("organizer"),
        meeting.id,
        MeetingRescheduleCommand(
            title="Updated",
            place="New place",
            purpose="New purpose",
            personal_gift="Flowers",
            start_time=new_start,
            duration_minutes=30,
        ),
        "reschedule-request",
    )

    assert result.status is MeetingStatus.RESCHEDULED
    assert result.start_time == new_start
    assert result.end_time == new_start + timedelta(minutes=30)
    assert result.place == "New place"
    repository.update_meeting.assert_awaited_once()
    assert audit_repository.events[0].decision_reason == "organizer"


async def test_reschedule_missing_meeting_returns_not_found_and_audits() -> None:
    service, repository, audit_repository = build_service()
    repository.get_meeting_access_facts = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundError):
        await service.reschedule_meeting(
            AuthenticatedPrincipal("organizer"),
            "missing",
            MeetingRescheduleCommand(
                start_time=utc_now_naive() + timedelta(days=2),
                duration_minutes=60,
            ),
            "missing-request",
        )

    repository.update_meeting.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "resource_not_found"
