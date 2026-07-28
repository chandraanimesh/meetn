from collections.abc import Iterator, Mapping
from datetime import datetime

import pytest

from app.api.dependencies.services import get_llm_provider
from app.infrastructure.llm.fake_deterministic import FakeDeterministicLLM
from app.main import app
from tests.conftest import MeetingAPITestContext


def assistant_payload(meeting_id: str) -> dict[str, object]:
    return {
        "message": "Open the meeting",
        "page_manifest": {
            "page_id": "meeting_detail",
            "active_meeting_id": meeting_id,
            "visible_meeting_ids": [meeting_id],
        },
    }


@pytest.fixture
def fixed_provider() -> Iterator[tuple[FakeDeterministicLLM, dict[str, object]]]:
    output: dict[str, object] = {
        "intent": "navigate",
        "action_id": "open_meeting_detail",
        "message": "I can open the meeting.",
        "requires_confirmation": False,
        "parameters": {},
    }
    provider = FakeDeterministicLLM(fixed_output=output)
    previous = app.dependency_overrides.get(get_llm_provider)
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        yield provider, output
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_llm_provider, None)
        else:
            app.dependency_overrides[get_llm_provider] = previous


def test_unknown_llm_action_is_denied_and_audited(
    meeting_api_context: MeetingAPITestContext,
    fixed_provider: tuple[FakeDeterministicLLM, dict[str, object]],
) -> None:
    context = meeting_api_context
    _, output = fixed_provider
    output["action_id"] = "run_arbitrary_function"
    context.authenticate(context.organizer_token)

    response = context.client.post(
        "/api/assistant/messages",
        json=assistant_payload(context.meeting_id),
        headers={"X-Request-ID": "unknown-action"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "action_denied"
    assert response.json()["navigation"] is None
    assert "run_arbitrary_function" not in response.text
    event = context.audit_records()[0]
    assert event["request_id"] == "unknown-action"
    assert event["actor_user_id"] == context.organizer_id
    assert event["event_type"] == "assistant_action_rejected"
    assert event["resource_type"] == "assistant_action"
    assert event["resource_id"] == "unresolved"
    assert event["action_id"] is None
    assert event["authorization_decision"] == "denied"
    assert event["decision_reason"] == "action_not_registered"
    assert isinstance(event["created_at"], datetime)


def test_llm_generated_url_fails_closed(
    meeting_api_context: MeetingAPITestContext,
    fixed_provider: tuple[FakeDeterministicLLM, dict[str, object]],
) -> None:
    context = meeting_api_context
    _, output = fixed_provider
    output["action_id"] = "open_meeting_history"
    output["message"] = "Go to https://malicious.example"
    context.authenticate(context.organizer_token)

    response = context.client.post(
        "/api/assistant/messages",
        json=assistant_payload(context.meeting_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "invalid_output"
    assert response.json()["navigation"] is None
    assert "malicious.example" not in response.text


@pytest.mark.parametrize(
    ("extra_location", "extra_value"),
    [
        ("request", {"authenticated_user": {"id": "attacker"}}),
        ("request", {"user_id": "attacker"}),
        ("manifest", {"transcript_content": "must not reach the assistant"}),
        ("manifest", {"confidential_note_content": "must not reach the assistant"}),
        ("manifest", {"is_admin": True}),
        ("manifest", {"has_premium": True}),
    ],
)
def test_untrusted_identity_and_protected_content_fields_are_rejected(
    meeting_api_context: MeetingAPITestContext,
    fixed_provider: tuple[FakeDeterministicLLM, dict[str, object]],
    extra_location: str,
    extra_value: Mapping[str, object],
) -> None:
    context = meeting_api_context
    provider, _ = fixed_provider
    context.authenticate(context.organizer_token)
    request_body = assistant_payload(context.meeting_id)
    if extra_location == "request":
        request_body.update(extra_value)
    else:
        manifest = request_body["page_manifest"]
        assert isinstance(manifest, dict)
        manifest.update(extra_value)

    response = context.client.post(
        "/api/assistant/messages",
        json=request_body,
    )

    assert response.status_code == 422
    assert provider.last_safe_context is None


def test_page_manifest_cannot_grant_cross_meeting_access(
    meeting_api_context: MeetingAPITestContext,
    fixed_provider: tuple[FakeDeterministicLLM, dict[str, object]],
) -> None:
    context = meeting_api_context
    _, output = fixed_provider
    output["parameters"] = {"meeting_id": context.other_meeting_id}
    context.authenticate(context.participant_token)

    response = context.client.post(
        "/api/assistant/messages",
        json=assistant_payload(context.other_meeting_id),
        headers={"X-Request-ID": "changed-meeting-id"},
    )

    assert response.status_code == 403
    assert response.json()["status"] == "access_denied"
    assert response.json()["navigation"] is None
    event = context.audit_records()[0]
    assert event["request_id"] == "changed-meeting-id"
    assert event["actor_user_id"] == context.participant_id
    assert event["action_id"] == "open_meeting_detail"
    assert event["resource_type"] == "meeting"
    assert event["resource_id"] == context.other_meeting_id
    assert event["authorization_decision"] == "denied"
    assert event["decision_reason"] == "not_authorized"


def test_assistant_cannot_return_model_authored_sensitive_content(
    meeting_api_context: MeetingAPITestContext,
    fixed_provider: tuple[FakeDeterministicLLM, dict[str, object]],
) -> None:
    context = meeting_api_context
    _, output = fixed_provider
    output.update(
        {
            "intent": context.note_content,
            "action_id": "open_transcript",
            "message": "Authorized transcript content",
            "parameters": {"meeting_id": context.meeting_id},
        }
    )
    context.authenticate(context.participant_token)

    response = context.client.post(
        "/api/assistant/messages",
        json=assistant_payload(context.meeting_id),
        headers={"X-Request-ID": "sensitive-llm-output"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmation_required"
    assert response.json()["message"] == (
        "Please confirm this action before continuing."
    )
    assert response.json()["intent"] == "navigation"
    assert response.json()["navigation"] is None
    assert "Authorized transcript content" not in response.text
    assert context.note_content not in response.text
    assert "Authorized transcript content" not in repr(context.audit_records())
    assert context.note_content not in repr(context.audit_records())


def test_confirmation_required_response_has_no_effect(
    meeting_api_context: MeetingAPITestContext,
    fixed_provider: tuple[FakeDeterministicLLM, dict[str, object]],
) -> None:
    context = meeting_api_context
    _, output = fixed_provider
    output.update(
        {
            "action_id": "open_membership_plans",
            "requires_confirmation": True,
            "parameters": {},
        }
    )
    context.authenticate(context.organizer_token)

    response = context.client.post(
        "/api/assistant/messages",
        json=assistant_payload(context.meeting_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmation_required"
    assert response.json()["navigation"] is None
    assert response.json()["focus_target"] is None
