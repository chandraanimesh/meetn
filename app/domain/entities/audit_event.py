from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

from app.domain.time import utc_now_naive
from app.domain.value_objects.media import InputModality


class AuditDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    request_id: str
    actor_user_id: str
    event_type: str
    resource_type: str
    resource_id: str
    authorization_decision: AuditDecision
    decision_reason: str
    action_id: str | None = None
    conversation_id: str | None = None
    input_modality: InputModality | None = None
    media_hash: str | None = None
    media_type: str | None = None
    media_size: int | None = None
    provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    selected_action_id: str | None = None
    entitlement_decision: str | None = None
    tts_allowed: bool | None = None
    latency_ms: int | None = None
    status: str | None = None
    error_code: str | None = None
    created_at: datetime = field(default_factory=utc_now_naive)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.media_hash is not None and (
            len(self.media_hash) != 64
            or any(character not in "0123456789abcdef" for character in self.media_hash)
        ):
            raise ValueError("media_hash must be a lowercase SHA-256 digest")
        if self.media_size is not None and self.media_size < 0:
            raise ValueError("media_size cannot be negative")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
