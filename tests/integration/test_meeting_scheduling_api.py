from datetime import UTC, datetime, timedelta

from tests.conftest import MeetingAPITestContext


def scheduling_payload() -> dict[str, object]:
    return {
        "title": "Product planning",
        "place": "Meeting room 3",
        "purpose": "Plan the product launch",
        "personal_gift": "Coffee beans",
        "start_time": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "duration_minutes": 60,
    }


def csrf_headers(
    context: MeetingAPITestContext,
    *,
    request_id: str,
) -> dict[str, str]:
    session = context.client.get("/api/v1/session")
    assert session.status_code == 200
    return {
        "X-CSRF-Token": session.json()["csrf_token"],
        "X-Request-ID": request_id,
    }


def test_create_meeting_uses_only_authenticated_actor_and_audits(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    response = context.client.post(
        "/api/meetings",
        json=scheduling_payload(),
        headers=csrf_headers(context, request_id="manual-create"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["organizer_id"] == context.participant_id
    assert body["status"] == "scheduled"
    assert body["place"] == "Meeting room 3"
    assert body["purpose"] == "Plan the product launch"
    assert body["personal_gift"] == "Coffee beans"
    event = context.audit_records()[0]
    assert event["request_id"] == "manual-create"
    assert event["actor_user_id"] == context.participant_id
    assert event["action_id"] == "meeting.create"
    assert event["resource_id"] == body["id"]
    assert event["authorization_decision"] == "allowed"


def test_create_meeting_requires_session_and_valid_csrf(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.clear_authentication()
    missing_session = context.client.post(
        "/api/meetings", json=scheduling_payload()
    )
    assert missing_session.status_code == 401

    context.authenticate(context.participant_token)
    missing_csrf = context.client.post(
        "/api/meetings", json=scheduling_payload()
    )
    invalid_csrf = context.client.post(
        "/api/meetings",
        json=scheduling_payload(),
        headers={"X-CSRF-Token": "invalid"},
    )

    assert missing_csrf.status_code == 403
    assert invalid_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    assert context.audit_records() == []


def test_frontend_user_id_and_unexpected_fields_are_rejected(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    payload = scheduling_payload()
    payload["user_id"] = context.organizer_id

    response = context.client.post(
        "/api/meetings",
        json=payload,
        headers=csrf_headers(context, request_id="identity-tamper"),
    )

    assert response.status_code == 422
    assert context.audit_records() == []


def test_participant_cannot_reschedule_organizers_meeting(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    response = context.client.patch(
        f"/api/meetings/{context.meeting_id}/schedule",
        json={
            "start_time": (datetime.now(UTC) + timedelta(days=8)).isoformat(),
            "duration_minutes": 90,
        },
        headers=csrf_headers(context, request_id="participant-reschedule"),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MEETING_ORGANIZER_REQUIRED"
    event = context.audit_records()[0]
    assert event["authorization_decision"] == "denied"
    assert event["decision_reason"] == "not_authorized"


def test_organizer_reschedules_meeting_and_cannot_change_another_meeting(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)
    payload = {
        **scheduling_payload(),
        "start_time": (datetime.now(UTC) + timedelta(days=9)).isoformat(),
        "duration_minutes": 30,
    }

    changed = context.client.patch(
        f"/api/meetings/{context.meeting_id}/schedule",
        json=payload,
        headers=csrf_headers(context, request_id="organizer-reschedule"),
    )
    bola_attempt = context.client.patch(
        f"/api/meetings/{context.other_meeting_id}/schedule",
        json=payload,
        headers=csrf_headers(context, request_id="organizer-bola"),
    )

    assert changed.status_code == 200
    assert changed.json()["status"] == "rescheduled"
    assert changed.json()["place"] == "Meeting room 3"
    assert bola_attempt.status_code == 403
    assert bola_attempt.json()["error"]["code"] == "MEETING_ORGANIZER_REQUIRED"
    records = context.audit_records()
    assert [record["request_id"] for record in records] == [
        "organizer-reschedule",
        "organizer-bola",
    ]
    assert [record["authorization_decision"] for record in records] == [
        "allowed",
        "denied",
    ]
