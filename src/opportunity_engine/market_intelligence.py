"""Domain market-intelligence contracts built on the existing MarketSignal model."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from opportunity_engine.unified_models import Evidence, MarketSignal


class MarketSignalType(StrEnum):
    ITEM_LISTING = "ITEM_LISTING"
    AUCTION_EVENT = "AUCTION_EVENT"
    BUSINESS_CLOSURE = "BUSINESS_CLOSURE"
    INSOLVENCY_OR_LIQUIDATION = "INSOLVENCY_OR_LIQUIDATION"
    WAREHOUSE_SURPLUS = "WAREHOUSE_SURPLUS"
    REPEATED_SELLER_ACTIVITY = "REPEATED_SELLER_ACTIVITY"
    RELATED_INVENTORY_ACTIVITY = "RELATED_INVENTORY_ACTIVITY"


class MarketSignalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WATCH = "WATCH"
    CLOSED = "CLOSED"
    INVALID = "INVALID"


class MarketSignalRecord(MarketSignal):
    """One independently durable market signal.

    The class extends the existing lightweight ``MarketSignal`` contract rather
    than introducing a parallel generic event framework. A signal may reference
    an opportunity, but it does not need to become one.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    signal_id: str = Field(min_length=1, max_length=255)
    signal_type: MarketSignalType
    source: str = Field(min_length=1, max_length=200)
    source_country: str = Field(min_length=2, max_length=2)
    source_url: HttpUrl
    title: str = Field(min_length=1, max_length=1000)
    company_name: str | None = Field(default=None, max_length=500)
    seller_name: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    first_observed_at: datetime
    latest_observed_at: datetime
    event_date: datetime | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    related_opportunity_id: str | None = Field(default=None, max_length=255)
    status: MarketSignalStatus = MarketSignalStatus.WATCH
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_country")
    @classmethod
    def uppercase_country(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_observation_window(self) -> "MarketSignalRecord":
        if self.latest_observed_at < self.first_observed_at:
            raise ValueError("latest_observed_at cannot precede first_observed_at")
        return self
