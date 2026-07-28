from tests.conftest import MeetingAPITestContext


def test_existing_cross_user_resources_return_403_without_content(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.outsider_token)

    responses = (
        context.client.get(f"/api/meetings/{context.meeting_id}"),
        context.client.get(f"/api/meetings/{context.meeting_id}/transcript"),
        context.client.get(
            f"/api/meetings/{context.meeting_id}/confidential-notes",
            headers={"X-Request-ID": "denied-notes"},
        ),
    )

    assert [response.status_code for response in responses] == [403, 403, 403]
    response_text = " ".join(response.text for response in responses)
    assert "Authorized transcript content" not in response_text
    assert context.note_content not in response_text

    event = next(
        event
        for event in context.audit_records()
        if event["request_id"] == "denied-notes"
    )
    assert event["request_id"] == "denied-notes"
    assert event["actor_user_id"] == context.outsider_id
    assert event["action_id"] == "confidential_notes.read"
    assert event["resource_type"] == "confidential_note_collection"
    assert event["resource_id"] == context.meeting_id
    assert event["authorization_decision"] == "denied"
    assert event["decision_reason"] == "not_authorized"


def test_user_id_query_parameter_cannot_override_verified_jwt_identity(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.outsider_token)

    list_response = context.client.get(
        "/api/me/meetings", params={"user_id": context.organizer_id}
    )
    detail_response = context.client.get(
        f"/api/meetings/{context.meeting_id}",
        params={"user_id": context.organizer_id},
    )
    transcript_response = context.client.get(
        f"/api/meetings/{context.meeting_id}/transcript",
        params={"user_id": context.organizer_id},
    )

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [
        context.other_meeting_id
    ]
    assert detail_response.status_code == 403
    assert transcript_response.status_code == 403

    openapi = context.client.get("/openapi.json").json()
    for path in (
        "/api/me/meetings",
        "/api/meetings/{id}",
        "/api/meetings/{id}/transcript",
        "/api/meetings/{id}/confidential-notes",
    ):
        parameters = openapi["paths"][path]["get"].get("parameters", [])
        assert "user_id" not in {parameter["name"] for parameter in parameters}


def test_participant_cannot_read_another_users_meeting_by_id(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    detail_response = context.client.get(
        f"/api/meetings/{context.other_meeting_id}"
    )
    transcript_response = context.client.get(
        f"/api/meetings/{context.other_meeting_id}/transcript"
    )

    assert detail_response.status_code == 403
    assert transcript_response.status_code == 403
    assert "Other user's transcript content" not in transcript_response.text
    records = context.audit_records()
    assert [record["resource_id"] for record in records] == [
        context.other_meeting_id,
        context.other_meeting_id,
    ]
    assert [record["authorization_decision"] for record in records] == [
        "denied",
        "denied",
    ]


def test_missing_transcript_returns_404_even_for_unrelated_user(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.outsider_token)

    response = context.client.get(
        f"/api/meetings/{context.empty_meeting_id}/transcript"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_tampered_session_cookie_is_rejected_before_resource_lookup(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate("tampered.jwt.value")

    response = context.client.get(f"/api/meetings/{context.meeting_id}")

    assert response.status_code == 401
