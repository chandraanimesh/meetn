import pytest
from pydantic import ValidationError

from app.agent.action_models import (
    AgentDecision,
    PresentationDirective,
    PresentationTheme,
)
from app.agent.action_registry import (
    ActionEffect,
    ActionPermission,
    BackendActionRegistry,
    InvalidActionParameters,
    MissingActionParameters,
)


EXPECTED_ACTION_IDS = frozenset(
    {
        "open_dashboard",
        "open_meeting_history",
        "open_meeting_detail",
        "open_transcript",
        "open_transcript_upload",
        "open_confidential_notes",
        "open_membership_plans",
        "focus_meeting_search",
        "activate_soothing_theme",
        "activate_happy_theme",
        "activate_dark_theme",
        "activate_light_theme",
        "activate_system_theme",
        "create_meeting",
        "reschedule_meeting",
    }
)


def test_registry_contains_only_prototype_actions() -> None:
    registry = BackendActionRegistry()

    assert registry.action_ids == EXPECTED_ACTION_IDS
    assert registry.resolve("not_registered") is None


@pytest.mark.parametrize(
    ("action_id", "theme", "reason"),
    [
        (
            "activate_soothing_theme",
            PresentationTheme.SOOTHING,
            "stress_detected",
        ),
        (
            "activate_happy_theme",
            PresentationTheme.HAPPY,
            "positive_mood_detected",
        ),
        (
            "activate_dark_theme",
            PresentationTheme.DARK,
            "dark_theme_requested",
        ),
        (
            "activate_light_theme",
            PresentationTheme.LIGHT,
            "light_theme_requested",
        ),
        (
            "activate_system_theme",
            PresentationTheme.SYSTEM,
            "system_theme_requested",
        ),
    ],
)
def test_theme_actions_are_authenticated_closed_presentation_actions(
    action_id: str,
    theme: PresentationTheme,
    reason: str,
) -> None:
    action = BackendActionRegistry().resolve(action_id)

    assert action is not None
    assert action.permission is ActionPermission.AUTHENTICATED
    assert action.effect is ActionEffect.PRESENTATION
    assert action.presentation_theme is theme
    assert action.presentation_reason == reason
    assert action.validate_parameters({}) == {}
    with pytest.raises(InvalidActionParameters):
        action.validate_parameters({"theme": theme.value})


def test_registry_validates_required_and_extra_parameters() -> None:
    action = BackendActionRegistry().resolve("open_transcript")
    assert action is not None

    with pytest.raises(MissingActionParameters):
        action.validate_parameters({})
    with pytest.raises(InvalidActionParameters):
        action.validate_parameters({"meeting_id": "meeting-1", "url": "malicious"})

    parameters = action.validate_parameters({"meeting_id": "meeting-1"})
    assert parameters == {"meeting_id": "meeting-1"}
    assert action.render_navigation(parameters) == "/meetings/meeting-1/transcript"


@pytest.mark.parametrize(
    "field_override",
    [
        {"message": "Open https://example.invalid"},
        {"message": "Open /meetings directly"},
        {"action_id": "https://example.invalid"},
        {"parameters": {"url": "https://example.invalid"}},
        {"parameters": {"meeting_id": "https://example.invalid"}},
    ],
)
def test_llm_output_schema_rejects_urls(
    field_override: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "intent": "navigate",
        "action_id": "open_meeting_history",
        "message": "Opening meeting history.",
        "requires_confirmation": False,
        "parameters": {},
    }
    payload.update(field_override)

    with pytest.raises(ValidationError):
        AgentDecision.model_validate(payload)


def test_llm_output_schema_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AgentDecision.model_validate(
            {
                "intent": "navigate",
                "action_id": "open_meeting_history",
                "message": "Opening meeting history.",
                "requires_confirmation": False,
                "parameters": {},
                "url": "/meetings",
            }
        )

    with pytest.raises(ValidationError):
        AgentDecision.model_validate(
            {
                "intent": "presentation",
                "action_id": "activate_soothing_theme",
                "message": "Changing theme.",
                "requires_confirmation": False,
                "parameters": {},
                "presentation": {"theme": "attacker-controlled"},
            }
        )

    with pytest.raises(ValidationError):
        PresentationDirective.model_validate(
            {"theme": "attacker-controlled", "reason": "model_claim"}
        )


def test_llm_descriptors_do_not_expose_backend_paths() -> None:
    descriptors = BackendActionRegistry().llm_descriptors()

    assert descriptors
    assert all("path" not in descriptor for descriptor in descriptors)
    assert all("navigation_template" not in descriptor for descriptor in descriptors)

    create_descriptor = next(
        descriptor
        for descriptor in descriptors
        if descriptor["action_id"] == "create_meeting"
    )
    parameter_names = create_descriptor["parameter_names"]
    assert isinstance(parameter_names, tuple)
    assert "personal_gift" in parameter_names
    assert create_descriptor["confirmation_required"] is True


def test_meeting_mutation_parameters_are_strict_and_timezone_aware() -> None:
    action = BackendActionRegistry().resolve("create_meeting")
    assert action is not None
    valid: dict[str, str | int | bool] = {
        "title": "Planning",
        "place": "Conference room",
        "purpose": "Quarterly plan",
        "start_time": "2026-08-01T10:00:00+05:30",
        "duration_minutes": 60,
        "personal_gift": "Coffee",
    }

    assert action.validate_parameters(valid) == valid
    with pytest.raises(InvalidActionParameters):
        action.validate_parameters({**valid, "start_time": "2026-08-01T10:00"})
    with pytest.raises(InvalidActionParameters):
        action.validate_parameters({**valid, "user_id": "someone-else"})
