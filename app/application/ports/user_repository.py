from abc import ABC, abstractmethod
from typing import Optional
from app.domain.entities.user import User, ExternalIdentity

class UserRepositoryPort(ABC):
    @abstractmethod
    async def get_by_external_identity(self, provider: str, subject: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def create_user_with_identity(self, user: User, identity: ExternalIdentity) -> User:
        pass

    @abstractmethod
    async def update_user_and_identity(self, user: User, identity: ExternalIdentity) -> User:
        pass
