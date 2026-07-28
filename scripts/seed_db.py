"""Idempotently seed local demo data after Alembic migrations are applied.

Run:
    uv run alembic upgrade head
    uv run python scripts/seed_db.py

This script never creates, drops, or truncates database objects.
"""

import asyncio
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.domain.entities.meeting import (
    ConfidentialNote,
    Meeting,
    MeetingParticipant,
    ParticipantRole,
    Transcript,
)
from app.domain.entities.user import ExternalIdentity, User
from app.domain.entities.recording import (
    Membership,
    MembershipPlan,
    Recording,
    RecordingProcessingStatus,
)
from app.domain.time import utc_now_naive
from app.infrastructure.database.repositories.meeting_repository import (
    SQLAlchemyMeetingRepository,
)
from app.infrastructure.database.repositories.membership_repository import (
    SQLAlchemyMembershipRepository,
)
from app.infrastructure.database.repositories.recording_repository import (
    SQLAlchemyRecordingRepository,
)
from app.infrastructure.database.repositories.user_repository import (
    SQLAlchemyUserRepository,
)

DEMO_MEETING_TITLE = "Q3 Planning"
DEMO_TRANSCRIPT = "Welcome to Q3 planning. The goals are set..."
DEMO_NOTE = "Need to discuss budget constraints privately."


async def _get_or_create_user(
    repository: SQLAlchemyUserRepository,
    *,
    display_name: str,
    email: str,
    provider_subject: str,
) -> User:
    existing = await repository.get_by_external_identity("google", provider_subject)
    if existing is not None:
        return existing

    return await repository.create_user_with_identity(
        User(display_name=display_name, primary_email=email),
        ExternalIdentity(
            provider="google",
            provider_subject=provider_subject,
            provider_email=email,
            email_verified=True,
        ),
    )


async def seed() -> None:
    engine = create_async_engine(settings.db.async_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            user_repository = SQLAlchemyUserRepository(session)
            meeting_repository = SQLAlchemyMeetingRepository(session)
            recording_repository = SQLAlchemyRecordingRepository(session)
            membership_repository = SQLAlchemyMembershipRepository(session)

            host = await _get_or_create_user(
                user_repository,
                display_name="Demo Host",
                email="host@meetn.example",
                provider_subject="g_123",
            )
            attendee = await _get_or_create_user(
                user_repository,
                display_name="Demo Attendee",
                email="attendee@meetn.example",
                provider_subject="g_456",
            )

            host_meetings = await meeting_repository.list_meetings_by_user(host.id)
            meeting = next(
                (
                    candidate
                    for candidate in host_meetings
                    if candidate.title == DEMO_MEETING_TITLE
                ),
                None,
            )
            if meeting is None:
                start_time = utc_now_naive() + timedelta(days=1)
                meeting = await meeting_repository.create_meeting(
                    Meeting(
                        title=DEMO_MEETING_TITLE,
                        created_by=host.id,
                        start_time=start_time,
                        end_time=start_time + timedelta(hours=1),
                        place="Meetn demo room",
                        purpose="Plan the next quarter",
                        personal_gift="Coffee beans",
                    )
                )

            participants = await meeting_repository.get_participants(
                meeting.id, host.id
            )
            if not any(participant.user_id == attendee.id for participant in participants):
                await meeting_repository.add_participant(
                    MeetingParticipant(
                        meeting_id=meeting.id,
                        user_id=attendee.id,
                        role=ParticipantRole.ATTENDEE,
                    ),
                    actor_user_id=host.id,
                )

            transcript = await meeting_repository.get_transcript(meeting.id, host.id)
            if transcript is None:
                await meeting_repository.add_transcript(
                    Transcript(meeting_id=meeting.id, content=DEMO_TRANSCRIPT),
                    actor_user_id=host.id,
                )

            notes = await meeting_repository.get_confidential_notes(
                meeting.id, host.id
            )
            if not any(note.content == DEMO_NOTE for note in notes):
                await meeting_repository.add_confidential_note(
                    ConfidentialNote(
                        meeting_id=meeting.id,
                        created_by=host.id,
                        content=DEMO_NOTE,
                    ),
                    actor_user_id=host.id,
                )

            await recording_repository.save(
                Recording(
                    meeting_id=meeting.id,
                    processing_status=RecordingProcessingStatus.AVAILABLE,
                    required_plan=MembershipPlan.PROFESSIONAL,
                )
            )
            await membership_repository.save(
                Membership(user_id=host.id, plan=MembershipPlan.PROFESSIONAL)
            )
            await membership_repository.save(
                Membership(user_id=attendee.id, plan=MembershipPlan.STARTER)
            )
    finally:
        await engine.dispose()

    print("Demo seed is present.")


if __name__ == "__main__":
    asyncio.run(seed())
