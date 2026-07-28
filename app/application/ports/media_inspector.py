from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaInspection:
    detected_mime: str | None
    duration_ms: int | None = None


class MediaInspectorPort(ABC):
    @abstractmethod
    def inspect(self, content: bytes) -> MediaInspection:
        """Inspect bounded in-memory media without persisting its content."""
