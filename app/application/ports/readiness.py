from typing import Protocol


class ReadinessProbePort(Protocol):
    async def check(self) -> bool:
        """Return whether the required dependency is currently available."""

