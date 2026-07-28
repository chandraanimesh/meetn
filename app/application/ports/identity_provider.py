from abc import ABC, abstractmethod
from typing import Dict, Any

class IdentityProviderPort(ABC):
    @abstractmethod
    def get_authorization_url(self, state: str, nonce: str) -> str:
        pass

    @abstractmethod
    async def verify_callback(self, code: str, expected_state: str, expected_nonce: str) -> Dict[str, Any]:
        """
        Exchanges code for tokens, validates ID token signature, issuer, audience, nonce.
        Returns the parsed identity (at least 'sub', 'email', 'name').
        """
        pass
