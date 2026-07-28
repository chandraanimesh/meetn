from abc import ABC, abstractmethod

from app.domain.entities.recording import Recording


class RecordingRepositoryPort(ABC):
    @abstractmethod
    async def get_by_meeting(self, meeting_id: str) -> Recording | None:
        """Load recording state without exposing recording content."""

    @abstractmethod
    async def save(self, recording: Recording) -> Recording:
        """Create or update the single recording state for a meeting."""
