from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities.meeting import (
    ConfidentialNote,
    ConfidentialNoteAccess,
    Meeting,
    MeetingParticipant,
    MeetingStatus,
    ParticipantMembershipStatus,
    ParticipantRole,
    Transcript,
)
from app.domain.entities.user import ExternalIdentity, User
from app.domain.time import utc_now_naive
from app.infrastructure.database.base import Base
from app.infrastructure.database.repositories.meeting_repository import (
    SQLAlchemyMeetingRepository,
)
from app.application.ports.meeting_repository import TranscriptAlreadyExistsError
from app.infrastructure.database.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.asyncio

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def setup_db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def session(setup_db):
    async with TestingSessionLocal() as database_session:
        yield database_session


@pytest_asyncio.fixture
async def user_repo(session: AsyncSession) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


@pytest_asyncio.fixture
async def meeting_repo(session: AsyncSession) -> SQLAlchemyMeetingRepository:
    return SQLAlchemyMeetingRepository(session)


async def create_user(
    repository: SQLAlchemyUserRepository, name: str
) -> User:
    subject = name.lower().replace(" ", "-")
    return await repository.create_user_with_identity(
        User(display_name=name, primary_email=f"{subject}@example.com"),
        ExternalIdentity(
            provider="test",
            provider_subject=subject,
            provider_email=f"{subject}@example.com",
        ),
    )


def build_meeting(organizer_id: str, title: str = "Weekly Sync") -> Meeting:
    start = utc_now_naive()
    return Meeting(
        title=title,
        created_by=organizer_id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        place="Room 1",
        purpose="Weekly planning",
        personal_gift="Coffee",
    )


async def test_create_and_get_meeting_is_actor_scoped(
    user_repo: SQLAlchemyUserRepository,
    meeting_repo: SQLAlchemyMeetingRepository,
) -> None:
    organizer = await create_user(user_repo, "Alice")
    outsider = await create_user(user_repo, "Outsider")

    created_meeting = await meeting_repo.create_meeting(build_meeting(organizer.id))

    fetched = await meeting_repo.get_meeting_by_id(
        created_meeting.id, organizer.id
    )
    hidden = await meeting_repo.get_meeting_by_id(created_meeting.id, outsider.id)
    access_facts = await meeting_repo.get_meeting_access_facts(created_meeting.id)

    assert fetched is not None
    assert fetched.title == "Weekly Sync"
    assert fetched.status == MeetingStatus.SCHEDULED
    assert fetched.place == "Room 1"
    assert fetched.purpose == "Weekly planning"
    assert fetched.personal_gift == "Coffee"
    assert [participant.user_id for participant in fetched.participants] == [
        organizer.id
    ]
    assert hidden is None
    assert access_facts is not None
    assert access_facts.organizer_user_id == organizer.id
    assert access_facts.active_participant_user_ids == frozenset({organizer.id})
    assert await meeting_repo.get_meeting_access_facts("missing") is None


async def test_update_meeting_persists_rescheduled_fields_for_organizer_only(
    user_repo: SQLAlchemyUserRepository,
    meeting_repo: SQLAlchemyMeetingRepository,
) -> None:
    organizer = await create_user(user_repo, "Schedule Owner")
    outsider = await create_user(user_repo, "Schedule Outsider")
    meeting = await meeting_repo.create_meeting(build_meeting(organizer.id))
    meeting.status = MeetingStatus.RESCHEDULED
    meeting.place = "Room 2"
    meeting.purpose = "Updated planning"
    meeting.personal_gift = "Flowers"

    with pytest.raises(PermissionError):
        await meeting_repo.update_meeting(meeting, actor_user_id=outsider.id)

    updated = await meeting_repo.update_meeting(
        meeting, actor_user_id=organizer.id
    )

    assert updated.status is MeetingStatus.RESCHEDULED
    assert updated.place == "Room 2"
    assert updated.purpose == "Updated planning"
    assert updated.personal_gift == "Flowers"


async def test_participant_membership_controls_meeting_visibility(
    user_repo: SQLAlchemyUserRepository,
    meeting_repo: SQLAlchemyMeetingRepository,
) -> None:
    organizer = await create_user(user_repo, "Bob")
    attendee = await create_user(user_repo, "Charlie")
    newcomer = await create_user(user_repo, "Dana")
    meeting = await meeting_repo.create_meeting(
        build_meeting(organizer.id, "Planning")
    )

    await meeting_repo.add_participant(
        MeetingParticipant(
            meeting_id=meeting.id,
            user_id=attendee.id,
            role=ParticipantRole.ATTENDEE,
        ),
        actor_user_id=organizer.id,
    )

    participants = await meeting_repo.get_participants(meeting.id, organizer.id)
    attendee_meetings = await meeting_repo.list_meetings_by_user(attendee.id)

    assert {participant.user_id for participant in participants} == {
        organizer.id,
        attendee.id,
    }
    assert [item.id for item in attendee_meetings] == [meeting.id]

    with pytest.raises(PermissionError):
        await meeting_repo.add_participant(
            MeetingParticipant(
                meeting_id=meeting.id,
                user_id=newcomer.id,
                role=ParticipantRole.ATTENDEE,
            ),
            actor_user_id=attendee.id,
        )

    removed = await meeting_repo.update_participant_membership(
        meeting.id,
        attendee.id,
        ParticipantMembershipStatus.REMOVED,
        actor_user_id=organizer.id,
    )

    assert removed is not None
    assert removed.membership_status is ParticipantMembershipStatus.REMOVED
    assert await meeting_repo.list_meetings_by_user(attendee.id) == []
    assert await meeting_repo.get_participants(meeting.id, attendee.id) == []


async def test_transcript_and_confidential_note_access_is_scoped_and_revocable(
    user_repo: SQLAlchemyUserRepository,
    meeting_repo: SQLAlchemyMeetingRepository,
) -> None:
    organizer = await create_user(user_repo, "Eve")
    attendee = await create_user(user_repo, "Frank")
    outsider = await create_user(user_repo, "Grace")
    meeting = await meeting_repo.create_meeting(
        build_meeting(organizer.id, "Secret Project")
    )
    await meeting_repo.add_participant(
        MeetingParticipant(
            meeting_id=meeting.id,
            user_id=attendee.id,
            role=ParticipantRole.ATTENDEE,
        ),
        actor_user_id=organizer.id,
    )

    transcript = await meeting_repo.add_transcript(
        Transcript(meeting_id=meeting.id, content="Sensitive transcript"),
        actor_user_id=organizer.id,
    )
    note = await meeting_repo.add_confidential_note(
        ConfidentialNote(
            meeting_id=meeting.id,
            created_by=organizer.id,
            content="Sensitive note",
        ),
        actor_user_id=organizer.id,
    )

    assert (
        await meeting_repo.get_transcript(meeting.id, attendee.id)
    ).id == transcript.id  # type: ignore[union-attr]
    assert await meeting_repo.get_transcript(meeting.id, outsider.id) is None
    assert await meeting_repo.get_confidential_notes(meeting.id, attendee.id) == []
    assert (
        await meeting_repo.get_confidential_note_by_id(note.id, outsider.id)
        is None
    )

    await meeting_repo.grant_note_access(
        ConfidentialNoteAccess(
            note_id=note.id,
            user_id=attendee.id,
            granted_by=organizer.id,
        )
    )
    note_access_facts = await meeting_repo.get_confidential_note_access_facts(
        meeting.id
    )
    granted_note = await meeting_repo.get_confidential_note_by_id(
        note.id, attendee.id
    )
    assert granted_note is not None
    assert granted_note.id == note.id
    assert len(note_access_facts) == 1
    assert note_access_facts[0].note_id == note.id
    assert note_access_facts[0].allowed_user_ids == frozenset({attendee.id})

    assert await meeting_repo.revoke_note_access(
        note.id, attendee.id, organizer.id
    )
    assert await meeting_repo.get_confidential_notes(meeting.id, attendee.id) == []

    await meeting_repo.grant_note_access(
        ConfidentialNoteAccess(
            note_id=note.id,
            user_id=attendee.id,
            granted_by=organizer.id,
        )
    )
    await meeting_repo.update_participant_membership(
        meeting.id,
        attendee.id,
        ParticipantMembershipStatus.REVOKED,
        actor_user_id=organizer.id,
    )

    assert await meeting_repo.get_transcript(meeting.id, attendee.id) is None
    assert await meeting_repo.get_confidential_notes(meeting.id, attendee.id) == []


async def test_failed_writes_are_rolled_back_and_session_remains_usable(
    user_repo: SQLAlchemyUserRepository,
    meeting_repo: SQLAlchemyMeetingRepository,
) -> None:
    organizer = await create_user(user_repo, "Heidi")

    with pytest.raises(IntegrityError):
        await user_repo.create_user_with_identity(
            User(display_name="Duplicate", primary_email="duplicate@example.com"),
            ExternalIdentity(
                provider="test",
                provider_subject="heidi",
                provider_email="duplicate@example.com",
            ),
        )

    assert await user_repo.get_by_id(organizer.id) is not None

    meeting = await meeting_repo.create_meeting(build_meeting(organizer.id))
    first_transcript = await meeting_repo.add_transcript(
        Transcript(meeting_id=meeting.id, content="First"),
        actor_user_id=organizer.id,
    )
    assert await meeting_repo.transcript_exists(meeting.id)
    assert not await meeting_repo.transcript_exists("missing")

    with pytest.raises(TranscriptAlreadyExistsError):
        await meeting_repo.add_transcript(
            Transcript(meeting_id=meeting.id, content="Duplicate"),
            actor_user_id=organizer.id,
        )

    persisted = await meeting_repo.get_transcript(meeting.id, organizer.id)
    assert persisted is not None
    assert persisted.id == first_transcript.id
