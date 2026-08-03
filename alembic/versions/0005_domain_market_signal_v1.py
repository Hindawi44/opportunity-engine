"""create durable domain market signal tables

Revision ID: 0005_domain_market_signal_v1
Revises: 0004_human_review_outcome_v1
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_domain_market_signal_v1"
down_revision: Union[str, None] = "0004_human_review_outcome_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("signal_id", sa.String(length=255), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("source_provider", sa.String(length=200), nullable=False),
        sa.Column("source_country", sa.String(length=2), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("seller_name", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("related_opportunity_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id", name="uq_market_signals_signal_id"),
    )
    op.create_index(
        "ix_market_signals_country_status",
        "market_signals",
        ["source_country", "status"],
        unique=False,
    )
    op.create_table(
        "market_signal_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("observation_key", sa.String(length=64), nullable=False),
        sa.Column("signal_id", sa.String(length=255), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["market_signals.signal_id"],
            name="fk_market_signal_observations_signal_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_key",
            name="uq_market_signal_observations_key",
        ),
    )
    op.create_index(
        "ix_market_signal_observations_signal_observed",
        "market_signal_observations",
        ["signal_id", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_signal_observations_signal_observed",
        table_name="market_signal_observations",
    )
    op.drop_table("market_signal_observations")
    op.drop_index("ix_market_signals_country_status", table_name="market_signals")
    op.drop_table("market_signals")
