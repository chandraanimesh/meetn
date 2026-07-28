from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.membership_repository import MembershipRepositoryPort
from app.domain.entities.recording import Membership
from app.infrastructure.database.models.recording import MembershipModel


class SQLAlchemyMembershipRepository(MembershipRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(self, user_id: str) -> Membership | None:
        result = await self.session.execute(
            select(MembershipModel).where(MembershipModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def save(self, membership: Membership) -> Membership:
        result = await self.session.execute(
            select(MembershipModel).where(
                MembershipModel.user_id == membership.user_id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = MembershipModel(
                id=membership.id,
                user_id=membership.user_id,
                plan=membership.plan,
                status=membership.status,
                valid_until=membership.valid_until,
                updated_at=membership.updated_at,
            )
            self.session.add(model)
        else:
            model.plan = membership.plan
            model.status = membership.status
            model.valid_until = membership.valid_until
            model.updated_at = membership.updated_at
        await self._commit()
        return self._to_entity(model)

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _to_entity(model: MembershipModel) -> Membership:
        return Membership(
            id=model.id,
            user_id=model.user_id,
            plan=model.plan,
            status=model.status,
            valid_until=model.valid_until,
            updated_at=model.updated_at,
        )
