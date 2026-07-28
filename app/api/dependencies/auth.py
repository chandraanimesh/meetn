import secrets

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.api.dependencies.database import get_db_session
from app.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository
from app.infrastructure.auth.jwt_cookie_session import JWTCookieSessionManager
from app.infrastructure.auth.google_oidc_provider import GoogleOIDCProvider
from app.application.services.authentication_service import AuthenticationService
from app.domain.entities.user import AuthSession, User
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal
from app.core.request_context import set_authenticated_user_id

def get_session_manager() -> JWTCookieSessionManager:
    return JWTCookieSessionManager(settings.session)

def get_identity_provider() -> GoogleOIDCProvider:
    return GoogleOIDCProvider(settings.oidc)

def get_user_repository(session: AsyncSession = Depends(get_db_session)) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)

def get_auth_service(
    identity_provider: GoogleOIDCProvider = Depends(get_identity_provider),
    user_repository: SQLAlchemyUserRepository = Depends(get_user_repository),
    session_manager: JWTCookieSessionManager = Depends(get_session_manager),
) -> AuthenticationService:
    return AuthenticationService(
        identity_provider=identity_provider,
        user_repository=user_repository,
        session_manager=session_manager
    )

def get_verified_session(
    request: Request,
    session_manager: JWTCookieSessionManager = Depends(get_session_manager),
) -> AuthSession:
    token = request.cookies.get("app_session")
    if not token:
        raise AppError(code="auth_error", message="Authentication required", status_code=401)

    session = session_manager.verify_session(token)
    if not session.is_active:
        raise AppError(code="auth_error", message="Session is inactive or expired", status_code=401)

    return session


async def get_current_user(
    session: AuthSession = Depends(get_verified_session),
    user_repository: SQLAlchemyUserRepository = Depends(get_user_repository),
) -> User:
    user = await user_repository.get_by_id(session.user_id)
    if not user or not user.is_active:
        raise AppError(code="auth_error", message="User not found or inactive", status_code=401)
        
    set_authenticated_user_id(user.id)
    return user


def require_csrf(
    session: AuthSession = Depends(get_verified_session),
    csrf_token: Annotated[
        str | None, Header(alias="X-CSRF-Token")
    ] = None,
) -> None:
    if (
        not csrf_token
        or not session.csrf_token
        or not secrets.compare_digest(csrf_token, session.csrf_token)
    ):
        raise AppError(
            code="CSRF_VALIDATION_FAILED",
            message="The CSRF token is missing or invalid",
            status_code=403,
        )


async def get_authenticated_principal(
    current_user: User = Depends(get_current_user),
) -> AuthenticatedPrincipal:
    """Build a principal only after JWT verification and server-side user loading."""
    return AuthenticatedPrincipal(
        user_id=current_user.id,
        is_active=current_user.is_active,
    )
