from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from app.api.dependencies.auth import (
    get_auth_service,
    get_current_user,
    get_verified_session,
    require_csrf,
)
from app.application.services.authentication_service import AuthenticationService
from app.domain.entities.user import AuthSession, User
from app.api.schemas.auth import SessionResponse, UserSummary
from app.core.exceptions import AppError
from app.core.config import settings

router = APIRouter()

@router.get("/auth/google/start")
async def google_auth_start(
    request: Request,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    url, state, nonce = auth_service.start_authentication()
    
    response = RedirectResponse(url=url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.session.cookie_secure
    )
    response.set_cookie(
        key="oauth_nonce",
        value=nonce,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.session.cookie_secure
    )
    return response

@router.get("/auth/google/callback")
async def google_auth_callback(
    request: Request,
    code: str,
    state: str,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    expected_state = request.cookies.get("oauth_state")
    expected_nonce = request.cookies.get("oauth_nonce")
    
    if not expected_state or not expected_nonce:
        raise AppError(code="auth_error", message="Missing OAuth cookies", status_code=400)
        
    if state != expected_state:
        raise AppError(code="auth_error", message="Invalid state parameter", status_code=400)
        
    cookie_settings = await auth_service.handle_callback(code, expected_state, expected_nonce)
    
    response = RedirectResponse(url="/")
    response.set_cookie(
        key=cookie_settings["key"],
        value=cookie_settings["value"],
        httponly=cookie_settings["httponly"],
        max_age=cookie_settings["max_age"],
        samesite=cookie_settings["samesite"],
        secure=cookie_settings["secure"]
    )
    # Clear oauth cookies
    response.delete_cookie("oauth_state")
    response.delete_cookie("oauth_nonce")
    
    return response

@router.get("/session", response_model=SessionResponse)
async def get_session(
    response: Response,
    current_user: User = Depends(get_current_user),
    current_session: AuthSession = Depends(get_verified_session),
):
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        user=UserSummary(
            id=current_user.id,
            display_name=current_user.display_name,
            primary_email=current_user.primary_email,
            avatar_url=current_user.avatar_url,
        ),
        csrf_token=current_session.csrf_token,
    )

@router.post("/auth/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    csrf_valid: None = Depends(require_csrf),
):
    response = Response(status_code=204)
    response.delete_cookie("app_session")
    return response
