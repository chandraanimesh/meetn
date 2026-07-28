"""add meeting scheduling fields

Revision ID: 9a4d2c7e6b10
Revises: f2a7c9d418be
Create Date: 2026-07-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "9a4d2c7e6b10"
down_revision: str | Sequence[str] | None = "f2a7c9d418be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEETING_STATUS_NAME = "meetingstatus"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            f"ALTER TYPE {MEETING_STATUS_NAME} "
            "ADD VALUE IF NOT EXISTS 'RESCHEDULED'"
        )

    op.add_column(
        "meetings",
        sa.Column("place", sa.String(length=255), server_default="", nullable=False),
    )
    op.add_column(
        "meetings",
        sa.Column("purpose", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "personal_gift",
            sa.String(length=255),
            server_default="",
            nullable=False,
        ),
    )
    if bind.dialect.name != "sqlite":
        op.alter_column("meetings", "place", server_default=None)
        op.alter_column("meetings", "purpose", server_default=None)
        op.alter_column("meetings", "personal_gift", server_default=None)


def downgrade() -> None:
    op.drop_column("meetings", "personal_gift")
    op.drop_column("meetings", "purpose")
    op.drop_column("meetings", "place")

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        "UPDATE meetings SET status = 'SCHEDULED' "
        "WHERE status::text = 'RESCHEDULED'"
    )
    op.execute(
        "ALTER TABLE meetings ALTER COLUMN status TYPE VARCHAR "
        "USING status::text"
    )
    postgresql.ENUM(name=MEETING_STATUS_NAME).drop(bind, checkfirst=True)
    replacement = postgresql.ENUM(
        "SCHEDULED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
        name=MEETING_STATUS_NAME,
    )
    replacement.create(bind, checkfirst=True)
    op.execute(
        "ALTER TABLE meetings ALTER COLUMN status TYPE meetingstatus "
        "USING status::meetingstatus"
    )
