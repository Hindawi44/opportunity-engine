"""Append-only persistence model for explicit human opportunity reviews."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utc_now


class HumanReviewOutcomeModel(Base):
    """One explicit reviewer decision for a canonical opportunity."""

    __tablename__ = "human_review_outcomes"
    __table_args__ = (
        UniqueConstraint("review_key", name="uq_human_review_outcomes_review_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_key: Mapped[str] = mapped_column(String(64), nullable=False)
    opportunity_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("unified_opportunities.opportunity_id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


Index(
    "ix_human_review_outcomes_opportunity_reviewed",
    HumanReviewOutcomeModel.opportunity_id,
    HumanReviewOutcomeModel.reviewed_at,
)
