"""SQLAlchemy models for durable market signals and changed observations."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .models import Base, utc_now


class MarketSignalModel(Base):
    """Latest known snapshot for one stable domain market signal."""

    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(200), nullable=False)
    source_country: Mapped[str] = mapped_column(String(2), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    related_opportunity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    observations: Mapped[list[MarketSignalObservationModel]] = relationship(
        back_populates="signal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MarketSignalObservationModel(Base):
    """Append-only observation created only when signal evidence or state changes."""

    __tablename__ = "market_signal_observations"
    __table_args__ = (
        UniqueConstraint("observation_key", name="uq_market_signal_observations_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("market_signals.signal_id", ondelete="CASCADE"),
        nullable=False,
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    signal: Mapped[MarketSignalModel] = relationship(back_populates="observations")


Index("ix_market_signals_country_status", MarketSignalModel.source_country, MarketSignalModel.status)
Index(
    "ix_market_signal_observations_signal_observed",
    MarketSignalObservationModel.signal_id,
    MarketSignalObservationModel.observed_at,
)
