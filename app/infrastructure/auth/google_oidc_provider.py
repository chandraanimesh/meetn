import httpx
import jwt
from typing import Dict, Any, Optional
from app.application.ports.identity_provider import IdentityProviderPort
from app.core.config import GoogleOIDCSettings
from app.core.exceptions import AppError

class GoogleOIDCProvider(IdentityProviderPort):
    def __init__(self, settings: GoogleOIDCSettings):
        self.settings = settings
        self.jwks: Optional[jwt.PyJWKClient] = None
        
    async def _fetch_discovery_document(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.settings.google_discovery_url)
            resp.raise_for_status()
            return resp.json()

    async def _fetch_jwks(self, jwks_uri: str) -> jwt.PyJWKClient:
        if not self.jwks:
            self.jwks = jwt.PyJWKClient(jwks_uri)
        return self.jwks

    def get_authorization_url(self, state: str, nonce: str) -> str:
        # Avoid blocking discovery on startup/start URL generation
        # We can hardcode the standard Google auth endpoint
        auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": self.settings.google_client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": self.settings.google_redirect_uri,
            "state": state,
            "nonce": nonce,
            "prompt": "select_account"
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{auth_endpoint}?{query}"

    async def verify_callback(self, code: str, expected_state: str, expected_nonce: str) -> Dict[str, Any]:
        discovery = await self._fetch_discovery_document()
        token_endpoint = discovery["token_endpoint"]
        jwks_uri = discovery["jwks_uri"]
        
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                token_endpoint,
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": self.settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            
            if token_resp.status_code != 200:
                raise AppError(code="auth_error", message="Failed to exchange code for token", status_code=401)
            
            token_data = token_resp.json()
            id_token = token_data.get("id_token")
            if not id_token:
                raise AppError(code="auth_error", message="No id_token found in response", status_code=401)

            jwks_client = await self._fetch_jwks(jwks_uri)
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)

            try:
                payload = jwt.decode(
                    id_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self.settings.google_client_id,
                    issuer="https://accounts.google.com"
                )
            except jwt.InvalidTokenError as e:
                raise AppError(code="auth_error", message=f"Invalid ID token: {str(e)}", status_code=401)

            if payload.get("nonce") != expected_nonce:
                raise AppError(code="auth_error", message="Invalid nonce", status_code=401)
            
            return {
                "sub": payload["sub"],
                "email": payload.get("email", ""),
                "name": payload.get("name", ""),
                "email_verified": payload.get("email_verified", False)
            }
