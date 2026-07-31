"""create persistence foundation v1

Revision ID: 0001_persistence_foundation_v1
Revises:
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_persistence_foundation_v1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("market_code", sa.String(length=2), nullable=True),
        sa.Column("final_decision", sa.String(length=64), nullable=True),
        sa.Column("opportunity_score", sa.Float(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id", name="uq_opportunities_opportunity_id"),
    )

    op.create_table(
        "shipment_evidence_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column("opportunity_id", sa.String(length=255), nullable=False),
        sa.Column("task_type", sa.String(length=128), nullable=False),
        sa.Column("requested_fields_json", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_channel", sa.String(length=64), nullable=False),
        sa.Column("question_nb", sa.Text(), nullable=False),
        sa.Column("question_ar", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("current_value_json", sa.JSON(), nullable=True),
        sa.Column("blocks_manual_quote", sa.Boolean(), nullable=False),
        sa.Column("blocks_qualification", sa.Boolean(), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["opportunities.opportunity_id"],
            name="fk_shipment_tasks_opportunity_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_shipment_evidence_tasks_task_id"),
    )
    op.create_index(
        "ix_shipment_tasks_opportunity",
        "shipment_evidence_tasks",
        ["opportunity_id"],
        unique=False,
    )

    op.create_table(
        "status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("from_status", sa.String(length=64), nullable=True),
        sa.Column("to_status", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_status_history_entity",
        "status_history",
        ["entity_type", "entity_key"],
        unique=False,
    )

    op.create_table(
        "source_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("pipeline_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("zero_result", sa.Boolean(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_source_runs_run_id"),
    )
    op.create_index(
        "ix_source_runs_pipeline_started",
        "source_runs",
        ["pipeline_name", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_source_runs_pipeline_started", table_name="source_runs")
    op.drop_table("source_runs")
    op.drop_index("ix_status_history_entity", table_name="status_history")
    op.drop_table("status_history")
    op.drop_index("ix_shipment_tasks_opportunity", table_name="shipment_evidence_tasks")
    op.drop_table("shipment_evidence_tasks")
    op.drop_table("opportunities")
