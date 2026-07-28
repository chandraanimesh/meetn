from tests.conftest import MeetingAPITestContext


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


def test_organizer_adds_transcript_then_reads_it(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)
    path = f"/api/meetings/{context.empty_meeting_id}/transcript"

    created = context.client.post(
        path,
        json={"content": "  Uploaded meeting transcript  "},
        headers=csrf_headers(context, request_id="transcript-upload"),
    )
    read = context.client.get(path)

    assert created.status_code == 201
    assert created.json()["meeting_id"] == context.empty_meeting_id
    assert created.json()["content"] == "Uploaded meeting transcript"
    assert read.status_code == 200
    assert read.json()["id"] == created.json()["id"]
    assert read.json()["content"] == "Uploaded meeting transcript"
    event = context.audit_records()[0]
    assert event["request_id"] == "transcript-upload"
    assert event["actor_user_id"] == context.organizer_id
    assert event["event_type"] == "transcript.create"
    assert event["action_id"] == "transcript.create"
    assert event["authorization_decision"] == "allowed"
    assert "Uploaded meeting transcript" not in repr(context.audit_records())


def test_transcript_create_requires_verified_session_and_csrf(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    path = f"/api/meetings/{context.empty_meeting_id}/transcript"
    context.clear_authentication()

    missing_session = context.client.post(path, json={"content": "Transcript"})
    context.authenticate(context.organizer_token)
    missing_csrf = context.client.post(path, json={"content": "Transcript"})

    assert missing_session.status_code == 401
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    assert context.audit_records() == []


def test_participant_and_cross_meeting_bola_transcript_writes_are_denied(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    participant_attempt = context.client.post(
        f"/api/meetings/{context.meeting_id}/transcript",
        json={"content": "Participant overwrite attempt"},
        headers=csrf_headers(context, request_id="participant-transcript-write"),
    )
    bola_attempt = context.client.post(
        f"/api/meetings/{context.other_meeting_id}/transcript",
        json={"content": "Cross-meeting transcript attempt"},
        headers=csrf_headers(context, request_id="bola-transcript-write"),
    )

    assert participant_attempt.status_code == 403
    assert bola_attempt.status_code == 403
    assert participant_attempt.json()["error"]["code"] == (
        "MEETING_ORGANIZER_REQUIRED"
    )
    records = context.audit_records()
    assert [record["request_id"] for record in records] == [
        "participant-transcript-write",
        "bola-transcript-write",
    ]
    assert all(
        record["authorization_decision"] == "denied" for record in records
    )
    assert "overwrite attempt" not in repr(records)
    assert "Cross-meeting transcript" not in repr(records)


def test_duplicate_and_unexpected_identity_input_fail_closed(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)
    path = f"/api/meetings/{context.meeting_id}/transcript"

    duplicate = context.client.post(
        path,
        json={"content": "Do not overwrite"},
        headers=csrf_headers(context, request_id="duplicate-transcript"),
    )
    identity_tamper = context.client.post(
        path,
        json={"content": "Tampered", "user_id": context.outsider_id},
        headers=csrf_headers(context, request_id="identity-tamper-transcript"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "TRANSCRIPT_ALREADY_EXISTS"
    assert identity_tamper.status_code == 422
    persisted = context.client.get(path)
    assert persisted.json()["content"] == "Authorized transcript content"
    records = context.audit_records()
    assert len(records) == 2
    assert records[0]["decision_reason"] == "transcript_already_exists"
    assert records[1]["action_id"] == "transcript.read"


def test_transcript_content_validation_rejects_blank_null_and_oversized_input(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)
    path = f"/api/meetings/{context.empty_meeting_id}/transcript"
    headers = csrf_headers(context, request_id="invalid-transcript")

    responses = (
        context.client.post(path, json={"content": "   "}, headers=headers),
        context.client.post(path, json={"content": "safe\x00unsafe"}, headers=headers),
        context.client.post(path, json={"content": "x" * 200_001}, headers=headers),
    )

    assert [response.status_code for response in responses] == [422, 422, 422]
    assert context.audit_records() == []
