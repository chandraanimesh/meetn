from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Mapping


@dataclass(frozen=True, slots=True)
class SafeAssistantResponseBuilder:
    """Build browser-visible prose without trusting model-authored text."""

    _ACTION_MESSAGES: ClassVar[Mapping[str, str]] = MappingProxyType(
        {
            "open_dashboard": "Your dashboard is ready to open.",
            "open_meeting_history": "Your meeting history is ready to open.",
            "open_meeting_detail": "The authorized meeting is ready to open.",
            "open_transcript": "The authorized transcript page is ready to open.",
            "open_transcript_upload": ("The transcript upload page is ready to open."),
            "open_confidential_notes": (
                "The authorized confidential-notes page is ready to open."
            ),
            "open_membership_plans": ("The membership plans page is ready to open."),
            "focus_meeting_search": "Meeting search is ready to use.",
            "activate_soothing_theme": (
                "I switched the interface to a calmer, soothing theme."
            ),
            "activate_happy_theme": (
                "I switched the interface to a warm, cheerful theme."
            ),
            "activate_dark_theme": "I switched the interface to dark mode.",
            "activate_light_theme": "I switched the interface to light mode.",
            "activate_system_theme": ("The interface now follows your system theme."),
            "create_meeting": "Your meeting has been planned.",
            "reschedule_meeting": "Your meeting has been rescheduled.",
        }
    )

    def action_message(
        self, action_id: str, *, confirmation_required: bool = False
    ) -> str:
        if confirmation_required:
            return "Please confirm this action before continuing."
        return self._ACTION_MESSAGES.get(
            action_id,
            "The requested action is ready.",
        )
