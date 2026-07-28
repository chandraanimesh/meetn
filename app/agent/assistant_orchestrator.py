from dataclasses import dataclass, field

from pydantic import ValidationError

from app.agent.action_dispatcher import ActionDispatcher
from app.agent.action_models import (
    AgentDecision,
    AssistantResult,
    AssistantStatus,
    NavigationDirective,
    PresentationDirective,
)
from app.agent.action_registry import (
    ActionPermission,
    BackendActionRegistry,
    InvalidActionParameters,
    MissingActionParameters,
    RegisteredAction,
)
from app.agent.context_builder import SafeContextBuilder
from app.agent.instructions import SYSTEM_INSTRUCTIONS
from app.agent.response_builder import SafeAssistantResponseBuilder
from app.agent.sentiment_analyzer import SafeSentimentAnalyzer, UserSentiment
from app.application.dto.assistant import PageManifestDTO
from app.application.ports.llm_provider import LLMProviderPort
from app.application.services.audit_service import AuditService
from app.domain.entities.user import User
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


PRESENTATION_ACTIONS = {
    UserSentiment.STRESSED: "activate_soothing_theme",
    UserSentiment.HAPPY: "activate_happy_theme",
    UserSentiment.EYE_STRAIN: "activate_dark_theme",
    UserSentiment.DARK_THEME: "activate_dark_theme",
    UserSentiment.LIGHT_THEME: "activate_light_theme",
    UserSentiment.SYSTEM_THEME: "activate_system_theme",
}


@dataclass(slots=True)
class AssistantOrchestrator:
    llm_provider: LLMProviderPort
    registry: BackendActionRegistry
    context_builder: SafeContextBuilder
    dispatcher: ActionDispatcher
    audit_service: AuditService
    response_builder: SafeAssistantResponseBuilder = field(
        default_factory=SafeAssistantResponseBuilder
    )
    sentiment_analyzer: SafeSentimentAnalyzer = field(
        default_factory=SafeSentimentAnalyzer
    )

    async def handle_message(
        self,
        *,
        user_message: str,
        page_manifest: PageManifestDTO,
        authenticated_user: User,
        request_id: str,
    ) -> AssistantResult:
        message = user_message.strip()
        if not message:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=None,
                reason="empty_message",
            )
            return self._safe_result(
                status=AssistantStatus.CLARIFICATION_REQUIRED,
                message="What would you like to open?",
                request_id=request_id,
            )
        if len(message) > 2_000:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=None,
                reason="message_too_long",
            )
            return self._safe_result(
                status=AssistantStatus.ACTION_DENIED,
                message="The assistant message is too long.",
                request_id=request_id,
            )

        safe_context = self.context_builder.build(
            authenticated_user=authenticated_user,
            page_manifest=page_manifest,
            registry=self.registry,
        )
        presentation_action_id = PRESENTATION_ACTIONS.get(
            self.sentiment_analyzer.analyze(message)
        )
        if presentation_action_id is not None:
            decision = AgentDecision(
                intent="presentation",
                action_id=presentation_action_id,
                message="Apply the requested presentation preference.",
                requires_confirmation=False,
                parameters={},
            )
        else:
            raw_output = await self.llm_provider.decide(
                instructions=SYSTEM_INSTRUCTIONS,
                user_message=message,
                safe_context=safe_context,
                output_schema=AgentDecision.model_json_schema(),
            )
            try:
                decision = AgentDecision.model_validate(dict(raw_output))
            except (ValidationError, TypeError, ValueError):
                await self._audit_rejection(
                    request_id=request_id,
                    user_id=authenticated_user.id,
                    action_id=None,
                    reason="invalid_llm_output",
                )
                return self._safe_result(
                    status=AssistantStatus.INVALID_OUTPUT,
                    message="The assistant could not produce a safe action.",
                    request_id=request_id,
                )

        action = self.registry.resolve(decision.action_id)
        if action is None:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=None,
                reason="action_not_registered",
            )
            return self._safe_result(
                status=AssistantStatus.ACTION_DENIED,
                message="That assistant action is not available.",
                request_id=request_id,
            )

        try:
            parameters = action.validate_parameters(decision.parameters)
        except MissingActionParameters:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=action.action_id,
                reason="missing_parameters",
            )
            return self._safe_result(
                status=AssistantStatus.CLARIFICATION_REQUIRED,
                intent=action.effect.value,
                action_id=action.action_id,
                message=action.clarification_message,
                request_id=request_id,
            )
        except InvalidActionParameters:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=action.action_id,
                reason="invalid_parameters",
            )
            return self._safe_result(
                status=AssistantStatus.ACTION_DENIED,
                intent=action.effect.value,
                action_id=action.action_id,
                message="The assistant action parameters are invalid.",
                request_id=request_id,
            )

        resource_type, resource_id = self._audit_resource(action, parameters)
        principal = AuthenticatedPrincipal(
            user_id=authenticated_user.id,
            is_active=authenticated_user.is_active,
        )
        dispatch = await self.dispatcher.dispatch(
            action=action,
            parameters=parameters,
            principal=principal,
        )
        if not dispatch.resource_found:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=action.action_id,
                reason=dispatch.reason,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return self._safe_result(
                status=AssistantStatus.NOT_FOUND,
                intent=action.effect.value,
                action_id=action.action_id,
                parameters=parameters,
                message="The requested resource was not found.",
                request_id=request_id,
            )
        if not dispatch.allowed:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                action_id=action.action_id,
                reason=dispatch.reason,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            return self._safe_result(
                status=AssistantStatus.ACCESS_DENIED,
                intent=action.effect.value,
                action_id=action.action_id,
                parameters=parameters,
                message="You are not authorized to perform that action.",
                request_id=request_id,
            )
        if action.confirmation_required:
            await self.audit_service.record_resource_access(
                request_id=request_id,
                actor_user_id=authenticated_user.id,
                event_type="assistant_action_pending_confirmation",
                resource_type=resource_type,
                resource_id=resource_id,
                action_id=action.action_id,
                allowed=True,
                reason="confirmation_required",
            )
            return self._safe_result(
                status=AssistantStatus.CONFIRMATION_REQUIRED,
                intent=action.effect.value,
                action_id=action.action_id,
                parameters=parameters,
                message=self.response_builder.action_message(
                    action.action_id,
                    confirmation_required=True,
                ),
                requires_confirmation=True,
                request_id=request_id,
            )

        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=authenticated_user.id,
            event_type="assistant_action_selected",
            resource_type=resource_type,
            resource_id=resource_id,
            action_id=action.action_id,
            allowed=True,
            reason=dispatch.reason,
        )
        navigation = (
            NavigationDirective(path=dispatch.navigation_path)
            if dispatch.navigation_path is not None
            else None
        )
        presentation = (
            PresentationDirective(
                theme=dispatch.presentation_theme,
                reason=action.presentation_reason or "backend_approved",
            )
            if dispatch.presentation_theme is not None
            else None
        )
        return self._safe_result(
            status=AssistantStatus.SUCCESS,
            intent=action.effect.value,
            action_id=action.action_id,
            parameters=parameters,
            message=self.response_builder.action_message(action.action_id),
            navigation=navigation,
            focus_target=dispatch.focus_target,
            presentation=presentation,
            request_id=request_id,
        )

    async def _audit_rejection(
        self,
        *,
        request_id: str,
        user_id: str,
        action_id: str | None,
        reason: str,
        resource_type: str = "assistant_action",
        resource_id: str = "unresolved",
    ) -> None:
        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=user_id,
            event_type="assistant_action_rejected",
            resource_type=resource_type,
            resource_id=resource_id,
            action_id=action_id,
            allowed=False,
            reason=reason,
        )

    @staticmethod
    def _audit_resource(
        action: RegisteredAction,
        parameters: dict[str, str | int | bool],
    ) -> tuple[str, str]:
        meeting_id = parameters.get("meeting_id")
        if isinstance(meeting_id, str):
            resource_types = {
                ActionPermission.MEETING: "meeting",
                ActionPermission.TRANSCRIPT: "transcript",
                ActionPermission.CONFIDENTIAL_NOTES: ("confidential_note_collection"),
            }
            return resource_types.get(action.permission, "meeting"), meeting_id
        if action.action_id == "create_meeting":
            return "meeting", "pending"
        return "assistant_action", action.action_id

    @staticmethod
    def _safe_result(
        *,
        status: AssistantStatus,
        message: str,
        request_id: str,
        intent: str | None = None,
        action_id: str | None = None,
        requires_confirmation: bool = False,
        parameters: dict[str, str | int | bool] | None = None,
        navigation: NavigationDirective | None = None,
        focus_target: str | None = None,
        presentation: PresentationDirective | None = None,
    ) -> AssistantResult:
        return AssistantResult(
            status=status,
            intent=intent,
            action_id=action_id,
            message=message,
            requires_confirmation=requires_confirmation,
            parameters=parameters or {},
            navigation=navigation,
            focus_target=focus_target,
            presentation=presentation,
            request_id=request_id,
        )
