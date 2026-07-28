from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.application.dto.meeting_scheduling import normalize_start_time
from app.agent.action_models import PresentationTheme


class ActionPermission(str, Enum):
    AUTHENTICATED = "authenticated"
    MEETING = "meeting"
    TRANSCRIPT = "transcript"
    CONFIDENTIAL_NOTES = "confidential_notes"
    MEETING_ORGANIZER = "meeting_organizer"


class ActionEffect(str, Enum):
    NAVIGATION = "navigation"
    FOCUS = "focus"
    MUTATION = "mutation"
    PRESENTATION = "presentation"


class EmptyParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MeetingParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    meeting_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )


def _validate_iso_start_time(value: str) -> str:
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        normalize_start_time(parsed)
    except ValueError as exc:
        raise ValueError(
            "start_time must be an ISO 8601 timestamp with timezone"
        ) from exc
    return normalized


class MeetingCreateParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=160)
    place: str = Field(min_length=1, max_length=255)
    purpose: str = Field(min_length=1, max_length=1_000)
    start_time: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(ge=15, le=480)
    personal_gift: str = Field(default="", max_length=255)

    @field_validator("title", "place", "purpose")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Meeting text fields cannot be blank")
        return normalized

    @field_validator("personal_gift")
    @classmethod
    def normalize_personal_gift(cls, value: str) -> str:
        return value.strip()

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, value: str) -> str:
        return _validate_iso_start_time(value)


class MeetingRescheduleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    meeting_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    start_time: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(ge=15, le=480)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    place: str | None = Field(default=None, min_length=1, max_length=255)
    purpose: str | None = Field(default=None, min_length=1, max_length=1_000)
    personal_gift: str | None = Field(default=None, max_length=255)

    @field_validator("title", "place", "purpose")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Meeting text fields cannot be blank")
        return normalized

    @field_validator("personal_gift")
    @classmethod
    def normalize_optional_gift(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, value: str) -> str:
        return _validate_iso_start_time(value)


class MissingActionParameters(ValueError):
    def __init__(self, parameter_names: tuple[str, ...]) -> None:
        self.parameter_names = parameter_names
        super().__init__("Required action parameters are missing")


class InvalidActionParameters(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredAction:
    action_id: str
    description: str
    permission: ActionPermission
    effect: ActionEffect
    parameter_model: type[BaseModel]
    navigation_template: str | None = None
    focus_target: str | None = None
    presentation_theme: PresentationTheme | None = None
    presentation_reason: str | None = None
    confirmation_required: bool = False
    clarification_message: str = "Please provide the required action details."

    def validate_parameters(
        self, raw_parameters: dict[str, str | int | bool]
    ) -> dict[str, str | int | bool]:
        try:
            validated = self.parameter_model.model_validate(raw_parameters)
        except ValidationError as exc:
            missing = tuple(
                str(error["loc"][0])
                for error in exc.errors()
                if error["type"] == "missing"
            )
            if missing:
                raise MissingActionParameters(missing) from exc
            raise InvalidActionParameters("Action parameters are invalid") from exc
        return validated.model_dump(exclude_none=True)

    def render_navigation(self, parameters: dict[str, str | int | bool]) -> str | None:
        if self.navigation_template is None:
            return None
        return self.navigation_template.format_map(parameters)

    def llm_descriptor(self) -> dict[str, object]:
        schema = self.parameter_model.model_json_schema()
        required_parameters = tuple(schema.get("required", ()))
        raw_properties = schema.get("properties", {})
        parameter_names = tuple(
            sorted(raw_properties) if isinstance(raw_properties, dict) else ()
        )
        return {
            "action_id": self.action_id,
            "description": self.description,
            "required_parameters": required_parameters,
            "parameter_names": parameter_names,
            "confirmation_required": self.confirmation_required,
        }


PROTOTYPE_ACTIONS = (
    RegisteredAction(
        action_id="open_dashboard",
        description="Open the authenticated user's dashboard.",
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.NAVIGATION,
        parameter_model=EmptyParameters,
        navigation_template="/dashboard",
    ),
    RegisteredAction(
        action_id="open_meeting_history",
        description="Open the authenticated user's meeting history.",
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.NAVIGATION,
        parameter_model=EmptyParameters,
        navigation_template="/meetings",
    ),
    RegisteredAction(
        action_id="open_meeting_detail",
        description="Open one meeting's detail page.",
        permission=ActionPermission.MEETING,
        effect=ActionEffect.NAVIGATION,
        parameter_model=MeetingParameters,
        navigation_template="/meetings/{meeting_id}",
        clarification_message="Which meeting should I use?",
    ),
    RegisteredAction(
        action_id="open_transcript",
        description="Open an authorized meeting transcript page.",
        permission=ActionPermission.TRANSCRIPT,
        effect=ActionEffect.NAVIGATION,
        parameter_model=MeetingParameters,
        navigation_template="/meetings/{meeting_id}/transcript",
        confirmation_required=True,
        clarification_message="Which meeting transcript should I open?",
    ),
    RegisteredAction(
        action_id="open_transcript_upload",
        description="Open the organizer-only transcript upload page for a meeting.",
        permission=ActionPermission.MEETING_ORGANIZER,
        effect=ActionEffect.NAVIGATION,
        parameter_model=MeetingParameters,
        navigation_template="/meetings/{meeting_id}/transcript",
        confirmation_required=True,
        clarification_message="Which meeting transcript should I add?",
    ),
    RegisteredAction(
        action_id="open_confidential_notes",
        description="Open an authorized meeting confidential-notes page.",
        permission=ActionPermission.CONFIDENTIAL_NOTES,
        effect=ActionEffect.NAVIGATION,
        parameter_model=MeetingParameters,
        navigation_template="/meetings/{meeting_id}/confidential-notes",
        clarification_message="Which meeting's confidential notes should I open?",
    ),
    RegisteredAction(
        action_id="open_membership_plans",
        description="Open the membership plans page.",
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.NAVIGATION,
        parameter_model=EmptyParameters,
        navigation_template="/plans",
        confirmation_required=True,
    ),
    RegisteredAction(
        action_id="focus_meeting_search",
        description="Focus the meeting-search control on the current page.",
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.FOCUS,
        parameter_model=EmptyParameters,
        focus_target="meeting_search",
    ),
    RegisteredAction(
        action_id="activate_soothing_theme",
        description=(
            "Use a calmer presentation when the user says they feel stressed, "
            "anxious, or overwhelmed."
        ),
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.PRESENTATION,
        parameter_model=EmptyParameters,
        presentation_theme=PresentationTheme.SOOTHING,
        presentation_reason="stress_detected",
    ),
    RegisteredAction(
        action_id="activate_happy_theme",
        description=(
            "Use a warm, cheerful presentation when the user says they feel "
            "happy, joyful, or positive."
        ),
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.PRESENTATION,
        parameter_model=EmptyParameters,
        presentation_theme=PresentationTheme.HAPPY,
        presentation_reason="positive_mood_detected",
    ),
    RegisteredAction(
        action_id="activate_dark_theme",
        description=(
            "Use dark mode when the user requests it or describes eye strain."
        ),
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.PRESENTATION,
        parameter_model=EmptyParameters,
        presentation_theme=PresentationTheme.DARK,
        presentation_reason="dark_theme_requested",
    ),
    RegisteredAction(
        action_id="activate_light_theme",
        description="Use light mode when the user explicitly requests it.",
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.PRESENTATION,
        parameter_model=EmptyParameters,
        presentation_theme=PresentationTheme.LIGHT,
        presentation_reason="light_theme_requested",
    ),
    RegisteredAction(
        action_id="activate_system_theme",
        description=(
            "Follow the device color-scheme preference when the user requests "
            "the system theme."
        ),
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.PRESENTATION,
        parameter_model=EmptyParameters,
        presentation_theme=PresentationTheme.SYSTEM,
        presentation_reason="system_theme_requested",
    ),
    RegisteredAction(
        action_id="create_meeting",
        description=(
            "Plan a meeting using title, place, purpose, ISO start_time with "
            "timezone, duration_minutes, and optional personal_gift."
        ),
        permission=ActionPermission.AUTHENTICATED,
        effect=ActionEffect.MUTATION,
        parameter_model=MeetingCreateParameters,
        confirmation_required=True,
        clarification_message=(
            "Please provide a title, place, purpose, start time with timezone, "
            "duration in minutes, and any optional personal gift."
        ),
    ),
    RegisteredAction(
        action_id="reschedule_meeting",
        description=(
            "Reschedule an existing meeting using meeting_id, ISO start_time "
            "with timezone, duration_minutes, and optional updated details."
        ),
        permission=ActionPermission.MEETING_ORGANIZER,
        effect=ActionEffect.MUTATION,
        parameter_model=MeetingRescheduleParameters,
        confirmation_required=True,
        clarification_message=(
            "Please provide the meeting, new start time with timezone, and "
            "duration in minutes."
        ),
    ),
)


class BackendActionRegistry:
    EXPECTED_ACTION_IDS: ClassVar[frozenset[str]] = frozenset(
        action.action_id for action in PROTOTYPE_ACTIONS
    )

    def __init__(
        self, actions: tuple[RegisteredAction, ...] = PROTOTYPE_ACTIONS
    ) -> None:
        by_id = {action.action_id: action for action in actions}
        if len(by_id) != len(actions):
            raise ValueError("Registered action IDs must be unique")
        self._actions = MappingProxyType(by_id)

    def resolve(self, action_id: str) -> RegisteredAction | None:
        return self._actions.get(action_id)

    def llm_descriptors(self) -> tuple[dict[str, object], ...]:
        return tuple(action.llm_descriptor() for action in self._actions.values())

    @property
    def action_ids(self) -> frozenset[str]:
        return frozenset(self._actions)
