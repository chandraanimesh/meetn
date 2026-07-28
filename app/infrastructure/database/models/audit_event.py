from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.time import utc_now_naive
from app.infrastructure.database.base import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_request_id", "request_id"),
        Index("ix_audit_events_actor_created", "actor_user_id", "created_at"),
        Index(
            "ix_audit_events_resource_created",
            "resource_type",
            "resource_id",
            "created_at",
        ),
        Index("ix_audit_events_media_hash", "media_hash"),
        Index(
            "ix_audit_events_conversation_created",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    action_id: Mapped[str | None] = mapped_column(String, nullable=True)
    authorization_decision: Mapped[str] = mapped_column(String, nullable=False)
    decision_reason: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    input_modality: Mapped[str | None] = mapped_column(String, nullable=True)
    media_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)
    media_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_action_id: Mapped[str | None] = mapped_column(String, nullable=True)
    entitlement_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    tts_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
