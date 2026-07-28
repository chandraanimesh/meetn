from collections.abc import Callable, Iterator, Mapping

import pytest

from app.api.dependencies.services import get_llm_provider
from app.infrastructure.llm.fake_deterministic import FakeDeterministicLLM
from app.main import app
from tests.conftest import MeetingAPITestContext


@pytest.fixture
def set_assistant_output() -> Iterator[
    Callable[[Mapping[str, object]], FakeDeterministicLLM]
]:
    previous = app.dependency_overrides.get(get_llm_provider)

    def configure(output: Mapping[str, object]) -> FakeDeterministicLLM:
        provider = FakeDeterministicLLM(fixed_output=output)
        app.dependency_overrides[get_llm_provider] = lambda: provider
        return provider

    try:
        yield configure
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_llm_provider, None)
        else:
            app.dependency_overrides[get_llm_provider] = previous


def payload(
    message: str,
    *,
    meeting_id: str | None,
) -> dict[str, object]:
    return {
        "message": message,
        "page_manifest": {
            "page_id": "meeting_detail" if meeting_id else "dashboard",
            "active_meeting_id": meeting_id,
            "visible_meeting_ids": [meeting_id] if meeting_id else [],
        },
    }


def llm_output(
    action_id: str,
    *,
    meeting_id: str | None = None,
) -> dict[str, object]:
    return {
        "intent": "navigate",
        "action_id": action_id,
        "message": "I can open that page.",
        "requires_confirmation": False,
        "parameters": {"meeting_id": meeting_id} if meeting_id else {},
    }


def csrf_headers(
    context: MeetingAPITestContext,
    *,
    request_id: str,
) -> dict[str, str]:
    response = context.client.get("/api/v1/session")
    assert response.status_code == 200
    return {
        "X-CSRF-Token": response.json()["csrf_token"],
        "X-Request-ID": request_id,
    }


def test_assistant_endpoint_requires_verified_jwt(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.clear_authentication()

    response = context.client.post(
        "/api/assistant/messages",
        json=payload("Show history", meeting_id=None),
    )

    assert response.status_code == 401


def test_assistant_dashboard_navigation_comes_from_backend_registry(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    set_assistant_output(llm_output("open_dashboard"))

    response = context.client.post(
        "/api/assistant/messages",
        json=payload("Take me to my dashboard", meeting_id=None),
        headers={"X-Request-ID": "assistant-dashboard"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["action_id"] == "open_dashboard"
    assert response.json()["navigation"] == {
        "path": "/dashboard",
        "method": "GET",
    }
    event = context.audit_events()[0]
    assert event["request_id"] == "assistant-dashboard"
    assert event["decision_reason"] == "authenticated"


def test_stress_message_returns_only_backend_allowlisted_soothing_theme(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    provider = set_assistant_output(llm_output("open_dashboard"))

    response = context.client.post(
        "/api/assistant/messages",
        json=payload("I m feeling stressed", meeting_id=None),
        headers={"X-Request-ID": "assistant-soothing-theme"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["action_id"] == "activate_soothing_theme"
    assert body["navigation"] is None
    assert body["presentation"] == {
        "theme": "soothing",
        "reason": "stress_detected",
    }
    assert provider.last_safe_context is None
    event = context.audit_records()[0]
    assert event["request_id"] == "assistant-soothing-theme"
    assert event["action_id"] == "activate_soothing_theme"
    assert event["authorization_decision"] == "allowed"


@pytest.mark.parametrize(
    ("message", "action_id", "theme", "reason"),
    [
        (
            "i m feeling happy",
            "activate_happy_theme",
            "happy",
            "positive_mood_detected",
        ),
        (
            "my eyes are stressed",
            "activate_dark_theme",
            "dark",
            "dark_theme_requested",
        ),
        (
            "turn to dark mode",
            "activate_dark_theme",
            "dark",
            "dark_theme_requested",
        ),
        (
            "switch to light mode",
            "activate_light_theme",
            "light",
            "light_theme_requested",
        ),
        (
            "follow my system theme",
            "activate_system_theme",
            "system",
            "system_theme_requested",
        ),
    ],
)
def test_presentation_message_returns_only_backend_allowlisted_theme(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
    message: str,
    action_id: str,
    theme: str,
    reason: str,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    provider = set_assistant_output(llm_output("open_dashboard"))
    request_id = f"assistant-{theme}-theme"

    response = context.client.post(
        "/api/assistant/messages",
        json=payload(message, meeting_id=None),
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["action_id"] == action_id
    assert body["navigation"] is None
    assert body["focus_target"] is None
    assert body["presentation"] == {"theme": theme, "reason": reason}
    assert provider.last_safe_context is None
    event = context.audit_records()[0]
    assert event["request_id"] == request_id
    assert event["action_id"] == action_id
    assert event["authorization_decision"] == "allowed"


def test_participant_confirms_backend_transcript_navigation(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    set_assistant_output(llm_output("open_transcript", meeting_id=context.meeting_id))

    response = context.client.post(
        "/api/assistant/messages",
        json=payload("Open transcript", meeting_id=context.meeting_id),
        headers={"X-Request-ID": "assistant-transcript"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmation_required"
    assert body["action_id"] == "open_transcript"
    assert body["navigation"] is None
    assert body["requires_confirmation"] is True

    confirmed = context.client.post(
        "/api/assistant/actions/confirm",
        json={
            "action_id": body["action_id"],
            "parameters": body["parameters"],
        },
        headers=csrf_headers(context, request_id="assistant-transcript-confirm"),
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "success"
    assert confirmed.json()["navigation"] == {
        "path": f"/meetings/{context.meeting_id}/transcript",
        "method": "GET",
    }
    assert "Authorized transcript content" not in confirmed.text
    assert context.note_content not in confirmed.text

    event = context.audit_events()[0]
    assert event["request_id"] == "assistant-transcript"
    assert event["event_type"] == "assistant_action_pending_confirmation"
    assert event["resource_type"] == "transcript"
    assert event["resource_id"] == context.meeting_id
    assert event["authorization_decision"] == "allowed"


def test_organizer_confirms_transcript_upload_page_navigation(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)
    set_assistant_output(
        llm_output(
            "open_transcript_upload",
            meeting_id=context.empty_meeting_id,
        )
    )

    proposed = context.client.post(
        "/api/assistant/messages",
        json=payload("Add transcript", meeting_id=context.empty_meeting_id),
        headers={"X-Request-ID": "assistant-transcript-upload"},
    )
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "confirmation_required"

    confirmed = context.client.post(
        "/api/assistant/actions/confirm",
        json={
            "action_id": proposed.json()["action_id"],
            "parameters": proposed.json()["parameters"],
        },
        headers=csrf_headers(
            context,
            request_id="assistant-transcript-upload-confirm",
        ),
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "success"
    assert confirmed.json()["navigation"] == {
        "path": f"/meetings/{context.empty_meeting_id}/transcript",
        "method": "GET",
    }
    assert "transcript" not in repr(confirmed.json()["parameters"]).casefold()


def test_assistant_meeting_creation_requires_csrf_and_executes_after_confirmation(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    parameters = {
        "title": "LLM Planning",
        "place": "Studio",
        "purpose": "Plan the launch",
        "start_time": "2026-08-01T10:00:00+05:30",
        "duration_minutes": 60,
        "personal_gift": "Coffee beans",
    }
    set_assistant_output(
        {
            "intent": "create_meeting",
            "action_id": "create_meeting",
            "message": "Model-provided text is not trusted.",
            "requires_confirmation": False,
            "parameters": parameters,
        }
    )

    proposed = context.client.post(
        "/api/assistant/messages",
        json=payload("Plan a meeting", meeting_id=None),
    )
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "confirmation_required"
    assert proposed.json()["navigation"] is None

    without_csrf = context.client.post(
        "/api/assistant/actions/confirm",
        json={"action_id": "create_meeting", "parameters": parameters},
    )
    assert without_csrf.status_code == 403
    assert without_csrf.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"

    confirmed = context.client.post(
        "/api/assistant/actions/confirm",
        json={"action_id": "create_meeting", "parameters": parameters},
        headers=csrf_headers(context, request_id="assistant-create"),
    )

    assert confirmed.status_code == 200
    result = confirmed.json()
    assert result["status"] == "success"
    assert result["action_id"] == "create_meeting"
    assert result["navigation"]["path"].startswith("/meetings/")
    assert "Model-provided text" not in confirmed.text


def test_confirmed_assistant_action_rejects_tampered_identity_parameter(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    parameters = {
        "title": "Tampered",
        "place": "Studio",
        "purpose": "Attempt scope bypass",
        "start_time": "2026-08-01T10:00:00+05:30",
        "duration_minutes": 60,
        "user_id": context.organizer_id,
    }

    response = context.client.post(
        "/api/assistant/actions/confirm",
        json={"action_id": "create_meeting", "parameters": parameters},
        headers=csrf_headers(context, request_id="assistant-tamper"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "action_denied"
    assert response.json()["navigation"] is None


def test_confirmed_assistant_reschedule_denies_participant_bola_attempt(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)

    response = context.client.post(
        "/api/assistant/actions/confirm",
        json={
            "action_id": "reschedule_meeting",
            "parameters": {
                "meeting_id": context.meeting_id,
                "start_time": "2026-08-03T10:00:00+05:30",
                "duration_minutes": 60,
            },
        },
        headers=csrf_headers(context, request_id="assistant-reschedule-bola"),
    )

    assert response.status_code == 403
    assert response.json()["status"] == "access_denied"
    assert response.json()["navigation"] is None
    assert context.audit_records()[0]["decision_reason"] == "not_authorized"


def test_confirm_endpoint_denies_invented_action_before_resource_lookup(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(context.organizer_token)

    response = context.client.post(
        "/api/assistant/actions/confirm",
        json={
            "action_id": "invented_meeting_writer",
            "parameters": {"meeting_id": context.meeting_id},
        },
        headers=csrf_headers(context, request_id="assistant-invented"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "action_denied"
    assert response.json()["navigation"] is None
    event = context.audit_records()[0]
    assert event["decision_reason"] == "action_not_registered"
    assert event["action_id"] is None


def test_missing_meeting_parameter_returns_clarification(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    context.authenticate(context.participant_token)
    set_assistant_output(llm_output("open_meeting_detail"))

    response = context.client.post(
        "/api/assistant/messages",
        json=payload("Open meeting", meeting_id=None),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "clarification_required"
    assert response.json()["navigation"] is None


def test_confidential_navigation_uses_backend_note_grant(
    meeting_api_context: MeetingAPITestContext,
    set_assistant_output: Callable[[Mapping[str, object]], FakeDeterministicLLM],
) -> None:
    context = meeting_api_context
    set_assistant_output(
        llm_output("open_confidential_notes", meeting_id=context.meeting_id)
    )
    request_body = payload("Open notes", meeting_id=context.meeting_id)

    context.authenticate(context.participant_token)
    denied = context.client.post("/api/assistant/messages", json=request_body)

    context.authenticate(context.granted_user_token)
    allowed = context.client.post("/api/assistant/messages", json=request_body)

    assert denied.status_code == 403
    assert denied.json()["status"] == "access_denied"
    assert denied.json()["navigation"] is None
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "success"
    assert allowed.json()["navigation"]["path"].endswith("/confidential-notes")
    assert context.note_content not in allowed.text
