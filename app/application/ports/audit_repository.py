from abc import ABC, abstractmethod

from app.domain.entities.audit_event import AuditEvent


class AuditRepositoryPort(ABC):
    @abstractmethod
    async def append(self, event: AuditEvent) -> None:
        """Persist an immutable security event."""
