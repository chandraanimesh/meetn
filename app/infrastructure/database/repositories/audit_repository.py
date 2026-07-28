from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.audit_repository import AuditRepositoryPort
from app.domain.entities.audit_event import AuditEvent
from app.infrastructure.database.models.audit_event import AuditEventModel


class SQLAlchemyAuditRepository(AuditRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, event: AuditEvent) -> None:
        self.session.add(
            AuditEventModel(
                id=event.id,
                request_id=event.request_id,
                actor_user_id=event.actor_user_id,
                event_type=event.event_type,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                action_id=event.action_id,
                authorization_decision=event.authorization_decision.value,
                decision_reason=event.decision_reason,
                conversation_id=event.conversation_id,
                input_modality=(
                    event.input_modality.value
                    if event.input_modality is not None
                    else None
                ),
                media_hash=event.media_hash,
                media_type=event.media_type,
                media_size=event.media_size,
                provider=event.provider,
                model_name=event.model_name,
                prompt_version=event.prompt_version,
                selected_action_id=event.selected_action_id,
                entitlement_decision=event.entitlement_decision,
                tts_allowed=event.tts_allowed,
                latency_ms=event.latency_ms,
                status=event.status,
                error_code=event.error_code,
                created_at=event.created_at,
            )
        )
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
