from dataclasses import dataclass, field
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from app.application.exceptions import (
    ResourceAccessDeniedError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.application.ports.audit_repository import AuditRepositoryPort
from app.application.ports.meeting_repository import (
    MeetingRepositoryPort,
    TranscriptAlreadyExistsError,
)
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.application.services.transcript_management_service import (
    MAX_TRANSCRIPT_CHARACTERS,
    TranscriptManagementService,
)
from app.domain.entities.audit_event import AuditEvent
from app.domain.entities.meeting import Transcript
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    MeetingAccessFacts,
)


pytestmark = pytest.mark.asyncio

ORGANIZER_ID = "organizer"
PARTICIPANT_ID = "participant"
MEETING_ID = "meeting-1"


@dataclass(slots=True)
class InMemoryAuditRepository(AuditRepositoryPort):
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


def build_service() -> tuple[
    TranscriptManagementService,
    Mock,
    InMemoryAuditRepository,
]:
    repository = Mock(spec=MeetingRepositoryPort)
    repository.get_meeting_access_facts = AsyncMock(
        return_value=MeetingAccessFacts(
            meeting_id=MEETING_ID,
            organizer_user_id=ORGANIZER_ID,
            active_participant_user_ids=frozenset(
                {ORGANIZER_ID, PARTICIPANT_ID}
            ),
        )
    )
    repository.transcript_exists = AsyncMock(return_value=False)
    repository.add_transcript = AsyncMock(
        side_effect=lambda transcript, actor_user_id: transcript
    )
    audit_repository = InMemoryAuditRepository()
    service = TranscriptManagementService(
        meeting_repository=cast(MeetingRepositoryPort, repository),
        authorization_service=AuthorizationService(),
        audit_service=AuditService(audit_repository),
    )
    return service, repository, audit_repository


async def test_organizer_creates_trimmed_transcript_and_audits_without_content() -> None:
    service, repository, audit_repository = build_service()

    result = await service.create_transcript(
        AuthenticatedPrincipal(user_id=ORGANIZER_ID),
        MEETING_ID,
        "  Speaker: Safe transcript text  ",
        "transcript-create",
    )

    assert result.meeting_id == MEETING_ID
    assert result.content == "Speaker: Safe transcript text"
    created = repository.add_transcript.await_args.args[0]
    assert isinstance(created, Transcript)
    assert created.content == "Speaker: Safe transcript text"
    assert repository.add_transcript.await_args.kwargs == {
        "actor_user_id": ORGANIZER_ID
    }
    event = audit_repository.events[0]
    assert event.event_type == "transcript.create"
    assert event.authorization_decision.value == "allowed"
    assert event.decision_reason == "organizer"
    assert result.content not in repr(event)


async def test_participant_cannot_create_transcript_or_probe_existing_state() -> None:
    service, repository, audit_repository = build_service()

    with pytest.raises(ResourceAccessDeniedError) as raised:
        await service.create_transcript(
            AuthenticatedPrincipal(user_id=PARTICIPANT_ID),
            MEETING_ID,
            "Participant supplied content",
            "participant-create",
        )

    assert raised.value.code == "MEETING_ORGANIZER_REQUIRED"
    repository.transcript_exists.assert_not_awaited()
    repository.add_transcript.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "not_authorized"


async def test_missing_meeting_returns_not_found_before_transcript_lookup() -> None:
    service, repository, audit_repository = build_service()
    repository.get_meeting_access_facts.return_value = None

    with pytest.raises(ResourceNotFoundError):
        await service.create_transcript(
            AuthenticatedPrincipal(user_id=ORGANIZER_ID),
            "missing",
            "Transcript",
            "missing-create",
        )

    repository.transcript_exists.assert_not_awaited()
    repository.add_transcript.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "resource_not_found"


@pytest.mark.parametrize("race_conflict", [False, True])
async def test_duplicate_transcript_is_audited_and_never_overwritten(
    race_conflict: bool,
) -> None:
    service, repository, audit_repository = build_service()
    if race_conflict:
        repository.add_transcript.side_effect = TranscriptAlreadyExistsError
    else:
        repository.transcript_exists.return_value = True

    with pytest.raises(ResourceConflictError) as raised:
        await service.create_transcript(
            AuthenticatedPrincipal(user_id=ORGANIZER_ID),
            MEETING_ID,
            "Replacement content",
            "duplicate-create",
        )

    assert raised.value.code == "TRANSCRIPT_ALREADY_EXISTS"
    assert audit_repository.events[0].decision_reason == "transcript_already_exists"


@pytest.mark.parametrize(
    "content",
    ["", "   ", "valid\x00invalid", "x" * (MAX_TRANSCRIPT_CHARACTERS + 1)],
    ids=("empty", "whitespace", "null-character", "oversized"),
)
async def test_invalid_transcript_content_is_rejected_before_resource_lookup(
    content: str,
) -> None:
    service, repository, audit_repository = build_service()

    with pytest.raises(ValueError):
        await service.create_transcript(
            AuthenticatedPrincipal(user_id=ORGANIZER_ID),
            MEETING_ID,
            content,
            "invalid-content",
        )

    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events == []
