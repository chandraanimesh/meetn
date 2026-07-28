from typing import Dict, Any
from app.application.ports.identity_provider import IdentityProviderPort
from app.core.exceptions import AppError

class FakeGoogleOIDCProvider(IdentityProviderPort):
    def __init__(self):
        self.expected_state = "test_state"
        self.expected_nonce = "test_nonce"
        self.mock_user_data = {
            "sub": "google-123",
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": True
        }
        self.should_fail = False

    def get_authorization_url(self, state: str, nonce: str) -> str:
        self.expected_state = state
        self.expected_nonce = nonce
        return f"http://fake.google.auth?state={state}&nonce={nonce}"

    async def verify_callback(self, code: str, expected_state: str, expected_nonce: str) -> Dict[str, Any]:
        if self.should_fail:
            raise AppError(code="auth_error", message="Mocked failure", status_code=401)
        if expected_state != self.expected_state:
            raise AppError(code="auth_error", message="Invalid state parameter", status_code=400)
        if expected_nonce != self.expected_nonce:
            raise AppError(code="auth_error", message="Invalid nonce", status_code=401)
            
        return self.mock_user_data
