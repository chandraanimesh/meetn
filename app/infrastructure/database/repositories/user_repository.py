from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.domain.entities.user import User, ExternalIdentity
from app.application.ports.user_repository import UserRepositoryPort
from app.infrastructure.database.models.user import UserModel, ExternalIdentityModel

class SQLAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_user_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            display_name=model.display_name,
            primary_email=model.primary_email,
            avatar_url=model.avatar_url,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_user_model(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            display_name=entity.display_name,
            primary_email=entity.primary_email,
            avatar_url=entity.avatar_url,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
        
    def _to_identity_model(self, entity: ExternalIdentity) -> ExternalIdentityModel:
        return ExternalIdentityModel(
            id=entity.id,
            user_id=entity.user_id,
            provider=entity.provider,
            provider_subject=entity.provider_subject,
            provider_email=entity.provider_email,
            email_verified=entity.email_verified,
            last_authenticated_at=entity.last_authenticated_at
        )

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def get_by_external_identity(self, provider: str, subject: str) -> Optional[User]:
        stmt = select(ExternalIdentityModel).options(selectinload(ExternalIdentityModel.user)).filter_by(
            provider=provider, provider_subject=subject
        )
        result = await self.session.execute(stmt)
        identity = result.scalar_one_or_none()
        if identity and identity.user:
            return self._to_user_entity(identity.user)
        return None

    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(UserModel).filter_by(id=user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return self._to_user_entity(user)
        return None

    async def create_user_with_identity(self, user: User, identity: ExternalIdentity) -> User:
        identity.user_id = user.id
        user_model = self._to_user_model(user)
        identity_model = self._to_identity_model(identity)
        
        self.session.add(user_model)
        self.session.add(identity_model)
        await self._commit()
        return self._to_user_entity(user_model)

    async def update_user_and_identity(self, user: User, identity: ExternalIdentity) -> User:
        user_model = await self.session.get(UserModel, user.id)
        if user_model:
            user_model.display_name = user.display_name
            user_model.primary_email = user.primary_email
            user_model.avatar_url = user.avatar_url
            user_model.is_active = user.is_active
            
        stmt = select(ExternalIdentityModel).filter_by(
            provider=identity.provider, provider_subject=identity.provider_subject
        )
        result = await self.session.execute(stmt)
        identity_model = result.scalar_one_or_none()
        
        if identity_model:
            identity_model.last_authenticated_at = identity.last_authenticated_at
            identity_model.email_verified = identity.email_verified
        else:
            self.session.add(self._to_identity_model(identity))

        await self._commit()
        return user
