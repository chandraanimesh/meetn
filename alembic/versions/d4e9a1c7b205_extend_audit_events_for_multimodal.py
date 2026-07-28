"""extend audit events for multimodal security metadata

Revision ID: d4e9a1c7b205
Revises: 9a4d2c7e6b10
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d4e9a1c7b205"
down_revision: str | Sequence[str] | None = "9a4d2c7e6b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_events", sa.Column("conversation_id", sa.String(), nullable=True)
    )
    op.add_column(
        "audit_events", sa.Column("input_modality", sa.String(), nullable=True)
    )
    op.add_column(
        "audit_events", sa.Column("media_hash", sa.String(length=64), nullable=True)
    )
    op.add_column("audit_events", sa.Column("media_type", sa.String(), nullable=True))
    op.add_column(
        "audit_events", sa.Column("media_size", sa.BigInteger(), nullable=True)
    )
    op.add_column("audit_events", sa.Column("provider", sa.String(), nullable=True))
    op.add_column("audit_events", sa.Column("model_name", sa.String(), nullable=True))
    op.add_column(
        "audit_events", sa.Column("prompt_version", sa.String(), nullable=True)
    )
    op.add_column(
        "audit_events", sa.Column("selected_action_id", sa.String(), nullable=True)
    )
    op.add_column(
        "audit_events",
        sa.Column("entitlement_decision", sa.String(), nullable=True),
    )
    op.add_column("audit_events", sa.Column("tts_allowed", sa.Boolean(), nullable=True))
    op.add_column("audit_events", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("audit_events", sa.Column("status", sa.String(), nullable=True))
    op.add_column("audit_events", sa.Column("error_code", sa.String(), nullable=True))
    op.create_index(
        "ix_audit_events_media_hash",
        "audit_events",
        ["media_hash"],
    )
    op.create_index(
        "ix_audit_events_conversation_created",
        "audit_events",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_events_conversation_created",
        table_name="audit_events",
    )
    op.drop_index("ix_audit_events_media_hash", table_name="audit_events")
    for column_name in (
        "error_code",
        "status",
        "latency_ms",
        "tts_allowed",
        "entitlement_decision",
        "selected_action_id",
        "prompt_version",
        "model_name",
        "provider",
        "media_size",
        "media_type",
        "media_hash",
        "input_modality",
        "conversation_id",
    ):
        op.drop_column("audit_events", column_name)
