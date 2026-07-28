from dataclasses import dataclass

from app.application.ports.audit_repository import AuditRepositoryPort
from app.domain.entities.audit_event import AuditDecision, AuditEvent
from app.domain.value_objects.media import InputModality


@dataclass(slots=True)
class AuditService:
    repository: AuditRepositoryPort

    async def record_resource_access(
        self,
        *,
        request_id: str,
        actor_user_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        allowed: bool,
        reason: str,
        action_id: str | None = None,
    ) -> None:
        event = AuditEvent(
            request_id=request_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action_id=action_id,
            authorization_decision=(
                AuditDecision.ALLOWED if allowed else AuditDecision.DENIED
            ),
            decision_reason=reason,
        )
        await self.repository.append(event)

    async def record_multimodal_event(
        self,
        *,
        request_id: str,
        actor_user_id: str,
        conversation_id: str,
        input_modality: InputModality,
        media_hash: str,
        media_type: str | None,
        media_size: int,
        provider: str,
        model_name: str,
        prompt_version: str,
        selected_action_id: str | None,
        resource_id: str,
        authorization_allowed: bool,
        authorization_reason: str,
        entitlement_decision: str,
        tts_allowed: bool,
        latency_ms: int,
        status: str,
        error_code: str | None,
    ) -> None:
        event = AuditEvent(
            request_id=request_id,
            actor_user_id=actor_user_id,
            event_type=(
                "multimodal_media_validated"
                if status == "validated"
                else "multimodal_media_rejected"
            ),
            resource_type="media",
            resource_id=resource_id,
            action_id=selected_action_id,
            authorization_decision=(
                AuditDecision.ALLOWED if authorization_allowed else AuditDecision.DENIED
            ),
            decision_reason=authorization_reason,
            conversation_id=conversation_id,
            input_modality=input_modality,
            media_hash=media_hash,
            media_type=media_type,
            media_size=media_size,
            provider=provider,
            model_name=model_name,
            prompt_version=prompt_version,
            selected_action_id=selected_action_id,
            entitlement_decision=entitlement_decision,
            tts_allowed=tts_allowed,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
        )
        await self.repository.append(event)
