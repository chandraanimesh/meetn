import json
import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


MANIFEST_PATTERN = re.compile(
    r'<script id="page-manifest" type="application/json">(.*?)</script>',
    re.DOTALL,
)


@pytest.fixture
def web_client() -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def extract_manifest(page: str) -> dict[str, object]:
    match = MANIFEST_PATTERN.search(page)
    assert match is not None
    value = json.loads(match.group(1))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(
    ("path", "page_id"),
    [
        ("/login", "login"),
        ("/dashboard", "dashboard"),
        ("/meetings", "meeting_history"),
        ("/meetings/meeting-1", "meeting_detail"),
        ("/meetings/meeting-1/transcript", "transcript"),
        (
            "/meetings/meeting-1/confidential-notes",
            "confidential_notes",
        ),
        ("/plans", "membership_plans"),
    ],
)
def test_frontend_pages_embed_versioned_manifest(
    web_client: TestClient,
    path: str,
    page_id: str,
) -> None:
    response = web_client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    manifest = extract_manifest(response.text)
    assert manifest["version"] == 1
    assert manifest["page_id"] == page_id
    assert 'src="/static/js/pages.js?v=1"' in response.text

    if path.startswith("/meetings/meeting-1"):
        assert manifest["active_meeting_id"] == "meeting-1"
        assert manifest["visible_meeting_ids"] == ["meeting-1"]
    else:
        assert manifest["active_meeting_id"] is None


def test_root_redirects_to_dashboard(web_client: TestClient) -> None:
    response = web_client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


def test_login_uses_existing_google_oidc_route_without_copilot(
    web_client: TestClient,
) -> None:
    response = web_client.get("/login")

    assert 'href="/api/v1/auth/google/start"' in response.text
    assert 'id="copilot"' not in response.text
    assert "password" not in response.text.casefold()


def test_authenticated_page_contains_assistant_and_logout_controls(
    web_client: TestClient,
) -> None:
    response = web_client.get("/dashboard")

    assert 'id="copilot"' in response.text
    assert 'id="copilot-form"' in response.text
    assert 'id="logout-button"' in response.text
    assert 'id="session-user"' in response.text


def test_meeting_detail_contains_backend_recording_state_region(
    web_client: TestClient,
) -> None:
    response = web_client.get("/meetings/meeting-1")

    assert 'id="recording-availability-message"' in response.text
    assert 'id="recording-required-plan"' in response.text
    assert 'id="recording-alternative-actions"' in response.text


def test_meeting_history_contains_manual_scheduler_fields(
    web_client: TestClient,
) -> None:
    response = web_client.get("/meetings")

    assert response.status_code == 200
    assert 'id="meeting-form-toggle"' in response.text
    assert 'id="meeting-schedule-form"' in response.text
    assert 'id="schedule-mode"' in response.text
    assert 'value="plan"' in response.text
    assert 'value="reschedule"' in response.text
    assert 'id="schedule-place"' in response.text
    assert 'id="schedule-start-time"' in response.text
    assert 'id="schedule-purpose"' in response.text
    assert 'id="schedule-personal-gift"' in response.text


def test_invalid_meeting_page_identifier_is_rejected(
    web_client: TestClient,
) -> None:
    response = web_client.get("/meetings/not%20safe")

    assert response.status_code == 422


def test_frontend_assets_are_served(web_client: TestClient) -> None:
    css_response = web_client.get("/static/css/app.css")
    api_response = web_client.get("/static/js/api.js")
    copilot_response = web_client.get("/static/js/copilot.js")
    theme_response = web_client.get("/static/js/theme.js")

    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert api_response.status_code == 200
    assert "javascript" in api_response.headers["content-type"]
    assert copilot_response.status_code == 200
    assert theme_response.status_code == 200


def test_api_client_uses_cookie_credentials_and_safe_error_boundaries(
    web_client: TestClient,
) -> None:
    source = web_client.get("/static/js/api.js").text

    assert 'credentials: "include"' in source
    assert "response.status === 401" in source
    assert "window.location.assign(`/login?next=" in source
    assert "response.status === 403" in source
    assert "You do not have permission" in source
    assert 'headers.set("X-CSRF-Token", csrfToken)' in source
    assert 'apiPath === "/api/v1/session"' in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source


def test_navigation_executes_only_allowlisted_backend_directives(
    web_client: TestClient,
) -> None:
    navigation = web_client.get("/static/js/navigation.js").text
    copilot = web_client.get("/static/js/copilot.js").text

    assert "KNOWN_PATHS" in navigation
    assert "url.origin !== window.location.origin" in navigation
    assert 'navigation.method !== "GET"' in navigation
    assert "followApprovedNavigation(result.navigation)" in copilot
    assert "renderAssistantResult(result, { autoExecute: true })" in copilot
    assert "confirmationSatisfied: execution.confirmationSatisfied === true" in copilot
    assert "!isKnownNavigationPath(navigation.path)" in navigation
    assert "focusApprovedTarget(result.focus_target)" in copilot
    assert "window.open" not in navigation
    assert "eval(" not in navigation
    assert "CONFIRMATION_REQUIRED_PATHS" in navigation
    assert 'window.confirm("Continue to this page?")' in navigation


def test_recording_alternatives_require_backend_ids_and_confirmation(
    web_client: TestClient,
) -> None:
    pages = web_client.get("/static/js/pages.js").text
    navigation = web_client.get("/static/js/navigation.js").text

    assert "/recording-availability" in pages
    assert "allowed_alternative_action_ids" in pages
    assert "followApprovedAlternativeAction(actionId, meetingId)" in pages
    assert "open_transcript" in navigation
    assert "open_membership_plans" in navigation
    assert "window.confirm" in navigation


def test_copilot_uses_structured_endpoint_and_confirmation_buttons(
    web_client: TestClient,
) -> None:
    source = web_client.get("/static/js/copilot.js").text

    assert 'apiFetch("/api/assistant/messages"' in source
    assert 'apiFetch("/api/assistant/actions/confirm"' in source
    assert "getAssistantPageManifest()" in source
    assert "result.requires_confirmation === true" in source
    assert 'addActionButton(container, "Confirm"' in source
    assert "textContent" in source
    assert "innerHTML" not in source


def test_transcript_page_supports_safe_text_paste_and_file_upload(
    web_client: TestClient,
) -> None:
    page = web_client.get("/meetings/meeting-1/transcript").text
    source = web_client.get("/static/js/pages.js").text

    assert 'id="transcript-upload-panel"' in page
    assert 'id="transcript-upload-form"' in page
    assert 'id="transcript-input"' in page
    assert 'maxlength="200000"' in page
    assert 'accept=".txt,text/plain"' in page
    assert 'method: "POST"' in source
    assert "JSON.stringify({ content: transcriptText })" in source
    assert "await file.text()" in source
    assert "MAX_TRANSCRIPT_CHARACTERS" in source
    assert "meeting.organizer_id === session.user.id" in source
    assert '"user_id"' not in source
    assert 'data-assistant-option="open_transcript_upload"' in page


def test_settings_dropdown_and_assistant_theme_use_closed_safe_values(
    web_client: TestClient,
) -> None:
    page = web_client.get("/dashboard").text
    theme = web_client.get("/static/js/theme.js").text
    copilot = web_client.get("/static/js/copilot.js").text
    css = web_client.get("/static/css/app.css").text

    assert 'src="/static/js/theme.js?v=1"' in page
    assert 'id="theme-select"' in page
    for value in ("system", "light", "dark", "soothing", "happy"):
        assert f'<option value="{value}">' in page
        assert f'"{value}"' in theme
    assert "const ALLOWED_THEMES = new Set([" in theme
    assert "!ALLOWED_THEMES.has(presentation.theme)" in theme
    assert "window.localStorage.setItem(THEME_STORAGE_KEY, theme)" in theme
    assert "app_session" not in theme
    assert "Authorization" not in theme
    assert "transcript" not in theme.casefold()
    assert 'import { applyAssistantPresentation } from "./theme.js"' in copilot
    assert "applyAssistantPresentation(result.presentation)" in copilot
    assert ':root[data-theme="dark"]' in css
    assert ':root[data-theme="soothing"]' in css
    assert ':root[data-theme="happy"]' in css


def test_copilot_voice_input_reuses_safe_text_message_flow(
    web_client: TestClient,
) -> None:
    page = web_client.get("/dashboard").text
    source = web_client.get("/static/js/copilot.js").text

    assert 'id="copilot-voice-button"' in page
    assert 'type="button" aria-label="Speak your assistant request"' in page
    assert 'aria-pressed="false"' in page
    assert 'id="copilot-voice-status"' in page
    assert 'aria-live="polite"' in page
    assert "browser's speech service" in page
    assert "window.SpeechRecognition || window.webkitSpeechRecognition" in source
    assert "speechRecognition.continuous = false" in source
    assert "speechRecognition.interimResults = false" in source
    assert 'voiceButton.addEventListener("click"' in source
    assert "void sendMessage(transcript)" in source
    assert 'window.addEventListener("pagehide"' in source
    assert "speechRecognition.abort()" in source
    assert 'errorCode === "not-allowed"' in source
    assert "transcript.length > 2000" in source
    assert "MediaRecorder" not in source
    assert "navigator.mediaDevices" not in source
    assert "FormData" not in source
    assert "localStorage" not in source
    assert "setPresentationTheme" not in source


def test_copilot_has_clickable_meeting_scheduling_options(
    web_client: TestClient,
) -> None:
    page = web_client.get("/dashboard").text
    source = web_client.get("/static/js/copilot.js").text

    assert 'data-assistant-option="create_meeting"' in page
    assert 'data-assistant-option="reschedule_meeting"' in page
    assert 'data-assistant-option="open_meeting_history"' in page
    assert 'option === "create_meeting"' in source
    assert 'option === "reschedule_meeting"' in source
    assert "getAssistantPageManifest()" in source


def test_copilot_offers_accessible_navigation_without_removing_actions(
    web_client: TestClient,
) -> None:
    page = web_client.get("/dashboard").text
    source = web_client.get("/static/js/copilot.js").text

    assert "Where would you like to go?" in page
    for action_id in (
        "open_dashboard",
        "open_meeting_history",
        "open_meeting_detail",
        "open_transcript",
        "open_transcript_upload",
        "open_confidential_notes",
        "open_membership_plans",
        "focus_meeting_search",
        "create_meeting",
        "reschedule_meeting",
    ):
        assert f'data-assistant-option="{action_id}"' in page

    assert "Where would you like to go? Choose an option" in source
    assert '["open_dashboard", "Open my dashboard"]' in source
    assert 'button.dataset.requiresMeeting === "true"' in source
    assert 'button.dataset.contextUnavailable = "true"' in source
    assert "!panel.hidden" in source


def test_confirmed_navigation_auto_follows_only_after_backend_confirmation(
    web_client: TestClient,
) -> None:
    source = web_client.get("/static/js/copilot.js").text
    navigation = web_client.get("/static/js/navigation.js").text

    assert 'apiFetch("/api/assistant/actions/confirm"' in source
    assert "confirmationSatisfied: true" in source
    assert "options.confirmationSatisfied === true" in navigation
    assert "!confirmationSatisfied" in navigation
    assert "!confirmSensitiveNavigation(navigation.path)" in navigation


def test_manual_scheduler_calls_only_scoped_backend_write_endpoints(
    web_client: TestClient,
) -> None:
    source = web_client.get("/static/js/pages.js").text

    assert 'method: rescheduling ? "PATCH" : "POST"' in source
    assert '"/api/meetings"' in source
    assert "/schedule`" in source
    assert "requestBody.user_id" not in source
    assert '"user_id":' not in source
    assert 'scheduled: "Planned to meet"' in source
    assert 'rescheduled: "Rescheduled"' in source


def test_frontend_does_not_store_tokens_or_protected_content(
    web_client: TestClient,
) -> None:
    sources = "\n".join(
        web_client.get(path).text
        for path in (
            "/static/js/api.js",
            "/static/js/manifest.js",
            "/static/js/navigation.js",
            "/static/js/pages.js",
            "/static/js/copilot.js",
        )
    )

    assert "localStorage" not in sources
    assert "sessionStorage" not in sources
    assert "document.cookie" not in sources
    assert "Authorization" not in sources
    assert "innerHTML" not in sources
