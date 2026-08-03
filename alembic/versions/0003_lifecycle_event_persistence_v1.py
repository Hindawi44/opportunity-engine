"""create append-only lifecycle event table

Revision ID: 0003_lifecycle_event_persistence_v1
Revises: 0002_unified_opportunity_v1
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_lifecycle_event_persistence_v1"
down_revision: Union[str, None] = "0002_unified_opportunity_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lifecycle_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=255), nullable=False),
        sa.Column("from_listing_status", sa.String(length=32), nullable=True),
        sa.Column("to_listing_status", sa.String(length=32), nullable=False),
        sa.Column("from_evaluation_status", sa.String(length=32), nullable=True),
        sa.Column("to_evaluation_status", sa.String(length=32), nullable=False),
        sa.Column("from_workflow_status", sa.String(length=64), nullable=True),
        sa.Column("to_workflow_status", sa.String(length=64), nullable=False),
        sa.Column("from_reason_code", sa.String(length=128), nullable=True),
        sa.Column("to_reason_code", sa.String(length=128), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["unified_opportunities.opportunity_id"],
            name="fk_lifecycle_events_opportunity_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_lifecycle_events_event_key"),
    )
    op.create_index(
        "ix_lifecycle_events_opportunity_changed",
        "lifecycle_events",
        ["opportunity_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lifecycle_events_opportunity_changed",
        table_name="lifecycle_events",
    )
    op.drop_table("lifecycle_events")
