from dataclasses import dataclass

from app.agent.action_registry import (
    ActionPermission,
    RegisteredAction,
)
from app.agent.action_models import PresentationTheme
from app.application.ports.meeting_repository import MeetingRepositoryPort
from app.application.services.authorization_service import AuthorizationService
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    MeetingAccessFacts,
)


@dataclass(frozen=True, slots=True)
class ActionDispatchResult:
    allowed: bool
    reason: str
    resource_found: bool = True
    navigation_path: str | None = None
    focus_target: str | None = None
    presentation_theme: PresentationTheme | None = None


@dataclass(slots=True)
class ActionDispatcher:
    meeting_repository: MeetingRepositoryPort
    authorization_service: AuthorizationService

    async def dispatch(
        self,
        *,
        action: RegisteredAction,
        parameters: dict[str, str | int | bool],
        principal: AuthenticatedPrincipal,
    ) -> ActionDispatchResult:
        if action.permission is ActionPermission.AUTHENTICATED:
            return self._allowed(action, parameters, "authenticated")

        meeting_id = str(parameters["meeting_id"])
        meeting = await self.meeting_repository.get_meeting_access_facts(meeting_id)
        if meeting is None:
            return ActionDispatchResult(
                allowed=False,
                reason="resource_not_found",
                resource_found=False,
            )

        if action.permission is ActionPermission.MEETING:
            decision = self.authorization_service.can_list_meeting(
                principal, meeting
            )
        elif action.permission is ActionPermission.MEETING_ORGANIZER:
            decision = self.authorization_service.can_manage_meeting(
                principal, meeting
            )
        elif action.permission is ActionPermission.TRANSCRIPT:
            if not await self.meeting_repository.transcript_exists(meeting_id):
                return ActionDispatchResult(
                    allowed=False,
                    reason="resource_not_found",
                    resource_found=False,
                )
            decision = self.authorization_service.can_view_transcript(
                principal, meeting
            )
        else:
            return await self._dispatch_confidential_notes(
                action=action,
                parameters=parameters,
                principal=principal,
                meeting_id=meeting_id,
                meeting=meeting,
            )

        if not decision.allowed:
            return ActionDispatchResult(allowed=False, reason=decision.reason)
        return self._allowed(action, parameters, decision.reason)

    async def _dispatch_confidential_notes(
        self,
        *,
        action: RegisteredAction,
        parameters: dict[str, str | int | bool],
        principal: AuthenticatedPrincipal,
        meeting_id: str,
        meeting: MeetingAccessFacts,
    ) -> ActionDispatchResult:
        if principal.user_id == meeting.organizer_user_id:
            return self._allowed(action, parameters, "organizer")

        notes = await self.meeting_repository.get_confidential_note_access_facts(
            meeting_id
        )
        for note in notes:
            decision = self.authorization_service.can_view_confidential_note(
                principal, meeting, note
            )
            if decision.allowed:
                return self._allowed(action, parameters, decision.reason)
        return ActionDispatchResult(allowed=False, reason="not_authorized")

    @staticmethod
    def _allowed(
        action: RegisteredAction,
        parameters: dict[str, str | int | bool],
        reason: str,
    ) -> ActionDispatchResult:
        return ActionDispatchResult(
            allowed=True,
            reason=reason,
            navigation_path=action.render_navigation(parameters),
            focus_target=action.focus_target,
            presentation_theme=action.presentation_theme,
        )
