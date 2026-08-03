"""create append-only human review outcome table

Revision ID: 0004_human_review_outcome_v1
Revises: 0003_lifecycle_event_persistence_v1
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_human_review_outcome_v1"
down_revision: Union[str, None] = "0003_lifecycle_event_persistence_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "human_review_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_key", sa.String(length=64), nullable=False),
        sa.Column("opportunity_id", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("reviewer", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["unified_opportunities.opportunity_id"],
            name="fk_human_review_outcomes_opportunity_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_key", name="uq_human_review_outcomes_review_key"),
    )
    op.create_index(
        "ix_human_review_outcomes_opportunity_reviewed",
        "human_review_outcomes",
        ["opportunity_id", "reviewed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_human_review_outcomes_opportunity_reviewed",
        table_name="human_review_outcomes",
    )
    op.drop_table("human_review_outcomes")
