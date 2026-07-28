from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.recording_repository import RecordingRepositoryPort
from app.domain.entities.recording import Recording
from app.infrastructure.database.models.recording import RecordingModel


class SQLAlchemyRecordingRepository(RecordingRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_meeting(self, meeting_id: str) -> Recording | None:
        result = await self.session.execute(
            select(RecordingModel).where(RecordingModel.meeting_id == meeting_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def save(self, recording: Recording) -> Recording:
        result = await self.session.execute(
            select(RecordingModel).where(
                RecordingModel.meeting_id == recording.meeting_id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = RecordingModel(
                id=recording.id,
                meeting_id=recording.meeting_id,
                processing_status=recording.processing_status,
                required_plan=recording.required_plan,
                created_at=recording.created_at,
            )
            self.session.add(model)
        else:
            model.processing_status = recording.processing_status
            model.required_plan = recording.required_plan
        await self._commit()
        return self._to_entity(model)

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _to_entity(model: RecordingModel) -> Recording:
        return Recording(
            id=model.id,
            meeting_id=model.meeting_id,
            processing_status=model.processing_status,
            required_plan=model.required_plan,
            created_at=model.created_at,
        )
