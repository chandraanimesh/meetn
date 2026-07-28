from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
import uuid
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.infrastructure.database.models.user import UserModel

from app.infrastructure.database.base import Base
from app.domain.time import utc_now_naive
from app.domain.entities.meeting import (
    MeetingStatus,
    ParticipantMembershipStatus,
    ParticipantRole,
)

class MeetingModel(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_created_by_start_time", "created_by", "start_time"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[MeetingStatus] = mapped_column(SQLEnum(MeetingStatus), default=MeetingStatus.SCHEDULED, nullable=False)
    place: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    personal_gift: Mapped[str] = mapped_column(
        String(255), default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)

    # Relationships
    creator: Mapped["UserModel"] = relationship(foreign_keys=[created_by])
    participants: Mapped[List["MeetingParticipantModel"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")
    transcript: Mapped[Optional["TranscriptModel"]] = relationship(back_populates="meeting", cascade="all, delete-orphan", uselist=False)
    confidential_notes: Mapped[List["ConfidentialNoteModel"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")


class MeetingParticipantModel(Base):
    __tablename__ = "meeting_participants"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id", "user_id", name="uq_meeting_participants_meeting_user"
        ),
        Index(
            "ix_meeting_participants_user_status_meeting",
            "user_id",
            "membership_status",
            "meeting_id",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    role: Mapped[ParticipantRole] = mapped_column(SQLEnum(ParticipantRole), nullable=False)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    membership_status: Mapped[ParticipantMembershipStatus] = mapped_column(
        SQLEnum(
            ParticipantMembershipStatus,
            name="participantmembershipstatus",
        ),
        default=ParticipantMembershipStatus.ACTIVE,
        server_default="ACTIVE",
        nullable=False,
    )
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    meeting: Mapped["MeetingModel"] = relationship(back_populates="participants")
    user: Mapped["UserModel"] = relationship()


class TranscriptModel(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)

    # Relationships
    meeting: Mapped["MeetingModel"] = relationship(back_populates="transcript")


class ConfidentialNoteModel(Base):
    __tablename__ = "confidential_notes"
    __table_args__ = (
        Index(
            "ix_confidential_notes_meeting_deleted",
            "meeting_id",
            "deleted_at",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    meeting: Mapped["MeetingModel"] = relationship(back_populates="confidential_notes")
    creator: Mapped["UserModel"] = relationship()
    access_list: Mapped[List["ConfidentialNoteAccessModel"]] = relationship(back_populates="note", cascade="all, delete-orphan")


class ConfidentialNoteAccessModel(Base):
    __tablename__ = "confidential_note_access"
    __table_args__ = (
        UniqueConstraint(
            "note_id", "user_id", name="uq_confidential_note_access_note_user"
        ),
        Index(
            "ix_confidential_note_access_user_revoked_note",
            "user_id",
            "revoked_at",
            "note_id",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id: Mapped[str] = mapped_column(String, ForeignKey("confidential_notes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    granted_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    note: Mapped["ConfidentialNoteModel"] = relationship(back_populates="access_list")
    user: Mapped["UserModel"] = relationship(foreign_keys=[user_id])
    granter: Mapped["UserModel"] = relationship(foreign_keys=[granted_by])
