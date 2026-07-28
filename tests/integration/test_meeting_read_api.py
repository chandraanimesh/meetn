from tests.conftest import MeetingAPITestContext


def test_meeting_read_endpoints_require_verified_session(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.clear_authentication()

    paths = (
        "/api/me/meetings",
        f"/api/meetings/{context.meeting_id}",
        f"/api/meetings/{context.meeting_id}/transcript",
        f"/api/meetings/{context.meeting_id}/confidential-notes",
    )

    for path in paths:
        response = context.client.get(path)
        assert response.status_code == 401


def test_list_and_detail_return_only_current_users_meetings(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    list_response = context.client.get("/api/me/meetings")
    detail_response = context.client.get(f"/api/meetings/{context.meeting_id}")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [
        context.meeting_id
    ]
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == context.meeting_id
    assert {
        participant["user_id"]
        for participant in detail_response.json()["participants"]
    } == {
        context.organizer_id,
        context.participant_id,
        context.granted_user_id,
    }


def test_transcript_read_and_missing_resource_mapping(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)

    response = context.client.get(
        f"/api/meetings/{context.meeting_id}/transcript"
    )
    missing_transcript = context.client.get(
        f"/api/meetings/{context.empty_meeting_id}/transcript"
    )
    missing_meeting = context.client.get("/api/meetings/does-not-exist")

    assert response.status_code == 200
    assert response.json()["id"] == context.transcript_id
    assert response.json()["content"] == "Authorized transcript content"
    assert missing_transcript.status_code == 404
    assert missing_transcript.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert missing_meeting.status_code == 404


def test_confidential_notes_are_filtered_and_every_attempt_is_audited(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    path = f"/api/meetings/{context.meeting_id}/confidential-notes"

    context.authenticate(context.participant_token)
    filtered_response = context.client.get(path, headers={"X-Request-ID": "filtered"})

    context.authenticate(context.granted_user_token)
    granted_response = context.client.get(path, headers={"X-Request-ID": "granted"})

    assert filtered_response.status_code == 200
    assert filtered_response.json() == {"meeting_id": context.meeting_id, "items": []}
    assert granted_response.status_code == 200
    assert granted_response.json()["items"][0]["id"] == context.note_id
    assert granted_response.json()["items"][0]["content"] == context.note_content

    events = context.audit_events()
    assert [event["request_id"] for event in events] == ["filtered", "granted"]
    assert [event["authorization_decision"] for event in events] == [
        "allowed",
        "allowed",
    ]
    assert [event["decision_reason"] for event in events] == [
        "no_accessible_notes",
        "explicit_user",
    ]
    assert all(event["event_type"] == "confidential_notes.read" for event in events)
    complete_records = context.audit_records()
    assert all(
        record["action_id"] == "confidential_notes.read"
        for record in complete_records
    )
    assert all(record["created_at"] is not None for record in complete_records)
    assert context.note_content not in repr(complete_records)


def test_confidential_notes_not_found_attempt_is_audited(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)

    response = context.client.get(
        "/api/meetings/does-not-exist/confidential-notes",
        headers={"X-Request-ID": "missing-notes"},
    )

    assert response.status_code == 404
    assert context.audit_events() == [
        {
            "request_id": "missing-notes",
            "actor_user_id": context.organizer_id,
            "event_type": "confidential_notes.read",
            "resource_type": "confidential_note_collection",
            "resource_id": "does-not-exist",
            "authorization_decision": "denied",
            "decision_reason": "resource_not_found",
        }
    ]
