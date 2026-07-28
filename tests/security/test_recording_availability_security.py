import asyncio

from app.domain.entities.recording import (
    MembershipPlan,
    Recording,
    RecordingProcessingStatus,
)
from app.infrastructure.database.repositories.recording_repository import (
    SQLAlchemyRecordingRepository,
)
from tests.conftest import MeetingAPITestContext


def test_idor_cannot_distinguish_another_users_meeting_from_missing_resource(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.outsider_token)

    protected = context.client.get(
        f"/api/meetings/{context.meeting_id}/recording-availability"
    )
    missing = context.client.get(
        "/api/meetings/does-not-exist/recording-availability"
    )

    assert protected.status_code == 200
    assert missing.status_code == 200
    for response in (protected, missing):
        body = response.json()
        assert body["availability"] is False
        assert body["verified_reason"] == "unauthorized"
        assert body["required_plan"] is None
        assert body["allowed_alternative_action_ids"] == []


def test_frontend_cannot_supply_membership_or_identity_flags(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.outsider_token)

    response = context.client.get(
        f"/api/meetings/{context.meeting_id}/recording-availability",
        params={
            "user_id": context.organizer_id,
            "plan": "organization",
            "has_premium": "true",
        },
    )

    assert response.status_code == 200
    assert response.json()["verified_reason"] == "unauthorized"
    assert response.json()["availability"] is False


def test_authorized_participant_cannot_forge_recording_entitlement(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context

    async def seed_available_recording() -> None:
        async with context.session_factory() as session:
            await SQLAlchemyRecordingRepository(session).save(
                Recording(
                    meeting_id=context.meeting_id,
                    processing_status=RecordingProcessingStatus.AVAILABLE,
                    required_plan=MembershipPlan.PROFESSIONAL,
                )
            )

    asyncio.run(seed_available_recording())
    context.authenticate(context.participant_token)

    response = context.client.get(
        f"/api/meetings/{context.meeting_id}/recording-availability",
        params={
            "plan": "organization",
            "membership_plan": "organization",
            "has_premium": "true",
            "is_admin": "true",
        },
        headers={"X-Request-ID": "forged-entitlement"},
    )

    assert response.status_code == 200
    assert response.json()["availability"] is False
    assert response.json()["verified_reason"] == "plan_restriction"
    assert response.json()["required_plan"] == "professional"
    event = context.audit_records()[0]
    assert event["request_id"] == "forged-entitlement"
    assert event["actor_user_id"] == context.participant_id
    assert event["action_id"] == "recording.availability.check"
    assert event["resource_type"] == "recording_availability"
    assert event["resource_id"] == context.meeting_id
    assert event["authorization_decision"] == "denied"
    assert event["decision_reason"] == "plan_restriction"
