import os
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.entities.meeting import (
    ConfidentialNote,
    ConfidentialNoteAccess,
    Meeting,
    MeetingParticipant,
    ParticipantRole,
    Transcript,
)
from app.domain.entities.audit_event import AuditDecision, AuditEvent
from app.domain.entities.recording import (
    Membership,
    MembershipPlan,
    Recording,
    RecordingProcessingStatus,
)
from app.domain.entities.user import ExternalIdentity, User
from app.domain.time import utc_now_naive
from app.infrastructure.database.repositories.meeting_repository import (
    SQLAlchemyMeetingRepository,
)
from app.infrastructure.database.models.audit_event import AuditEventModel
from app.infrastructure.database.repositories.audit_repository import (
    SQLAlchemyAuditRepository,
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def require_test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(database_url)
    database_name = parsed_url.database or ""
    if "test" not in database_name.lower():
        pytest.fail("TEST_DATABASE_URL must target a database containing 'test'")
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    return database_url


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def test_postgres_migrations_round_trip() -> None:
    database_url = require_test_database_url()
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.asyncio
async def test_postgres_repository_security_and_persistence() -> None:
    database_url = require_test_database_url()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            user_repository = SQLAlchemyUserRepository(session)
            meeting_repository = SQLAlchemyMeetingRepository(session)
            membership_repository = SQLAlchemyMembershipRepository(session)
            recording_repository = SQLAlchemyRecordingRepository(session)
            audit_repository = SQLAlchemyAuditRepository(session)

            organizer = await user_repository.create_user_with_identity(
                User(
                    display_name="Integration Organizer",
                    primary_email="integration-organizer@example.invalid",
                ),
                ExternalIdentity(
                    provider="integration",
                    provider_subject="organizer",
                    provider_email="integration-organizer@example.invalid",
                ),
            )
            attendee = await user_repository.create_user_with_identity(
                User(
                    display_name="Integration Attendee",
                    primary_email="integration-attendee@example.invalid",
                ),
                ExternalIdentity(
                    provider="integration",
                    provider_subject="attendee",
                    provider_email="integration-attendee@example.invalid",
                ),
            )
            outsider = await user_repository.create_user_with_identity(
                User(
                    display_name="Integration Outsider",
                    primary_email="integration-outsider@example.invalid",
                ),
                ExternalIdentity(
                    provider="integration",
                    provider_subject="outsider",
                    provider_email="integration-outsider@example.invalid",
                ),
            )

            start_time = utc_now_naive()
            meeting = await meeting_repository.create_meeting(
                Meeting(
                    title="PostgreSQL Integration",
                    created_by=organizer.id,
                    start_time=start_time,
                    end_time=start_time + timedelta(hours=1),
                )
            )
            await meeting_repository.add_participant(
                MeetingParticipant(
                    meeting_id=meeting.id,
                    user_id=attendee.id,
                    role=ParticipantRole.ATTENDEE,
                ),
                actor_user_id=organizer.id,
            )
            transcript = await meeting_repository.add_transcript(
                Transcript(meeting_id=meeting.id, content="integration transcript"),
                actor_user_id=organizer.id,
            )
            note = await meeting_repository.add_confidential_note(
                ConfidentialNote(
                    meeting_id=meeting.id,
                    created_by=organizer.id,
                    content="integration note",
                ),
                actor_user_id=organizer.id,
            )
            await meeting_repository.grant_note_access(
                ConfidentialNoteAccess(
                    note_id=note.id,
                    user_id=attendee.id,
                    granted_by=organizer.id,
                )
            )
            saved_recording = await recording_repository.save(
                Recording(
                    meeting_id=meeting.id,
                    processing_status=RecordingProcessingStatus.AVAILABLE,
                    required_plan=MembershipPlan.PROFESSIONAL,
                )
            )
            saved_membership = await membership_repository.save(
                Membership(
                    user_id=attendee.id,
                    plan=MembershipPlan.PROFESSIONAL,
                )
            )
            audit_event = AuditEvent(
                request_id="postgres-audit-request",
                actor_user_id=attendee.id,
                event_type="transcript.read",
                action_id="transcript.read",
                resource_type="transcript",
                resource_id=meeting.id,
                authorization_decision=AuditDecision.ALLOWED,
                decision_reason="participant",
            )
            await audit_repository.append(audit_event)

            assert (
                await meeting_repository.get_transcript(meeting.id, attendee.id)
            ).id == transcript.id  # type: ignore[union-attr]
            assert (
                await meeting_repository.get_transcript(meeting.id, outsider.id)
                is None
            )
            assert len(
                await meeting_repository.get_confidential_notes(
                    meeting.id, attendee.id
                )
            ) == 1
            assert (
                await meeting_repository.get_confidential_note_by_id(
                    note.id, outsider.id
                )
                is None
            )
            assert (
                await recording_repository.get_by_meeting(meeting.id)
            ) == saved_recording
            assert (
                await membership_repository.get_by_user(attendee.id)
            ) == saved_membership
            audit_result = await session.execute(
                select(AuditEventModel).where(
                    AuditEventModel.id == audit_event.id
                )
            )
            persisted_audit = audit_result.scalar_one()
            assert persisted_audit.request_id == "postgres-audit-request"
            assert persisted_audit.actor_user_id == attendee.id
            assert persisted_audit.event_type == "transcript.read"
            assert persisted_audit.action_id == "transcript.read"
            assert persisted_audit.resource_type == "transcript"
            assert persisted_audit.resource_id == meeting.id
            assert persisted_audit.authorization_decision == "allowed"
            assert persisted_audit.decision_reason == "participant"
            assert persisted_audit.created_at is not None
    finally:
        await engine.dispose()
