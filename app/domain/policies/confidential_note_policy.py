from app.domain.value_objects.access_decision import AccessDecision
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)


class ConfidentialNotePolicy:
    VERSION = "confidential-note-access.v1"

    def can_view(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
        note: ConfidentialNoteAccessFacts,
    ) -> AccessDecision:
        scope = f"confidential_note:{note.note_id}"
        if not principal.is_active:
            return AccessDecision(False, "inactive_user", scope, self.VERSION)
        if note.is_deleted:
            return AccessDecision(False, "resource_unavailable", scope, self.VERSION)
        if note.meeting_id != meeting.meeting_id:
            return AccessDecision(False, "resource_scope_mismatch", scope, self.VERSION)
        if principal.user_id == meeting.organizer_user_id:
            return AccessDecision(True, "organizer", scope, self.VERSION)

        # Explicit grants are valid only while the grantee remains a participant.
        if principal.user_id not in meeting.active_participant_user_ids:
            return AccessDecision(False, "not_authorized", scope, self.VERSION)
        if principal.user_id in note.allowed_user_ids:
            return AccessDecision(True, "explicit_user", scope, self.VERSION)

        active_roles = meeting.active_role_ids_for(principal.user_id)
        if active_roles & note.allowed_role_ids:
            return AccessDecision(True, "allowed_role", scope, self.VERSION)
        return AccessDecision(False, "not_authorized", scope, self.VERSION)

