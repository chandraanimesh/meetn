import jwt
import secrets
import uuid
from datetime import timedelta
from app.application.ports.session_manager import SessionManagerPort
from app.domain.entities.user import AuthSession
from app.core.config import SessionSettings
from app.core.exceptions import AppError
from app.domain.time import utc_from_timestamp_naive, utc_now_naive

class JWTCookieSessionManager(SessionManagerPort):
    def __init__(self, settings: SessionSettings):
        self.settings = settings

    def create_session(self, user_id: str) -> AuthSession:
        now = utc_now_naive()
        expires = now + timedelta(seconds=self.settings.session_max_age_seconds)
        return AuthSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            jwt_id=str(uuid.uuid4()),
            csrf_token=secrets.token_urlsafe(32),
            issued_at=now,
            expires_at=expires,
            last_seen_at=now
        )

    def create_jwt_cookie(self, session: AuthSession) -> dict:
        payload = {
            "jti": session.jwt_id,
            "sub": session.user_id,
            "sid": session.session_id,
            "csrf": session.csrf_token,
            "iat": session.issued_at,
            "exp": session.expires_at,
        }
        token = jwt.encode(payload, self.settings.session_secret_key, algorithm="HS256")
        
        return {
            "key": "app_session",
            "value": token,
            "httponly": True,
            "secure": self.settings.cookie_secure,
            "samesite": "lax",
            "max_age": self.settings.session_max_age_seconds
        }

    def verify_session(self, jwt_token: str) -> AuthSession:
        try:
            payload = jwt.decode(
                jwt_token, 
                self.settings.session_secret_key, 
                algorithms=["HS256"],
                options={
                    "require": ["jti", "sub", "sid", "csrf", "iat", "exp"]
                },
            )
        except jwt.ExpiredSignatureError:
            raise AppError(code="auth_error", message="Session expired", status_code=401)
        except (jwt.InvalidTokenError, KeyError, TypeError):
            raise AppError(code="auth_error", message="Invalid session token", status_code=401)

        if not isinstance(payload["csrf"], str) or not payload["csrf"]:
            raise AppError(
                code="auth_error",
                message="Invalid session token",
                status_code=401,
            )
            
        return AuthSession(
            session_id=payload["sid"],
            user_id=payload["sub"],
            jwt_id=payload["jti"],
            csrf_token=payload["csrf"],
            issued_at=utc_from_timestamp_naive(payload["iat"]),
            expires_at=utc_from_timestamp_naive(payload["exp"])
        )
