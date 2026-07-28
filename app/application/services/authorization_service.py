from dataclasses import dataclass, field

from app.domain.policies.confidential_note_policy import ConfidentialNotePolicy
from app.domain.policies.meeting_access_policy import MeetingAccessPolicy
from app.domain.policies.transcript_access_policy import TranscriptAccessPolicy
from app.domain.value_objects.access_decision import AccessDecision
from app.domain.value_objects.authorization_facts import (
    AuthenticatedPrincipal,
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)


@dataclass(frozen=True, slots=True)
class AuthorizationService:
    """Route-independent facade over backend authorization policies.

    The principal must come from the verified application session. This API does
    not accept a client-provided user ID, participant flag, or role claim.
    """

    meeting_policy: MeetingAccessPolicy = field(default_factory=MeetingAccessPolicy)
    transcript_policy: TranscriptAccessPolicy = field(
        default_factory=TranscriptAccessPolicy
    )
    confidential_note_policy: ConfidentialNotePolicy = field(
        default_factory=ConfidentialNotePolicy
    )

    def can_list_meeting(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
    ) -> AccessDecision:
        return self.meeting_policy.can_list(principal, meeting)

    def can_view_transcript(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
    ) -> AccessDecision:
        return self.transcript_policy.can_view(principal, meeting)

    def can_manage_meeting(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
    ) -> AccessDecision:
        return self.meeting_policy.can_manage(principal, meeting)

    def can_view_confidential_note(
        self,
        principal: AuthenticatedPrincipal,
        meeting: MeetingAccessFacts,
        note: ConfidentialNoteAccessFacts,
    ) -> AccessDecision:
        return self.confidential_note_policy.can_view(principal, meeting, note)
