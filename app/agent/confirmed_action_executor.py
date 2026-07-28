from dataclasses import dataclass, field
from datetime import datetime

from app.agent.action_dispatcher import ActionDispatcher
from app.agent.action_models import (
    AssistantResult,
    AssistantStatus,
    NavigationDirective,
)
from app.agent.action_registry import (
    ActionEffect,
    BackendActionRegistry,
    InvalidActionParameters,
    MissingActionParameters,
    RegisteredAction,
)
from app.agent.response_builder import SafeAssistantResponseBuilder
from app.application.dto.meeting_scheduling import (
    MeetingCreateCommand,
    MeetingRescheduleCommand,
    normalize_start_time,
)
from app.application.services.audit_service import AuditService
from app.application.services.meeting_scheduling_service import (
    MeetingSchedulingService,
)
from app.domain.entities.user import User
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal


@dataclass(slots=True)
class ConfirmedActionExecutor:
    registry: BackendActionRegistry
    dispatcher: ActionDispatcher
    scheduling_service: MeetingSchedulingService
    audit_service: AuditService
    response_builder: SafeAssistantResponseBuilder = field(
        default_factory=SafeAssistantResponseBuilder
    )

    async def execute(
        self,
        *,
        action_id: str,
        raw_parameters: dict[str, str | int | bool],
        authenticated_user: User,
        request_id: str,
    ) -> AssistantResult:
        action = self.registry.resolve(action_id)
        if action is None or not action.confirmation_required:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                reason=(
                    "action_not_registered"
                    if action is None
                    else "confirmation_not_supported"
                ),
            )
            return self._result(
                status=AssistantStatus.ACTION_DENIED,
                message="That confirmed assistant action is not available.",
                request_id=request_id,
            )

        try:
            parameters = action.validate_parameters(raw_parameters)
        except MissingActionParameters:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                reason="missing_parameters",
                action_id=action.action_id,
            )
            return self._result(
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
                reason="invalid_parameters",
                action_id=action.action_id,
            )
            return self._result(
                status=AssistantStatus.ACTION_DENIED,
                intent=action.effect.value,
                action_id=action.action_id,
                message="The confirmed action parameters are invalid.",
                request_id=request_id,
            )

        principal = AuthenticatedPrincipal(
            user_id=authenticated_user.id,
            is_active=authenticated_user.is_active,
        )
        dispatch = await self.dispatcher.dispatch(
            action=action,
            parameters=parameters,
            principal=principal,
        )
        resource_id = str(parameters.get("meeting_id", "pending"))
        if not dispatch.resource_found:
            await self._audit_rejection(
                request_id=request_id,
                user_id=authenticated_user.id,
                reason=dispatch.reason,
                action_id=action.action_id,
                resource_id=resource_id,
            )
            return self._result(
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
                reason=dispatch.reason,
                action_id=action.action_id,
                resource_id=resource_id,
            )
            return self._result(
                status=AssistantStatus.ACCESS_DENIED,
                intent=action.effect.value,
                action_id=action.action_id,
                parameters=parameters,
                message="You are not authorized to perform that action.",
                request_id=request_id,
            )

        navigation_path = dispatch.navigation_path
        if action.effect is ActionEffect.MUTATION:
            navigation_path, resource_id = await self._execute_mutation(
                action=action,
                parameters=parameters,
                principal=principal,
                request_id=request_id,
            )

        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=authenticated_user.id,
            event_type="assistant_action_executed",
            resource_type="meeting" if resource_id != "pending" else "assistant_action",
            resource_id=resource_id,
            action_id=action.action_id,
            allowed=True,
            reason=dispatch.reason,
        )
        navigation = (
            NavigationDirective(path=navigation_path)
            if navigation_path is not None
            else None
        )
        return self._result(
            status=AssistantStatus.SUCCESS,
            intent=action.effect.value,
            action_id=action.action_id,
            parameters=parameters,
            message=self.response_builder.action_message(action.action_id),
            navigation=navigation,
            request_id=request_id,
        )

    async def _execute_mutation(
        self,
        *,
        action: RegisteredAction,
        parameters: dict[str, str | int | bool],
        principal: AuthenticatedPrincipal,
        request_id: str,
    ) -> tuple[str, str]:
        if action.action_id == "create_meeting":
            result = await self.scheduling_service.create_meeting(
                principal,
                MeetingCreateCommand(
                    title=str(parameters["title"]),
                    place=str(parameters["place"]),
                    purpose=str(parameters["purpose"]),
                    start_time=self._parse_start_time(parameters["start_time"]),
                    duration_minutes=int(parameters["duration_minutes"]),
                    personal_gift=str(parameters.get("personal_gift", "")),
                ),
                request_id,
            )
        elif action.action_id == "reschedule_meeting":
            meeting_id = str(parameters["meeting_id"])
            result = await self.scheduling_service.reschedule_meeting(
                principal,
                meeting_id,
                MeetingRescheduleCommand(
                    start_time=self._parse_start_time(parameters["start_time"]),
                    duration_minutes=int(parameters["duration_minutes"]),
                    title=self._optional_text(parameters, "title"),
                    place=self._optional_text(parameters, "place"),
                    purpose=self._optional_text(parameters, "purpose"),
                    personal_gift=self._optional_text(
                        parameters, "personal_gift"
                    ),
                ),
                request_id,
            )
        else:
            raise RuntimeError("Unsupported registered mutation action")
        return f"/meetings/{result.id}", result.id

    async def _audit_rejection(
        self,
        *,
        request_id: str,
        user_id: str,
        reason: str,
        action_id: str | None = None,
        resource_id: str = "unresolved",
    ) -> None:
        await self.audit_service.record_resource_access(
            request_id=request_id,
            actor_user_id=user_id,
            event_type="assistant_action_rejected",
            resource_type="assistant_action",
            resource_id=resource_id,
            action_id=action_id,
            allowed=False,
            reason=reason,
        )

    @staticmethod
    def _parse_start_time(value: str | int | bool) -> datetime:
        if not isinstance(value, str):
            raise RuntimeError("Validated start time is not a string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return normalize_start_time(parsed)

    @staticmethod
    def _optional_text(
        parameters: dict[str, str | int | bool], key: str
    ) -> str | None:
        value = parameters.get(key)
        return value if isinstance(value, str) else None

    @staticmethod
    def _result(
        *,
        status: AssistantStatus,
        message: str,
        request_id: str,
        intent: str | None = None,
        action_id: str | None = None,
        parameters: dict[str, str | int | bool] | None = None,
        navigation: NavigationDirective | None = None,
    ) -> AssistantResult:
        return AssistantResult(
            status=status,
            intent=intent,
            action_id=action_id,
            message=message,
            requires_confirmation=False,
            parameters=parameters or {},
            navigation=navigation,
            request_id=request_id,
        )
