import inspect
from collections.abc import Callable

import pytest

from app.application.services.authorization_service import AuthorizationService
from app.domain.value_objects.access_decision import AccessDecision
from app.domain.value_objects.authorization_facts import (
    ActiveMeetingRole,
    AuthenticatedPrincipal,
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)


ORGANIZER_ID = "user-organizer"
PARTICIPANT_ID = "user-participant"
OUTSIDER_ID = "user-outsider"
EXPLICIT_USER_ID = "user-explicit"
ALLOWED_ROLE_USER_ID = "user-legal"
DENIED_ROLE_USER_ID = "user-observer"
MEETING_ID = "meeting-1"
NOTE_ID = "note-1"
ALLOWED_ROLE_ID = "legal-reviewer"
DENIED_ROLE_ID = "observer"


@pytest.fixture
def service() -> AuthorizationService:
    return AuthorizationService()


@pytest.fixture
def meeting() -> MeetingAccessFacts:
    return MeetingAccessFacts(
        meeting_id=MEETING_ID,
        organizer_user_id=ORGANIZER_ID,
        active_participant_user_ids=frozenset(
            {
                ORGANIZER_ID,
                PARTICIPANT_ID,
                EXPLICIT_USER_ID,
                ALLOWED_ROLE_USER_ID,
                DENIED_ROLE_USER_ID,
            }
        ),
        active_role_assignments=frozenset(
            {
                ActiveMeetingRole(ALLOWED_ROLE_USER_ID, ALLOWED_ROLE_ID),
                ActiveMeetingRole(DENIED_ROLE_USER_ID, DENIED_ROLE_ID),
            }
        ),
    )


@pytest.fixture
def note() -> ConfidentialNoteAccessFacts:
    return ConfidentialNoteAccessFacts(
        note_id=NOTE_ID,
        meeting_id=MEETING_ID,
        allowed_user_ids=frozenset({EXPLICIT_USER_ID}),
        allowed_role_ids=frozenset({ALLOWED_ROLE_ID}),
    )


@pytest.mark.parametrize(
    ("method_name", "user_id", "allowed", "reason"),
    [
        ("can_list_meeting", ORGANIZER_ID, True, "organizer"),
        ("can_list_meeting", PARTICIPANT_ID, True, "participant"),
        ("can_list_meeting", OUTSIDER_ID, False, "not_authorized"),
        ("can_view_transcript", ORGANIZER_ID, True, "organizer"),
        ("can_view_transcript", PARTICIPANT_ID, True, "participant"),
        ("can_view_transcript", OUTSIDER_ID, False, "not_authorized"),
    ],
)
def test_meeting_and_transcript_access_matrix(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
    method_name: str,
    user_id: str,
    allowed: bool,
    reason: str,
) -> None:
    method = getattr(service, method_name)
    decision: AccessDecision = method(AuthenticatedPrincipal(user_id), meeting)

    assert decision.to_dict() == {"allowed": allowed, "reason": reason}


@pytest.mark.parametrize(
    ("user_id", "allowed", "reason"),
    [
        (ORGANIZER_ID, True, "organizer"),
        (PARTICIPANT_ID, False, "not_authorized"),
        (OUTSIDER_ID, False, "not_authorized"),
        (EXPLICIT_USER_ID, True, "explicit_user"),
        (ALLOWED_ROLE_USER_ID, True, "allowed_role"),
        (DENIED_ROLE_USER_ID, False, "not_authorized"),
    ],
)
def test_confidential_note_access_matrix(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
    note: ConfidentialNoteAccessFacts,
    user_id: str,
    allowed: bool,
    reason: str,
) -> None:
    decision = service.can_view_confidential_note(
        AuthenticatedPrincipal(user_id), meeting, note
    )

    assert decision.to_dict() == {"allowed": allowed, "reason": reason}


def test_explicit_grant_does_not_survive_participant_removal(
    service: AuthorizationService,
    note: ConfidentialNoteAccessFacts,
) -> None:
    meeting = MeetingAccessFacts(
        meeting_id=MEETING_ID,
        organizer_user_id=ORGANIZER_ID,
    )

    decision = service.can_view_confidential_note(
        AuthenticatedPrincipal(EXPLICIT_USER_ID), meeting, note
    )

    assert decision.to_dict() == {"allowed": False, "reason": "not_authorized"}


def test_role_grant_requires_an_active_matching_assignment(
    service: AuthorizationService,
    note: ConfidentialNoteAccessFacts,
) -> None:
    meeting = MeetingAccessFacts(
        meeting_id=MEETING_ID,
        organizer_user_id=ORGANIZER_ID,
        active_participant_user_ids=frozenset({ALLOWED_ROLE_USER_ID}),
        active_role_assignments=frozenset(
            {ActiveMeetingRole(ALLOWED_ROLE_USER_ID, DENIED_ROLE_ID)}
        ),
    )

    decision = service.can_view_confidential_note(
        AuthenticatedPrincipal(ALLOWED_ROLE_USER_ID), meeting, note
    )

    assert decision.to_dict() == {"allowed": False, "reason": "not_authorized"}


def test_note_from_another_meeting_is_denied(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
) -> None:
    note = ConfidentialNoteAccessFacts(
        note_id=NOTE_ID,
        meeting_id="meeting-2",
        allowed_user_ids=frozenset({EXPLICIT_USER_ID}),
    )

    decision = service.can_view_confidential_note(
        AuthenticatedPrincipal(EXPLICIT_USER_ID), meeting, note
    )

    assert decision.to_dict() == {
        "allowed": False,
        "reason": "resource_scope_mismatch",
    }


def test_deleted_note_is_denied(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
) -> None:
    note = ConfidentialNoteAccessFacts(
        note_id=NOTE_ID,
        meeting_id=MEETING_ID,
        allowed_user_ids=frozenset({EXPLICIT_USER_ID}),
        is_deleted=True,
    )

    decision = service.can_view_confidential_note(
        AuthenticatedPrincipal(EXPLICIT_USER_ID), meeting, note
    )

    assert decision.to_dict() == {
        "allowed": False,
        "reason": "resource_unavailable",
    }


def test_inactive_principal_is_denied_confidential_note_access(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
    note: ConfidentialNoteAccessFacts,
) -> None:
    decision = service.can_view_confidential_note(
        AuthenticatedPrincipal(ORGANIZER_ID, is_active=False), meeting, note
    )

    assert decision.to_dict() == {"allowed": False, "reason": "inactive_user"}


@pytest.mark.parametrize(
    "method_name",
    ["can_list_meeting", "can_view_transcript"],
)
def test_inactive_principal_is_denied_meeting_access(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
    method_name: str,
) -> None:
    method: Callable[..., AccessDecision] = getattr(service, method_name)

    decision = method(
        AuthenticatedPrincipal(ORGANIZER_ID, is_active=False), meeting
    )

    assert decision.to_dict() == {"allowed": False, "reason": "inactive_user"}


def test_frontend_user_id_cannot_affect_authorization(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
) -> None:
    frontend_payload = {"user_id": ORGANIZER_ID}
    authenticated_principal = AuthenticatedPrincipal(OUTSIDER_ID)

    decision = service.can_list_meeting(authenticated_principal, meeting)

    assert frontend_payload["user_id"] != authenticated_principal.user_id
    assert decision.to_dict() == {"allowed": False, "reason": "not_authorized"}
    assert "user_id" not in inspect.signature(service.can_list_meeting).parameters
    assert "frontend_user_id" not in inspect.signature(
        service.can_list_meeting
    ).parameters


def test_decision_contains_stable_policy_metadata(
    service: AuthorizationService,
    meeting: MeetingAccessFacts,
) -> None:
    decision = service.can_list_meeting(
        AuthenticatedPrincipal(ORGANIZER_ID), meeting
    )

    assert decision.resource_scope == f"meeting:{MEETING_ID}"
    assert decision.policy_version == "meeting-access.v1"
