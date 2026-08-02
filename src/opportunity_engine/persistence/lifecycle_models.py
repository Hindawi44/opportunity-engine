"""SQLAlchemy model for append-only opportunity lifecycle transitions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utc_now


class LifecycleEventModel(Base):
    """One append-only change across the canonical lifecycle state vector."""

    __tablename__ = "lifecycle_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_lifecycle_events_event_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    opportunity_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("unified_opportunities.opportunity_id", ondelete="CASCADE"),
        nullable=False,
    )

    from_listing_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_listing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    from_evaluation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_evaluation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    from_workflow_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_workflow_status: Mapped[str] = mapped_column(String(64), nullable=False)
    from_reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    to_reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)

    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


Index(
    "ix_lifecycle_events_opportunity_changed",
    LifecycleEventModel.opportunity_id,
    LifecycleEventModel.changed_at,
)
