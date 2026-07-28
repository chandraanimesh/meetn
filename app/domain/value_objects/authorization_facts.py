from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Server-authenticated actor; never construct this from request body fields."""

    user_id: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ActiveMeetingRole:
    """A current, meeting-scoped role assignment loaded by the backend."""

    user_id: str
    role_id: str


@dataclass(frozen=True, slots=True)
class MeetingAccessFacts:
    """Current authorization facts for one meeting, loaded from trusted storage."""

    meeting_id: str
    organizer_user_id: str
    active_participant_user_ids: frozenset[str] = field(default_factory=frozenset)
    active_role_assignments: frozenset[ActiveMeetingRole] = field(
        default_factory=frozenset
    )

    def active_role_ids_for(self, user_id: str) -> frozenset[str]:
        return frozenset(
            assignment.role_id
            for assignment in self.active_role_assignments
            if assignment.user_id == user_id
        )


@dataclass(frozen=True, slots=True)
class ConfidentialNoteAccessFacts:
    """Current grants and resource scope for one confidential note."""

    note_id: str
    meeting_id: str
    allowed_user_ids: frozenset[str] = field(default_factory=frozenset)
    allowed_role_ids: frozenset[str] = field(default_factory=frozenset)
    is_deleted: bool = False

