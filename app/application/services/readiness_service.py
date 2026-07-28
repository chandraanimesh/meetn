from dataclasses import dataclass

from app.application.ports.readiness import ReadinessProbePort


@dataclass(frozen=True, slots=True)
class ReadinessService:
    database_probe: ReadinessProbePort

    async def is_ready(self) -> bool:
        return await self.database_probe.check()
