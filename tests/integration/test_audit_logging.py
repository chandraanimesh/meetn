from datetime import datetime

from tests.conftest import MeetingAPITestContext


def test_meeting_and_transcript_decisions_persist_complete_audit_rows(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    meeting_response = context.client.get(
        f"/api/meetings/{context.meeting_id}",
        headers={"X-Request-ID": "audit-meeting-read"},
    )
    transcript_response = context.client.get(
        f"/api/meetings/{context.meeting_id}/transcript",
        headers={"X-Request-ID": "audit-transcript-read"},
    )

    assert meeting_response.status_code == 200
    assert transcript_response.status_code == 200
    records = context.audit_records()
    assert len(records) == 2
    assert records[0] | {"id": None, "created_at": None} == {
        "id": None,
        "request_id": "audit-meeting-read",
        "actor_user_id": context.participant_id,
        "event_type": "meeting.read",
        "resource_type": "meeting",
        "resource_id": context.meeting_id,
        "action_id": "meeting.read",
        "authorization_decision": "allowed",
        "decision_reason": "participant",
        "created_at": None,
    }
    assert records[1] | {"id": None, "created_at": None} == {
        "id": None,
        "request_id": "audit-transcript-read",
        "actor_user_id": context.participant_id,
        "event_type": "transcript.read",
        "resource_type": "transcript",
        "resource_id": context.meeting_id,
        "action_id": "transcript.read",
        "authorization_decision": "allowed",
        "decision_reason": "participant",
        "created_at": None,
    }
    assert all(isinstance(record["id"], str) for record in records)
    assert all(isinstance(record["created_at"], datetime) for record in records)


def test_cross_meeting_denial_audits_target_without_sensitive_content(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    response = context.client.get(
        f"/api/meetings/{context.other_meeting_id}/transcript",
        headers={"X-Request-ID": "audit-cross-meeting"},
    )

    assert response.status_code == 403
    record = context.audit_records()[0]
    assert record["actor_user_id"] == context.participant_id
    assert record["action_id"] == "transcript.read"
    assert record["resource_type"] == "transcript"
    assert record["resource_id"] == context.other_meeting_id
    assert record["authorization_decision"] == "denied"
    assert record["decision_reason"] == "not_authorized"
    serialized = repr(record)
    assert "Other user's transcript content" not in serialized
    assert context.note_content not in serialized

