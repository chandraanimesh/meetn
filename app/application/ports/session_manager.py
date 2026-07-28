from abc import ABC, abstractmethod
from app.domain.entities.user import AuthSession

class SessionManagerPort(ABC):
    @abstractmethod
    def create_session(self, user_id: str) -> AuthSession:
        pass

    @abstractmethod
    def create_jwt_cookie(self, session: AuthSession) -> dict:
        """
        Returns cookie settings like {"key": "app_session", "value": "<jwt>", "httponly": True, "secure": True, ...}
        """
        pass

    @abstractmethod
    def verify_session(self, jwt_token: str) -> AuthSession:
        """
        Parses and verifies the JWT. Returns the AuthSession object.
        Raises domain/application exception on invalid or expired token.
        """
        pass
