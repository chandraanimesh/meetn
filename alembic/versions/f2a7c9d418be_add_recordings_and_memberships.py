"""add recordings and memberships

Revision ID: f2a7c9d418be
Revises: c6b2a8d4e901
Create Date: 2026-07-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f2a7c9d418be"
down_revision: str | Sequence[str] | None = "c6b2a8d4e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


membership_plan = postgresql.ENUM(
    "STARTER",
    "PROFESSIONAL",
    "ORGANIZATION",
    name="membershipplan",
    create_type=False,
)
membership_status = postgresql.ENUM(
    "ACTIVE",
    "INACTIVE",
    name="membershipstatus",
    create_type=False,
)
recording_status = postgresql.ENUM(
    "PROCESSING",
    "AVAILABLE",
    name="recordingprocessingstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            "STARTER",
            "PROFESSIONAL",
            "ORGANIZATION",
            name="membershipplan",
        ).create(bind, checkfirst=True)
        postgresql.ENUM(
            "ACTIVE",
            "INACTIVE",
            name="membershipstatus",
        ).create(bind, checkfirst=True)
        postgresql.ENUM(
            "PROCESSING",
            "AVAILABLE",
            name="recordingprocessingstatus",
        ).create(bind, checkfirst=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("plan", membership_plan, nullable=False),
        sa.Column("status", membership_status, nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_memberships_plan_status",
        "memberships",
        ["plan", "status"],
    )

    op.create_table(
        "recordings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("processing_status", recording_status, nullable=False),
        sa.Column("required_plan", membership_plan, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meeting_id"], ["meetings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
    )
    op.create_index(
        "ix_recordings_status_required_plan",
        "recordings",
        ["processing_status", "required_plan"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recordings_status_required_plan",
        table_name="recordings",
    )
    op.drop_table("recordings")
    op.drop_index("ix_memberships_plan_status", table_name="memberships")
    op.drop_table("memberships")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        recording_status.drop(bind, checkfirst=True)
        membership_status.drop(bind, checkfirst=True)
        membership_plan.drop(bind, checkfirst=True)
