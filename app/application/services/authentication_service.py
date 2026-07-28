import secrets
from typing import Tuple
from app.application.ports.identity_provider import IdentityProviderPort
from app.application.ports.user_repository import UserRepositoryPort
from app.application.ports.session_manager import SessionManagerPort
from app.domain.entities.user import User, ExternalIdentity

class AuthenticationService:
    def __init__(
        self, 
        identity_provider: IdentityProviderPort, 
        user_repository: UserRepositoryPort,
        session_manager: SessionManagerPort
    ):
        self.identity_provider = identity_provider
        self.user_repository = user_repository
        self.session_manager = session_manager

    def start_authentication(self) -> Tuple[str, str, str]:
        """
        Returns (authorization_url, state, nonce)
        """
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        url = self.identity_provider.get_authorization_url(state, nonce)
        return url, state, nonce

    async def handle_callback(self, code: str, expected_state: str, expected_nonce: str) -> dict:
        """
        Verifies callback, creates/updates user, returns cookie settings.
        """
        identity_data = await self.identity_provider.verify_callback(code, expected_state, expected_nonce)
        
        provider = "google"
        subject = identity_data["sub"]
        
        user = await self.user_repository.get_by_external_identity(provider, subject)
        
        if not user:
            # Create new user
            new_user = User(
                display_name=identity_data["name"] or identity_data["email"].split("@")[0],
                primary_email=identity_data["email"]
            )
            new_identity = ExternalIdentity(
                user_id=new_user.id,
                provider=provider,
                provider_subject=subject,
                provider_email=identity_data["email"],
                email_verified=identity_data["email_verified"]
            )
            user = await self.user_repository.create_user_with_identity(new_user, new_identity)
        else:
            # Update last authenticated
            identity = ExternalIdentity(
                user_id=user.id,
                provider=provider,
                provider_subject=subject,
                provider_email=identity_data["email"],
                email_verified=identity_data["email_verified"]
            )
            user = await self.user_repository.update_user_and_identity(user, identity)

        session = self.session_manager.create_session(user.id)
        cookie_settings = self.session_manager.create_jwt_cookie(session)
        return cookie_settings
