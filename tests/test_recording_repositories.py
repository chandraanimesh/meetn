from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domain.entities.meeting import Meeting
from app.domain.entities.recording import (
    Membership,
    MembershipPlan,
    MembershipStatus,
    Recording,
    RecordingProcessingStatus,
)
from app.domain.entities.user import ExternalIdentity, User
from app.domain.time import utc_now_naive
from app.infrastructure.database.base import Base
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

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as database_session:
        yield database_session
    await engine.dispose()


async def test_recording_repository_persists_and_updates_by_meeting(
    session: AsyncSession,
) -> None:
    users = SQLAlchemyUserRepository(session)
    meetings = SQLAlchemyMeetingRepository(session)
    recordings = SQLAlchemyRecordingRepository(session)
    organizer = await users.create_user_with_identity(
        User(display_name="Organizer", primary_email="organizer@example.invalid"),
        ExternalIdentity(
            provider="test",
            provider_subject="recording-organizer",
            provider_email="organizer@example.invalid",
        ),
    )
    start = utc_now_naive()
    meeting = await meetings.create_meeting(
        Meeting(
            title="Recorded meeting",
            created_by=organizer.id,
            start_time=start,
            end_time=start + timedelta(hours=1),
        )
    )

    created = await recordings.save(
        Recording(
            meeting_id=meeting.id,
            processing_status=RecordingProcessingStatus.PROCESSING,
        )
    )
    updated = await recordings.save(
        Recording(
            id=created.id,
            meeting_id=meeting.id,
            processing_status=RecordingProcessingStatus.AVAILABLE,
            required_plan=MembershipPlan.ORGANIZATION,
            created_at=created.created_at,
        )
    )

    assert updated.id == created.id
    assert updated.processing_status is RecordingProcessingStatus.AVAILABLE
    assert updated.required_plan is MembershipPlan.ORGANIZATION
    assert await recordings.get_by_meeting("missing-meeting") is None


async def test_membership_repository_persists_and_updates_by_user(
    session: AsyncSession,
) -> None:
    users = SQLAlchemyUserRepository(session)
    memberships = SQLAlchemyMembershipRepository(session)
    user = await users.create_user_with_identity(
        User(display_name="Member", primary_email="member@example.invalid"),
        ExternalIdentity(
            provider="test",
            provider_subject="membership-user",
            provider_email="member@example.invalid",
        ),
    )
    created = await memberships.save(
        Membership(user_id=user.id, plan=MembershipPlan.STARTER)
    )
    updated = await memberships.save(
        Membership(
            id=created.id,
            user_id=user.id,
            plan=MembershipPlan.PROFESSIONAL,
            status=MembershipStatus.INACTIVE,
            updated_at=utc_now_naive(),
        )
    )

    assert updated.id == created.id
    assert updated.plan is MembershipPlan.PROFESSIONAL
    assert updated.status is MembershipStatus.INACTIVE
    assert await memberships.get_by_user("missing-user") is None

