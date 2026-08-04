"""SQLAlchemy model for durable Swedish organisation identity watches."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, utc_now


class SwedenOrganisationWatchlistModel(Base):
    """One official Swedish organisation identity discovered from market evidence."""

    __tablename__ = "sweden_organisation_watchlist"

    organisation_number: Mapped[str] = mapped_column(String(10), primary_key=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_company_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_provider: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
