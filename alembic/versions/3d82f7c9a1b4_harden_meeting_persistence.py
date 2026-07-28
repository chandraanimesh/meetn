"""harden meeting persistence

Revision ID: 3d82f7c9a1b4
Revises: 816deb28a6af
Create Date: 2026-07-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "3d82f7c9a1b4"
down_revision: str | Sequence[str] | None = "816deb28a6af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEMBERSHIP_ENUM_NAME = "participantmembershipstatus"


def upgrade() -> None:
    membership_enum = postgresql.ENUM(
        "ACTIVE",
        "REMOVED",
        "REVOKED",
        name=MEMBERSHIP_ENUM_NAME,
    )
    membership_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "meeting_participants",
        sa.Column(
            "membership_status",
            postgresql.ENUM(
                "ACTIVE",
                "REMOVED",
                "REVOKED",
                name=MEMBERSHIP_ENUM_NAME,
                create_type=False,
            ),
            server_default="ACTIVE",
            nullable=False,
        ),
    )
    op.add_column(
        "meeting_participants",
        sa.Column("removed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "confidential_notes",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "confidential_note_access",
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_external_identities_provider_subject",
        "external_identities",
        ["provider", "provider_subject"],
    )
    op.create_unique_constraint(
        "uq_meeting_participants_meeting_user",
        "meeting_participants",
        ["meeting_id", "user_id"],
    )
    op.create_unique_constraint(
        "uq_confidential_note_access_note_user",
        "confidential_note_access",
        ["note_id", "user_id"],
    )

    op.create_index(
        "ix_meetings_created_by_start_time",
        "meetings",
        ["created_by", "start_time"],
    )
    op.create_index(
        "ix_meeting_participants_user_status_meeting",
        "meeting_participants",
        ["user_id", "membership_status", "meeting_id"],
    )
    op.create_index(
        "ix_confidential_notes_meeting_deleted",
        "confidential_notes",
        ["meeting_id", "deleted_at"],
    )
    op.create_index(
        "ix_confidential_note_access_user_revoked_note",
        "confidential_note_access",
        ["user_id", "revoked_at", "note_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_confidential_note_access_user_revoked_note",
        table_name="confidential_note_access",
    )
    op.drop_index(
        "ix_confidential_notes_meeting_deleted",
        table_name="confidential_notes",
    )
    op.drop_index(
        "ix_meeting_participants_user_status_meeting",
        table_name="meeting_participants",
    )
    op.drop_index("ix_meetings_created_by_start_time", table_name="meetings")

    op.drop_constraint(
        "uq_confidential_note_access_note_user",
        "confidential_note_access",
        type_="unique",
    )
    op.drop_constraint(
        "uq_meeting_participants_meeting_user",
        "meeting_participants",
        type_="unique",
    )
    op.drop_constraint(
        "uq_external_identities_provider_subject",
        "external_identities",
        type_="unique",
    )

    op.drop_column("confidential_note_access", "revoked_at")
    op.drop_column("confidential_notes", "deleted_at")
    op.drop_column("meeting_participants", "removed_at")
    op.drop_column("meeting_participants", "membership_status")

    postgresql.ENUM(name=MEMBERSHIP_ENUM_NAME).drop(
        op.get_bind(), checkfirst=True
    )
