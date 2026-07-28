from app.domain.value_objects.access_decision import AccessDecision
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    MeetingAccessFacts,
)


class MeetingAccessPolicy:
    VERSION = "meeting-access.v1"

    def can_list(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
    ) -> AccessDecision:
        scope = f"meeting:{meeting.meeting_id}"
        if not principal.is_active:
            return AccessDecision(False, "inactive_user", scope, self.VERSION)
        if principal.user_id == meeting.organizer_user_id:
            return AccessDecision(True, "organizer", scope, self.VERSION)
        if principal.user_id in meeting.active_participant_user_ids:
            return AccessDecision(True, "participant", scope, self.VERSION)
        return AccessDecision(False, "not_authorized", scope, self.VERSION)

    def can_manage(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
    ) -> AccessDecision:
        """Allow schedule mutations only for the active organizer."""

        scope = f"meeting:{meeting.meeting_id}"
        if not principal.is_active:
            return AccessDecision(False, "inactive_user", scope, self.VERSION)
        if principal.user_id == meeting.organizer_user_id:
            return AccessDecision(True, "organizer", scope, self.VERSION)
        return AccessDecision(False, "not_authorized", scope, self.VERSION)
