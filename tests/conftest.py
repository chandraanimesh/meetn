import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.dependencies.database import get_db_session
from app.core.config import settings
from app.domain.entities.meeting import (
    ConfidentialNote,
    ConfidentialNoteAccess,
    Meeting,
    MeetingParticipant,
    ParticipantRole,
    Transcript,
)
from app.domain.entities.user import ExternalIdentity, User
from app.domain.time import utc_now_naive
from app.infrastructure.auth.jwt_cookie_session import JWTCookieSessionManager
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.audit_event import AuditEventModel
from app.infrastructure.database.repositories.meeting_repository import (
    SQLAlchemyMeetingRepository,
)
from app.infrastructure.database.repositories.user_repository import (
    SQLAlchemyUserRepository,
)
from app.main import app


@dataclass(slots=True)
class MeetingAPITestContext:
    client: TestClient
    session_factory: async_sessionmaker[AsyncSession]
    organizer_id: str
    participant_id: str
    granted_user_id: str
    outsider_id: str
    meeting_id: str
    empty_meeting_id: str
    other_meeting_id: str
    transcript_id: str
    note_id: str
    note_content: str
    organizer_token: str
    participant_token: str
    granted_user_token: str
    outsider_token: str

    def authenticate(self, token: str) -> None:
        self.client.cookies.set("app_session", token)

    def clear_authentication(self) -> None:
        self.client.cookies.delete("app_session")

    def audit_events(self) -> list[dict[str, Any]]:
        async def load_events() -> list[dict[str, Any]]:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(
                        AuditEventModel.request_id,
                        AuditEventModel.actor_user_id,
                        AuditEventModel.event_type,
                        AuditEventModel.resource_type,
                        AuditEventModel.resource_id,
                        AuditEventModel.authorization_decision,
                        AuditEventModel.decision_reason,
                    ).order_by(AuditEventModel.created_at)
                )
                return [dict(row) for row in result.mappings().all()]

        return asyncio.run(load_events())

    def audit_records(self) -> list[dict[str, Any]]:
        """Return complete audit rows for security-contract assertions."""

        async def load_records() -> list[dict[str, Any]]:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(
                        AuditEventModel.id,
                        AuditEventModel.request_id,
                        AuditEventModel.actor_user_id,
                        AuditEventModel.event_type,
                        AuditEventModel.resource_type,
                        AuditEventModel.resource_id,
                        AuditEventModel.action_id,
                        AuditEventModel.authorization_decision,
                        AuditEventModel.decision_reason,
                        AuditEventModel.created_at,
                    ).order_by(AuditEventModel.created_at)
                )
                return [dict(row) for row in result.mappings().all()]

        return asyncio.run(load_records())

    def multimodal_audit_records(self) -> list[dict[str, Any]]:
        """Return the Module 9 audit fields without any sensitive content."""

        async def load_records() -> list[dict[str, Any]]:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(
                        AuditEventModel.request_id,
                        AuditEventModel.actor_user_id,
                        AuditEventModel.conversation_id,
                        AuditEventModel.input_modality,
                        AuditEventModel.media_hash,
                        AuditEventModel.media_type,
                        AuditEventModel.media_size,
                        AuditEventModel.provider,
                        AuditEventModel.model_name,
                        AuditEventModel.prompt_version,
                        AuditEventModel.selected_action_id,
                        AuditEventModel.resource_id,
                        AuditEventModel.authorization_decision,
                        AuditEventModel.entitlement_decision,
                        AuditEventModel.tts_allowed,
                        AuditEventModel.latency_ms,
                        AuditEventModel.status,
                        AuditEventModel.error_code,
                        AuditEventModel.created_at,
                    ).order_by(AuditEventModel.created_at)
                )
                return [dict(row) for row in result.mappings().all()]

        return asyncio.run(load_records())


def _session_token(user_id: str) -> str:
    manager = JWTCookieSessionManager(settings.session)
    session = manager.create_session(user_id)
    return str(manager.create_jwt_cookie(session)["value"])


@pytest.fixture
def meeting_api_context(tmp_path: Path) -> Iterator[MeetingAPITestContext]:
    database_path = tmp_path / "meeting-api.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def seed_database() -> dict[str, str]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            users = SQLAlchemyUserRepository(session)
            meetings = SQLAlchemyMeetingRepository(session)

            async def create_user(name: str) -> User:
                subject = name.lower().replace(" ", "-")
                return await users.create_user_with_identity(
                    User(
                        display_name=name,
                        primary_email=f"{subject}@example.invalid",
                    ),
                    ExternalIdentity(
                        provider="api-test",
                        provider_subject=subject,
                        provider_email=f"{subject}@example.invalid",
                        email_verified=True,
                    ),
                )

            organizer = await create_user("API Organizer")
            participant = await create_user("API Participant")
            granted_user = await create_user("API Granted User")
            outsider = await create_user("API Outsider")

            start = utc_now_naive()
            meeting = await meetings.create_meeting(
                Meeting(
                    title="Authorized Meeting",
                    created_by=organizer.id,
                    start_time=start,
                    end_time=start + timedelta(hours=1),
                )
            )
            for user in (participant, granted_user):
                await meetings.add_participant(
                    MeetingParticipant(
                        meeting_id=meeting.id,
                        user_id=user.id,
                        role=ParticipantRole.ATTENDEE,
                    ),
                    actor_user_id=organizer.id,
                )

            transcript = await meetings.add_transcript(
                Transcript(
                    meeting_id=meeting.id,
                    content="Authorized transcript content",
                ),
                actor_user_id=organizer.id,
            )
            note_content = "Authorized confidential note content"
            note = await meetings.add_confidential_note(
                ConfidentialNote(
                    meeting_id=meeting.id,
                    created_by=organizer.id,
                    content=note_content,
                ),
                actor_user_id=organizer.id,
            )
            await meetings.grant_note_access(
                ConfidentialNoteAccess(
                    note_id=note.id,
                    user_id=granted_user.id,
                    granted_by=organizer.id,
                )
            )

            empty_meeting = await meetings.create_meeting(
                Meeting(
                    title="Meeting Without Transcript",
                    created_by=organizer.id,
                    start_time=start + timedelta(days=1),
                    end_time=start + timedelta(days=1, hours=1),
                )
            )
            other_meeting = await meetings.create_meeting(
                Meeting(
                    title="Outsider Meeting",
                    created_by=outsider.id,
                    start_time=start + timedelta(days=2),
                    end_time=start + timedelta(days=2, hours=1),
                )
            )
            await meetings.add_transcript(
                Transcript(
                    meeting_id=other_meeting.id,
                    content="Other user's transcript content",
                ),
                actor_user_id=outsider.id,
            )

            return {
                "organizer_id": organizer.id,
                "participant_id": participant.id,
                "granted_user_id": granted_user.id,
                "outsider_id": outsider.id,
                "meeting_id": meeting.id,
                "empty_meeting_id": empty_meeting.id,
                "other_meeting_id": other_meeting.id,
                "transcript_id": transcript.id,
                "note_id": note.id,
                "note_content": note_content,
            }

    seeded = asyncio.run(seed_database())

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    had_previous_override = get_db_session in app.dependency_overrides
    previous_override = app.dependency_overrides.get(get_db_session)
    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        with TestClient(app) as client:
            yield MeetingAPITestContext(
                client=client,
                session_factory=session_factory,
                organizer_id=seeded["organizer_id"],
                participant_id=seeded["participant_id"],
                granted_user_id=seeded["granted_user_id"],
                outsider_id=seeded["outsider_id"],
                meeting_id=seeded["meeting_id"],
                empty_meeting_id=seeded["empty_meeting_id"],
                other_meeting_id=seeded["other_meeting_id"],
                transcript_id=seeded["transcript_id"],
                note_id=seeded["note_id"],
                note_content=seeded["note_content"],
                organizer_token=_session_token(seeded["organizer_id"]),
                participant_token=_session_token(seeded["participant_id"]),
                granted_user_token=_session_token(seeded["granted_user_id"]),
                outsider_token=_session_token(seeded["outsider_id"]),
            )
    finally:
        if had_previous_override and previous_override is not None:
            app.dependency_overrides[get_db_session] = previous_override
        else:
            app.dependency_overrides.pop(get_db_session, None)
        asyncio.run(engine.dispose())
