from dataclasses import dataclass, field
import hashlib
from time import perf_counter
import re

from app.application.dto.multimodal import (
    MediaValidationCommand,
    MediaValidationResult,
)
from app.application.exceptions import (
    InvalidMediaRequestError,
    MediaTooLargeError,
    ResourceAccessDeniedError,
    UnsupportedMediaTypeError,
)
from app.application.ports.media_inspector import MediaInspectorPort
from app.application.services.audit_service import AuditService
from app.domain.policies.media_validation_policy import MediaValidationPolicy
from app.domain.value_objects.authorization_facts import AuthenticatedPrincipal
from app.domain.value_objects.media import (
    InputModality,
    MediaDescriptor,
)


CONVERSATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TYPE_FAILURE_REASONS = frozenset(
    {
        "unsupported_media_type",
        "actual_media_type_unknown",
        "mime_type_mismatch",
        "extension_mismatch",
        "modality_mismatch",
        "invalid_audio_container",
    }
)


@dataclass(slots=True)
class MediaValidationService:
    media_inspector: MediaInspectorPort
    audit_service: AuditService
    policy: MediaValidationPolicy = field(default_factory=MediaValidationPolicy)

    async def validate(
        self,
        *,
        principal: AuthenticatedPrincipal,
        command: MediaValidationCommand,
        request_id: str,
    ) -> MediaValidationResult:
        if not principal.is_active:
            raise ResourceAccessDeniedError(
                "MEDIA_ACCESS_DENIED",
                "You are not authorized to validate media",
            )
        if not CONVERSATION_ID_PATTERN.fullmatch(command.conversation_id):
            raise InvalidMediaRequestError(
                "INVALID_CONVERSATION_ID",
                "The conversation identifier is invalid",
            )

        started_at = perf_counter()
        media_hash = hashlib.sha256(command.content).hexdigest()
        declared_mime = (
            command.declared_mime.split(";", maxsplit=1)[0].strip().casefold()
        )
        inspection = self.media_inspector.inspect(command.content)
        input_modality = self._input_modality(inspection.detected_mime or declared_mime)
        descriptor = MediaDescriptor(
            filename=command.filename,
            declared_mime=declared_mime,
            detected_mime=inspection.detected_mime,
            size_bytes=len(command.content),
            duration_ms=inspection.duration_ms,
            input_modality=input_modality,
        )
        decision = self.policy.evaluate(descriptor)
        latency_ms = max(0, round((perf_counter() - started_at) * 1000))

        if not decision.allowed:
            await self._audit(
                request_id=request_id,
                principal=principal,
                command=command,
                descriptor=descriptor,
                media_hash=media_hash,
                latency_ms=latency_ms,
                status="rejected",
                error_code=decision.reason,
            )
            self._raise_validation_error(decision.reason)

        await self._audit(
            request_id=request_id,
            principal=principal,
            command=command,
            descriptor=descriptor,
            media_hash=media_hash,
            latency_ms=latency_ms,
            status="validated",
            error_code=None,
        )
        return MediaValidationResult(
            conversation_id=command.conversation_id,
            input_modality=descriptor.input_modality,
            media_hash=media_hash,
            media_type=descriptor.detected_mime or "unknown",
            media_size=descriptor.size_bytes,
            duration_ms=descriptor.duration_ms,
        )

    async def _audit(
        self,
        *,
        request_id: str,
        principal: AuthenticatedPrincipal,
        command: MediaValidationCommand,
        descriptor: MediaDescriptor,
        media_hash: str,
        latency_ms: int,
        status: str,
        error_code: str | None,
    ) -> None:
        await self.audit_service.record_multimodal_event(
            request_id=request_id,
            actor_user_id=principal.user_id,
            conversation_id=command.conversation_id,
            input_modality=descriptor.input_modality,
            media_hash=media_hash,
            media_type=descriptor.detected_mime,
            media_size=descriptor.size_bytes,
            provider="not_invoked",
            model_name="not_invoked",
            prompt_version=MediaValidationPolicy.VERSION,
            selected_action_id=None,
            resource_id=media_hash,
            authorization_allowed=True,
            authorization_reason="authenticated",
            entitlement_decision="not_applicable",
            tts_allowed=False,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
        )

    @staticmethod
    def _input_modality(mime_type: str) -> InputModality:
        if mime_type.startswith("image/"):
            return InputModality.IMAGE
        if mime_type.startswith("audio/"):
            return InputModality.AUDIO
        return InputModality.UNKNOWN

    @staticmethod
    def _raise_validation_error(reason: str) -> None:
        if reason == "media_too_large":
            raise MediaTooLargeError("Media exceeds the configured size limit")
        if reason in TYPE_FAILURE_REASONS:
            raise UnsupportedMediaTypeError(
                "Declared, detected, and filename media types must agree"
            )
        messages = {
            "invalid_filename": "The media filename is invalid",
            "empty_media": "Media content cannot be empty",
            "audio_duration_exceeded": "Audio duration exceeds the configured limit",
        }
        raise InvalidMediaRequestError(
            reason.upper(),
            messages.get(reason, "Media validation failed"),
        )
