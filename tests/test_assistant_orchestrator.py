from dataclasses import dataclass, field
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from app.agent.action_dispatcher import ActionDispatcher
from app.agent.action_models import AssistantResult, AssistantStatus
from app.agent.action_registry import BackendActionRegistry
from app.agent.assistant_orchestrator import AssistantOrchestrator
from app.agent.context_builder import SafeContextBuilder
from app.application.dto.assistant import PageManifestDTO
from app.application.ports.audit_repository import AuditRepositoryPort
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.services.audit_service import AuditService
from app.application.services.authorization_service import AuthorizationService
from app.domain.entities.audit_event import AuditEvent
from app.domain.entities.user import User
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)
from app.infrastructure.llm.fake_deterministic import FakeDeterministicLLM


pytestmark = pytest.mark.asyncio

USER_ID = "user-1"
MEETING_ID = "meeting-1"


@dataclass(slots=True)
class InMemoryAuditRepository(AuditRepositoryPort):
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


def decision(
    action_id: str,
    *,
    parameters: dict[str, object] | None = None,
    message: str = "I can do that.",
    requires_confirmation: bool = False,
) -> dict[str, object]:
    return {
        "intent": "navigate",
        "action_id": action_id,
        "message": message,
        "requires_confirmation": requires_confirmation,
        "parameters": parameters or {},
    }


def build_orchestrator(
    output: dict[str, object],
) -> tuple[
    AssistantOrchestrator,
    Mock,
    InMemoryAuditRepository,
    FakeDeterministicLLM,
]:
    repository = Mock(spec=MeetingRepositoryPort)
    repository.get_meeting_access_facts = AsyncMock(
        return_value=MeetingAccessFacts(
            meeting_id=MEETING_ID,
            organizer_user_id="organizer",
            active_participant_user_ids=frozenset({USER_ID}),
        )
    )
    repository.transcript_exists = AsyncMock(return_value=True)
    repository.get_confidential_note_access_facts = AsyncMock(return_value=[])
    repository.get_confidential_notes = AsyncMock(
        side_effect=AssertionError("Assistant must not load note content")
    )
    repository.get_transcript = AsyncMock(
        side_effect=AssertionError("Assistant must not load transcript content")
    )
    audit_repository = InMemoryAuditRepository()
    llm = FakeDeterministicLLM(fixed_output=output)
    orchestrator = AssistantOrchestrator(
        llm_provider=llm,
        registry=BackendActionRegistry(),
        context_builder=SafeContextBuilder(),
        dispatcher=ActionDispatcher(
            meeting_repository=cast(MeetingRepositoryPort, repository),
            authorization_service=AuthorizationService(),
        ),
        audit_service=AuditService(audit_repository),
    )
    return orchestrator, repository, audit_repository, llm


async def run_orchestrator(
    orchestrator: AssistantOrchestrator,
    *,
    user_message: str = "help me",
) -> AssistantResult:
    return await orchestrator.handle_message(
        user_message=user_message,
        page_manifest=PageManifestDTO(
            page_id="meeting_detail",
            active_meeting_id=MEETING_ID,
            visible_meeting_ids=(MEETING_ID,),
        ),
        authenticated_user=User(
            id=USER_ID,
            display_name="Safe User",
            primary_email="private@example.invalid",
        ),
        request_id="request-1",
    )


async def test_authorized_transcript_action_requires_backend_confirmation() -> None:
    orchestrator, repository, audit_repository, llm = build_orchestrator(
        decision("open_transcript", parameters={"meeting_id": MEETING_ID})
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.CONFIRMATION_REQUIRED
    assert result.requires_confirmation
    assert result.navigation is None
    assert result.parameters == {"meeting_id": MEETING_ID}
    repository.get_transcript.assert_not_awaited()
    repository.get_confidential_notes.assert_not_awaited()
    assert (
        audit_repository.events[0].event_type == "assistant_action_pending_confirmation"
    )
    assert audit_repository.events[0].action_id == "open_transcript"
    assert audit_repository.events[0].resource_type == "transcript"
    assert audit_repository.events[0].resource_id == MEETING_ID
    assert llm.last_output_schema is not None
    assert "required" in llm.last_output_schema


async def test_transcript_upload_navigation_is_organizer_only_and_confirmed() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision(
            "open_transcript_upload",
            parameters={"meeting_id": MEETING_ID},
        )
    )
    repository.get_meeting_access_facts.return_value = MeetingAccessFacts(
        meeting_id=MEETING_ID,
        organizer_user_id=USER_ID,
        active_participant_user_ids=frozenset({USER_ID}),
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.CONFIRMATION_REQUIRED
    assert result.action_id == "open_transcript_upload"
    assert result.requires_confirmation
    assert result.navigation is None
    repository.transcript_exists.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "confirmation_required"


async def test_participant_cannot_open_transcript_upload_navigation() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision(
            "open_transcript_upload",
            parameters={"meeting_id": MEETING_ID},
        )
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.ACCESS_DENIED
    assert result.navigation is None
    repository.transcript_exists.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "not_authorized"


async def test_unknown_action_is_denied_before_repository_lookup() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision("delete_everything")
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.ACTION_DENIED
    assert result.navigation is None
    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "action_not_registered"
    assert audit_repository.events[0].action_id is None
    assert "delete_everything" not in repr(audit_repository.events[0])


async def test_missing_parameters_request_clarification() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision("open_meeting_detail")
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.CLARIFICATION_REQUIRED
    assert result.message == "Which meeting should I use?"
    assert result.navigation is None
    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "missing_parameters"


async def test_confirmation_prevents_effect_execution() -> None:
    orchestrator, _, audit_repository, _ = build_orchestrator(
        decision("open_membership_plans", requires_confirmation=True)
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.CONFIRMATION_REQUIRED
    assert result.requires_confirmation
    assert result.navigation is None
    assert (
        audit_repository.events[0].event_type == "assistant_action_pending_confirmation"
    )
    assert audit_repository.events[0].authorization_decision.value == "allowed"
    assert audit_repository.events[0].decision_reason == "confirmation_required"


async def test_meeting_creation_requires_confirmation_even_if_model_says_no() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision(
            "create_meeting",
            parameters={
                "title": "Planning",
                "place": "Room 1",
                "purpose": "Plan work",
                "start_time": "2026-08-01T10:00:00+05:30",
                "duration_minutes": 60,
                "personal_gift": "Coffee",
            },
            requires_confirmation=False,
        )
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.CONFIRMATION_REQUIRED
    assert result.requires_confirmation
    assert result.navigation is None
    repository.create_meeting.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "confirmation_required"


async def test_invalid_url_output_fails_closed() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision(
            "open_meeting_history",
            message="Open https://malicious.example",
        )
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.INVALID_OUTPUT
    assert "https://" not in result.message
    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events[0].decision_reason == "invalid_llm_output"


async def test_confidential_action_uses_only_content_free_facts() -> None:
    orchestrator, repository, _, _ = build_orchestrator(
        decision(
            "open_confidential_notes",
            parameters={"meeting_id": MEETING_ID},
        )
    )
    repository.get_confidential_note_access_facts.return_value = [
        ConfidentialNoteAccessFacts(
            note_id="note-1",
            meeting_id=MEETING_ID,
            allowed_user_ids=frozenset({USER_ID}),
        )
    ]

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.SUCCESS
    repository.get_confidential_note_access_facts.assert_awaited_once_with(MEETING_ID)
    repository.get_confidential_notes.assert_not_awaited()
    repository.get_transcript.assert_not_awaited()


async def test_safe_context_excludes_email_and_protected_content() -> None:
    orchestrator, _, _, llm = build_orchestrator(decision("focus_meeting_search"))

    await run_orchestrator(orchestrator)

    serialized_context = repr(llm.last_safe_context)
    assert "private@example.invalid" not in serialized_context
    assert "Authorized transcript content" not in serialized_context
    assert "Authorized confidential note content" not in serialized_context
    assert "navigation_template" not in serialized_context
    assert "display_name" in serialized_context


async def test_dashboard_navigation_is_backend_registered_and_authenticated() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision("open_dashboard")
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.SUCCESS
    assert result.action_id == "open_dashboard"
    assert result.navigation is not None
    assert result.navigation.path == "/dashboard"
    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events[0].event_type == "assistant_action_selected"
    assert audit_repository.events[0].decision_reason == "authenticated"


async def test_stress_sentiment_uses_registered_soothing_presentation_without_llm() -> (
    None
):
    orchestrator, repository, audit_repository, llm = build_orchestrator(
        decision("delete_everything")
    )

    result = await run_orchestrator(
        orchestrator,
        user_message="i m feeling stressed",
    )

    assert result.status is AssistantStatus.SUCCESS
    assert result.action_id == "activate_soothing_theme"
    assert result.presentation is not None
    assert result.presentation.theme.value == "soothing"
    assert result.presentation.reason == "stress_detected"
    assert result.navigation is None
    assert result.focus_target is None
    assert llm.last_safe_context is None
    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events[0].action_id == "activate_soothing_theme"
    assert audit_repository.events[0].decision_reason == "authenticated"


@pytest.mark.parametrize(
    ("user_message", "action_id", "theme", "reason"),
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
        (
            "I am happy, but turn to dark mode",
            "activate_dark_theme",
            "dark",
            "dark_theme_requested",
        ),
    ],
)
async def test_presentation_signal_uses_registered_theme_without_llm(
    user_message: str,
    action_id: str,
    theme: str,
    reason: str,
) -> None:
    orchestrator, repository, audit_repository, llm = build_orchestrator(
        decision("delete_everything")
    )

    result = await run_orchestrator(
        orchestrator,
        user_message=user_message,
    )

    assert result.status is AssistantStatus.SUCCESS
    assert result.action_id == action_id
    assert result.presentation is not None
    assert result.presentation.theme.value == theme
    assert result.presentation.reason == reason
    assert result.navigation is None
    assert result.focus_target is None
    assert llm.last_safe_context is None
    repository.get_meeting_access_facts.assert_not_awaited()
    assert audit_repository.events[0].action_id == action_id
    assert audit_repository.events[0].decision_reason == "authenticated"


async def test_negated_stress_does_not_change_presentation() -> None:
    orchestrator, _, _, llm = build_orchestrator(decision("open_dashboard"))

    result = await run_orchestrator(
        orchestrator,
        user_message="I am not stressed",
    )

    assert result.action_id == "open_dashboard"
    assert result.presentation is None
    assert llm.last_safe_context is not None


async def test_dispatcher_denies_unrelated_principal() -> None:
    orchestrator, repository, audit_repository, _ = build_orchestrator(
        decision("open_meeting_detail", parameters={"meeting_id": MEETING_ID})
    )
    repository.get_meeting_access_facts.return_value = MeetingAccessFacts(
        meeting_id=MEETING_ID,
        organizer_user_id="another-user",
    )

    result = await run_orchestrator(orchestrator)

    assert result.status is AssistantStatus.ACCESS_DENIED
    assert result.navigation is None
    assert audit_repository.events[0].decision_reason == "not_authorized"


async def test_fake_llm_is_deterministic_and_returns_structured_output() -> None:
    provider = FakeDeterministicLLM()
    context: dict[str, object] = {"page_manifest": {"active_meeting_id": MEETING_ID}}
    schema = {"type": "object"}

    first = await provider.decide(
        instructions="structured only",
        user_message="Open transcript",
        safe_context=context,
        output_schema=schema,
    )
    second = await provider.decide(
        instructions="structured only",
        user_message="Open transcript",
        safe_context=context,
        output_schema=schema,
    )

    assert first == second
    assert first["action_id"] == "open_transcript"
    assert first["parameters"] == {"meeting_id": MEETING_ID}


async def test_fake_llm_can_select_dashboard_navigation() -> None:
    provider = FakeDeterministicLLM()

    result = await provider.decide(
        instructions="structured only",
        user_message="Take me to my dashboard",
        safe_context={"page_manifest": {"active_meeting_id": None}},
        output_schema={"type": "object"},
    )

    assert result["action_id"] == "open_dashboard"
    assert result["parameters"] == {}


async def test_fake_llm_can_select_soothing_presentation() -> None:
    provider = FakeDeterministicLLM()

    result = await provider.decide(
        instructions="structured only",
        user_message="I am feeling overwhelmed",
        safe_context={"page_manifest": {"active_meeting_id": None}},
        output_schema={"type": "object"},
    )

    assert result["intent"] == "presentation"
    assert result["action_id"] == "activate_soothing_theme"
    assert result["parameters"] == {}


async def test_principal_is_not_accepted_from_llm_parameters() -> None:
    signature = ActionDispatcher.dispatch.__annotations__

    assert signature["principal"] is AuthenticatedPrincipal
