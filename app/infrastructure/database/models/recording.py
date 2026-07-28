from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.recording import (
    MembershipPlan,
    MembershipStatus,
    RecordingProcessingStatus,
)
from app.domain.time import utc_now_naive
from app.infrastructure.database.base import Base


class RecordingModel(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        Index(
            "ix_recordings_status_required_plan",
            "processing_status",
            "required_plan",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    processing_status: Mapped[RecordingProcessingStatus] = mapped_column(
        SQLEnum(
            RecordingProcessingStatus,
            name="recordingprocessingstatus",
        ),
        nullable=False,
    )
    required_plan: Mapped[MembershipPlan] = mapped_column(
        SQLEnum(MembershipPlan, name="membershipplan"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )


class MembershipModel(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        Index("ix_memberships_plan_status", "plan", "status"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan: Mapped[MembershipPlan] = mapped_column(
        SQLEnum(MembershipPlan, name="membershipplan"),
        nullable=False,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        SQLEnum(MembershipStatus, name="membershipstatus"),
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
