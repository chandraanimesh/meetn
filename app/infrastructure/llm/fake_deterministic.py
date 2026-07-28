from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(slots=True)
class FakeDeterministicLLM:
    """Network-free structured-output provider for prototype and tests."""

    fixed_output: Mapping[str, object] | None = None
    last_safe_context: Mapping[str, object] | None = field(
        default=None, init=False
    )
    last_output_schema: Mapping[str, object] | None = field(
        default=None, init=False
    )

    async def decide(
        self,
        *,
        instructions: str,
        user_message: str,
        safe_context: Mapping[str, object],
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.last_safe_context = safe_context
        self.last_output_schema = output_schema
        if self.fixed_output is not None:
            return dict(self.fixed_output)

        active_meeting_id = self._active_meeting_id(safe_context)
        normalized = user_message.casefold()
        parameters = (
            {"meeting_id": active_meeting_id}
            if active_meeting_id is not None
            else {}
        )

        if any(
            phrase in normalized
            for phrase in (
                "feeling stressed",
                "feel stressed",
                "feeling anxious",
                "feel anxious",
                "feeling overwhelmed",
                "feel overwhelmed",
            )
        ):
            return self._decision(
                "activate_soothing_theme",
                "I can use a calmer interface.",
                intent="presentation",
            )
        if "dashboard" in normalized or "home page" in normalized:
            return self._decision(
                "open_dashboard",
                "I can open your dashboard.",
            )
        if "reschedule" in normalized:
            return self._decision(
                "reschedule_meeting",
                "I can help reschedule that meeting.",
                parameters,
                intent="reschedule_meeting",
            )
        if (
            "plan a meeting" in normalized
            or "schedule a meeting" in normalized
            or "create a meeting" in normalized
        ):
            return self._decision(
                "create_meeting",
                "I can help plan that meeting.",
                intent="create_meeting",
            )

        if "confidential" in normalized or "note" in normalized:
            return self._decision(
                "open_confidential_notes",
                "I can open the confidential-notes page.",
                parameters,
            )
        if "add transcript" in normalized or "upload transcript" in normalized:
            return self._decision(
                "open_transcript_upload",
                "I can open the transcript upload page.",
                parameters,
            )
        if "transcript" in normalized:
            return self._decision(
                "open_transcript",
                "I can open the transcript page.",
                parameters,
            )
        if "detail" in normalized:
            return self._decision(
                "open_meeting_detail",
                "I can open the meeting details.",
                parameters,
            )
        if "history" in normalized or "past meeting" in normalized:
            return self._decision(
                "open_meeting_history",
                "I can open your meeting history.",
            )
        if "plan" in normalized or "membership" in normalized:
            return self._decision(
                "open_membership_plans",
                "I can open the membership plans.",
            )
        return self._decision(
            "focus_meeting_search",
            "I can focus meeting search.",
            intent="search_meetings",
        )

    @staticmethod
    def _active_meeting_id(safe_context: Mapping[str, object]) -> str | None:
        page_manifest = safe_context.get("page_manifest")
        if not isinstance(page_manifest, Mapping):
            return None
        meeting_id = page_manifest.get("active_meeting_id")
        return meeting_id if isinstance(meeting_id, str) else None

    @staticmethod
    def _decision(
        action_id: str,
        message: str,
        parameters: dict[str, str] | None = None,
        *,
        intent: str = "navigate",
    ) -> dict[str, object]:
        return {
            "intent": intent,
            "action_id": action_id,
            "message": message,
            "requires_confirmation": False,
            "parameters": parameters or {},
        }
