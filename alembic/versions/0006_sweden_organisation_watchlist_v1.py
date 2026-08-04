"""create durable Swedish organisation watchlist

Revision ID: 0006_sweden_organisation_watchlist_v1
Revises: 0005_domain_market_signal_v1
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_sweden_organisation_watchlist_v1"
down_revision: Union[str, None] = "0005_domain_market_signal_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sweden_organisation_watchlist",
        sa.Column("organisation_number", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("artifact_company_name", sa.Text(), nullable=False),
        sa.Column("source_provider", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("organisation_number"),
    )


def downgrade() -> None:
    op.drop_table("sweden_organisation_watchlist")
