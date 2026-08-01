"""Canonical opportunity lifecycle models.

These models provide one validated shape for opportunities produced by different
collectors. They intentionally do not include persistence, API, or financial
analysis concerns.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class ListingStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    SOLD = "SOLD"
    UNAVAILABLE = "UNAVAILABLE"


class EvaluationStatus(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"


class WorkflowStatus(StrEnum):
    EARLY_SIGNAL = "EARLY_SIGNAL"
    CANDIDATE = "CANDIDATE"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    ACTIVE_OPPORTUNITY = "ACTIVE_OPPORTUNITY"
    QUALIFIED_OPPORTUNITY = "QUALIFIED_OPPORTUNITY"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class MarketSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    signal_type: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)
    source: str | None = Field(default=None, max_length=200)
    observed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_type: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    captured_at: datetime | None = None
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class MissingInformation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_name: str = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=500)
    required_for: str | None = Field(default=None, max_length=200)


class OpportunityRecord(BaseModel):
    """One source-independent opportunity record.

    Unknown public facts remain ``None``. The model never estimates missing
    quantity, price, location, or dates.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    opportunity_id: str = Field(min_length=1, max_length=250)
    market_code: str = Field(min_length=2, max_length=2)
    domain: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=1000)

    source_provider: str = Field(min_length=1, max_length=200)
    source_url: HttpUrl

    listing_status: ListingStatus = ListingStatus.UNKNOWN
    evaluation_status: EvaluationStatus = EvaluationStatus.NOT_EVALUATED
    workflow_status: WorkflowStatus = WorkflowStatus.CANDIDATE

    scenario: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    inventory_type: str | None = Field(default=None, max_length=200)
    currency: str = Field(default="NOK", min_length=3, max_length=3)
    price: float | None = Field(default=None, ge=0)
    bid_price: float | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=1)
    published_at: datetime | None = None
    discovered_at: datetime

    identity_stable: bool = False
    verified: bool = False
    analysis_eligible: bool = False
    top5_eligible: bool = False

    market_signals: list[MarketSignal] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    missing_information: list[MissingInformation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("market_code", "currency")
    @classmethod
    def uppercase_codes(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def enforce_lifecycle_consistency(self) -> "OpportunityRecord":
        if self.listing_status in {
            ListingStatus.ENDED,
            ListingStatus.SOLD,
            ListingStatus.UNAVAILABLE,
        } and self.analysis_eligible:
            raise ValueError("inactive listings cannot be analysis eligible")
        if self.evaluation_status == EvaluationStatus.QUALIFIED and not self.verified:
            raise ValueError("qualified opportunities must be verified")
        if self.workflow_status == WorkflowStatus.QUALIFIED_OPPORTUNITY and (
            self.evaluation_status != EvaluationStatus.QUALIFIED or not self.verified
        ):
            raise ValueError(
                "qualified workflow status requires verified QUALIFIED evaluation"
            )
        return self
