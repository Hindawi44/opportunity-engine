"""create isolated unified opportunity persistence tables

Revision ID: 0002_unified_opportunity_v1
Revises: 0001_persistence_foundation_v1
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_unified_opportunity_v1"
down_revision: Union[str, None] = "0001_persistence_foundation_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unified_opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.String(length=255), nullable=False),
        sa.Column("market_code", sa.String(length=2), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_provider", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("listing_status", sa.String(length=32), nullable=False),
        sa.Column("evaluation_status", sa.String(length=32), nullable=False),
        sa.Column("workflow_status", sa.String(length=64), nullable=False),
        sa.Column("scenario", sa.String(length=100), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("inventory_type", sa.String(length=200), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("bid_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("identity_stable", sa.Boolean(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("analysis_eligible", sa.Boolean(), nullable=False),
        sa.Column("top5_eligible", sa.Boolean(), nullable=False),
        sa.Column("record_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            name="uq_unified_opportunities_opportunity_id",
        ),
    )
    op.create_index(
        "ix_unified_opportunities_workflow",
        "unified_opportunities",
        ["workflow_status"],
        unique=False,
    )

    op.create_table(
        "unified_opportunity_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.String(length=255), nullable=False),
        sa.Column("evidence_key", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["unified_opportunities.opportunity_id"],
            name="fk_unified_evidence_opportunity_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opportunity_id",
            "evidence_key",
            name="uq_unified_evidence_opportunity_key",
        ),
    )
    op.create_index(
        "ix_unified_evidence_opportunity",
        "unified_opportunity_evidence",
        ["opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_unified_evidence_opportunity",
        table_name="unified_opportunity_evidence",
    )
    op.drop_table("unified_opportunity_evidence")
    op.drop_index(
        "ix_unified_opportunities_workflow",
        table_name="unified_opportunities",
    )
    op.drop_table("unified_opportunities")
