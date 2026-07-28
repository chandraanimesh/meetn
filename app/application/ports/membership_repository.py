from abc import ABC, abstractmethod

from app.domain.entities.recording import Membership


class MembershipRepositoryPort(ABC):
    @abstractmethod
    async def get_by_user(self, user_id: str) -> Membership | None:
        """Load backend-trusted membership for one authenticated user."""

    @abstractmethod
    async def save(self, membership: Membership) -> Membership:
        """Create or replace a user's membership state."""
