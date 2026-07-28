from dataclasses import dataclass, field
from datetime import datetime

import pytest

from app.application.ports.audit_repository import AuditRepositoryPort
from app.application.services.audit_service import AuditService
from app.domain.entities.audit_event import AuditDecision, AuditEvent
from app.domain.time import utc_now_naive
from app.domain.value_objects.media import InputModality


@dataclass(slots=True)
class InMemoryAuditRepository(AuditRepositoryPort):
    events: list[AuditEvent] = field(default_factory=list)

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("allowed", "expected_decision"),
    [
        (True, AuditDecision.ALLOWED),
        (False, AuditDecision.DENIED),
    ],
)
async def test_audit_service_records_complete_security_event(
    allowed: bool,
    expected_decision: AuditDecision,
) -> None:
    repository = InMemoryAuditRepository()
    before = utc_now_naive()

    await AuditService(repository).record_resource_access(
        request_id="request-123",
        actor_user_id="user-123",
        event_type="transcript.read",
        action_id="transcript.read",
        resource_type="transcript",
        resource_id="meeting-123",
        allowed=allowed,
        reason="participant" if allowed else "not_authorized",
    )
    after = utc_now_naive()

    assert len(repository.events) == 1
    event = repository.events[0]
    assert event.actor_user_id == "user-123"
    assert event.event_type == "transcript.read"
    assert event.action_id == "transcript.read"
    assert event.resource_type == "transcript"
    assert event.resource_id == "meeting-123"
    assert event.authorization_decision is expected_decision
    assert event.decision_reason == ("participant" if allowed else "not_authorized")
    assert event.request_id == "request-123"
    assert isinstance(event.created_at, datetime)
    assert before <= event.created_at <= after


class FailingAuditRepository(AuditRepositoryPort):
    async def append(self, event: AuditEvent) -> None:
        raise RuntimeError("audit persistence unavailable")


@pytest.mark.asyncio
async def test_security_audit_failure_propagates_and_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="audit persistence unavailable"):
        await AuditService(FailingAuditRepository()).record_resource_access(
            request_id="request-failure",
            actor_user_id="user-123",
            event_type="confidential_notes.read",
            action_id="confidential_notes.read",
            resource_type="confidential_note_collection",
            resource_id="meeting-123",
            allowed=True,
            reason="explicit_user",
        )


@pytest.mark.asyncio
async def test_multimodal_audit_service_records_complete_metadata_schema() -> None:
    repository = InMemoryAuditRepository()

    await AuditService(repository).record_multimodal_event(
        request_id="request-media",
        actor_user_id="user-123",
        conversation_id="conversation-123",
        input_modality=InputModality.IMAGE,
        media_hash="a" * 64,
        media_type="image/png",
        media_size=128,
        provider="not_invoked",
        model_name="not_invoked",
        prompt_version="multimodal-media-validation.v1",
        selected_action_id=None,
        resource_id="a" * 64,
        authorization_allowed=True,
        authorization_reason="authenticated",
        entitlement_decision="not_applicable",
        tts_allowed=False,
        latency_ms=3,
        status="validated",
        error_code=None,
    )

    event = repository.events[0]
    assert event.request_id == "request-media"
    assert event.actor_user_id == "user-123"
    assert event.conversation_id == "conversation-123"
    assert event.input_modality is InputModality.IMAGE
    assert event.media_hash == "a" * 64
    assert event.media_type == "image/png"
    assert event.media_size == 128
    assert event.provider == "not_invoked"
    assert event.model_name == "not_invoked"
    assert event.prompt_version == "multimodal-media-validation.v1"
    assert event.selected_action_id is None
    assert event.resource_id == "a" * 64
    assert event.authorization_decision is AuditDecision.ALLOWED
    assert event.entitlement_decision == "not_applicable"
    assert event.tts_allowed is False
    assert event.latency_ms == 3
    assert event.status == "validated"
    assert event.error_code is None
