import asyncio

from app.domain.entities.recording import (
    Membership,
    MembershipPlan,
    Recording,
    RecordingProcessingStatus,
)
from app.infrastructure.database.repositories.membership_repository import (
    SQLAlchemyMembershipRepository,
)
from app.infrastructure.database.repositories.recording_repository import (
    SQLAlchemyRecordingRepository,
)
from tests.conftest import MeetingAPITestContext


def seed_recording_access(
    context: MeetingAPITestContext,
    *,
    meeting_id: str,
    processing_status: RecordingProcessingStatus,
    member_user_id: str | None = None,
    member_plan: MembershipPlan = MembershipPlan.PROFESSIONAL,
) -> None:
    async def seed() -> None:
        async with context.session_factory() as session:
            await SQLAlchemyRecordingRepository(session).save(
                Recording(
                    meeting_id=meeting_id,
                    processing_status=processing_status,
                    required_plan=MembershipPlan.PROFESSIONAL,
                )
            )
            if member_user_id is not None:
                await SQLAlchemyMembershipRepository(session).save(
                    Membership(user_id=member_user_id, plan=member_plan)
                )

    asyncio.run(seed())


def test_recording_availability_requires_verified_session(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.clear_authentication()

    response = context.client.get(
        f"/api/meetings/{context.meeting_id}/recording-availability"
    )

    assert response.status_code == 401


def test_available_and_plan_restricted_responses_are_backend_verified(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    seed_recording_access(
        context,
        meeting_id=context.meeting_id,
        processing_status=RecordingProcessingStatus.AVAILABLE,
        member_user_id=context.organizer_id,
    )
    path = f"/api/meetings/{context.meeting_id}/recording-availability"

    context.authenticate(context.organizer_token)
    available = context.client.get(path, headers={"X-Request-ID": "available"})
    context.authenticate(context.participant_token)
    restricted = context.client.get(
        path, headers={"X-Request-ID": "restricted"}
    )

    assert available.status_code == 200
    assert available.json() == {
        "meeting_id": context.meeting_id,
        "availability": True,
        "verified_reason": "available",
        "required_plan": None,
        "allowed_alternative_action_ids": [],
    }
    assert restricted.status_code == 200
    assert restricted.json() == {
        "meeting_id": context.meeting_id,
        "availability": False,
        "verified_reason": "plan_restriction",
        "required_plan": "professional",
        "allowed_alternative_action_ids": [
            "open_transcript",
            "open_membership_plans",
        ],
    }
    events = context.audit_events()
    assert [event["request_id"] for event in events] == [
        "available",
        "restricted",
    ]
    assert [event["decision_reason"] for event in events] == [
        "available",
        "plan_restriction",
    ]


def test_processing_state_is_returned_without_plan_requirement(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    seed_recording_access(
        context,
        meeting_id=context.empty_meeting_id,
        processing_status=RecordingProcessingStatus.PROCESSING,
    )
    context.authenticate(context.organizer_token)

    processing = context.client.get(
        f"/api/meetings/{context.empty_meeting_id}/recording-availability"
    )

    assert processing.status_code == 200
    assert processing.json() == {
        "meeting_id": context.empty_meeting_id,
        "availability": False,
        "verified_reason": "processing",
        "required_plan": None,
        "allowed_alternative_action_ids": [],
    }


def test_authorized_meeting_without_recording_reports_not_created(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)

    response = context.client.get(
        f"/api/meetings/{context.empty_meeting_id}/recording-availability"
    )

    assert response.status_code == 200
    assert response.json() == {
        "meeting_id": context.empty_meeting_id,
        "availability": False,
        "verified_reason": "not_created",
        "required_plan": None,
        "allowed_alternative_action_ids": [],
    }
