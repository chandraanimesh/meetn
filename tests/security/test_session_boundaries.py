from datetime import timedelta

from app.core.config import settings
from app.domain.entities.user import AuthSession
from app.domain.time import utc_now_naive
from app.infrastructure.auth.jwt_cookie_session import JWTCookieSessionManager
from tests.conftest import MeetingAPITestContext


def expired_token(user_id: str) -> str:
    now = utc_now_naive()
    session = AuthSession(
        user_id=user_id,
        jwt_id="expired-jwt-id",
        session_id="expired-session-id",
        issued_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        last_seen_at=now - timedelta(hours=2),
    )
    cookie = JWTCookieSessionManager(settings.session).create_jwt_cookie(session)
    return str(cookie["value"])


def test_missing_jwt_is_rejected_before_resource_access(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.clear_authentication()

    response = context.client.get(
        f"/api/meetings/{context.meeting_id}",
        headers={"X-Request-ID": "missing-session"},
    )

    assert response.status_code == 401
    assert context.audit_records() == []


def test_correctly_signed_expired_jwt_is_rejected_without_fabricating_actor(
    meeting_api_context: MeetingAPITestContext,
) -> None:
    context = meeting_api_context
    context.authenticate(expired_token(context.participant_id))

    response = context.client.get(
        f"/api/meetings/{context.meeting_id}",
        headers={"X-Request-ID": "expired-session"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Session expired"
    assert context.audit_records() == []

