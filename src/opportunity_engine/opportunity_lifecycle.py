"""Deterministic lifecycle classification for canonical opportunity records.

The classifier is intentionally pure: it reads one discovery candidate and returns
one lifecycle decision. It does not persist data, contact sources, rank candidates,
or perform any commercial action.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from opportunity_engine.unified_models import (
    EvaluationStatus,
    ListingStatus,
    WorkflowStatus,
)


CONFIRMED_SALE = "CONFIRMED_SALE"
STRONG_LEAD_REQUIRES_VERIFICATION = "STRONG_LEAD_REQUIRES_VERIFICATION"
HISTORICAL_MARKET_EVIDENCE = "HISTORICAL_MARKET_EVIDENCE"
REJECTED_STATES = frozenset({"REJECTED", "REJECTED_NOISE"})
EARLY_SIGNAL_STATES = frozenset({"EARLY_SIGNAL", "EVENT_LEAD"})
INACTIVE_LISTING_STATUSES = frozenset(
    {ListingStatus.ENDED, ListingStatus.SOLD, ListingStatus.UNAVAILABLE}
)


class LifecycleReasonCode(StrEnum):
    """Stable machine-readable reason for the selected lifecycle state."""

    REJECTED_BY_SOURCE = "REJECTED_BY_SOURCE"
    HISTORICAL_INACTIVE_LISTING = "HISTORICAL_INACTIVE_LISTING"
    INACTIVE_LISTING_CLOSED = "INACTIVE_LISTING_CLOSED"
    TRACEABLE_EARLY_SIGNAL = "TRACEABLE_EARLY_SIGNAL"
    CONFIRMED_SALE_NEEDS_VERIFICATION = "CONFIRMED_SALE_NEEDS_VERIFICATION"
    MISSING_REQUIRED_VERIFICATION = "MISSING_REQUIRED_VERIFICATION"
    ACTIVE_READY_FOR_ANALYSIS = "ACTIVE_READY_FOR_ANALYSIS"
    QUALIFIED_CONFIRMED_SALE = "QUALIFIED_CONFIRMED_SALE"
    NEW_CANDIDATE = "NEW_CANDIDATE"


class LifecycleDecision(BaseModel):
    """One normalized lifecycle decision and its effective eligibility flags."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    listing_status: ListingStatus
    evaluation_status: EvaluationStatus
    workflow_status: WorkflowStatus
    verified: bool
    top5_eligible: bool
    analysis_eligible: bool
    reason_code: LifecycleReasonCode


def normalize_listing_status(value: object) -> ListingStatus:
    """Map an external listing status into the canonical enum without guessing."""
    try:
        return ListingStatus(str(value or ListingStatus.UNKNOWN.value).upper())
    except ValueError:
        return ListingStatus.UNKNOWN


def _verification_items(candidate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = candidate.get("verification") or []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def candidate_is_verified(candidate: Mapping[str, Any]) -> bool:
    """Return true only when explicit source evidence is marked verified."""
    return bool(candidate.get("verified") is True) or any(
        item.get("verified") is True for item in _verification_items(candidate)
    )


def classify_opportunity_lifecycle(
    candidate: Mapping[str, Any],
    *,
    verified: bool | None = None,
) -> LifecycleDecision:
    """Classify one candidate using ordered, deterministic lifecycle rules.

    Rule precedence is deliberate: rejection and historical/inactive evidence always
    outrank current-opportunity states. Eligibility flags are normalized with the
    lifecycle so ended, historical, or rejected records cannot enter current Top 5
    or analysis flows.
    """
    listing_status = normalize_listing_status(candidate.get("listing_status"))
    state = str(
        candidate.get("opportunity_state") or candidate.get("state") or ""
    ).strip().upper()
    page_role = str(candidate.get("page_role") or "").strip().upper()
    verified_value = candidate_is_verified(candidate) if verified is None else verified
    requested_top5 = candidate.get("top5_eligible") is True
    requested_analysis = candidate.get("analysis_eligible") is True

    if state in REJECTED_STATES:
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.REJECTED,
            workflow_status=WorkflowStatus.REJECTED,
            verified=verified_value,
            top5_eligible=False,
            analysis_eligible=False,
            reason_code=LifecycleReasonCode.REJECTED_BY_SOURCE,
        )

    if (
        state == HISTORICAL_MARKET_EVIDENCE
        and listing_status in INACTIVE_LISTING_STATUSES
    ):
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.HISTORICAL_ONLY,
            workflow_status=WorkflowStatus.HISTORICAL_MARKET_EVIDENCE,
            verified=verified_value,
            top5_eligible=False,
            analysis_eligible=False,
            reason_code=LifecycleReasonCode.HISTORICAL_INACTIVE_LISTING,
        )

    if listing_status in INACTIVE_LISTING_STATUSES:
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.REQUIRES_VERIFICATION,
            workflow_status=WorkflowStatus.CLOSED,
            verified=verified_value,
            top5_eligible=False,
            analysis_eligible=False,
            reason_code=LifecycleReasonCode.INACTIVE_LISTING_CLOSED,
        )

    if state in EARLY_SIGNAL_STATES or page_role == "EVENT_LEAD":
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.NOT_EVALUATED,
            workflow_status=WorkflowStatus.EARLY_SIGNAL,
            verified=verified_value,
            top5_eligible=requested_top5,
            analysis_eligible=False,
            reason_code=LifecycleReasonCode.TRACEABLE_EARLY_SIGNAL,
        )

    if state == CONFIRMED_SALE:
        if (
            listing_status == ListingStatus.ACTIVE
            and verified_value
            and requested_analysis
        ):
            return LifecycleDecision(
                listing_status=listing_status,
                evaluation_status=EvaluationStatus.QUALIFIED,
                workflow_status=WorkflowStatus.QUALIFIED_OPPORTUNITY,
                verified=True,
                top5_eligible=requested_top5,
                analysis_eligible=True,
                reason_code=LifecycleReasonCode.QUALIFIED_CONFIRMED_SALE,
            )
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.REQUIRES_VERIFICATION,
            workflow_status=WorkflowStatus.REQUIRES_VERIFICATION,
            verified=verified_value,
            top5_eligible=requested_top5,
            analysis_eligible=False,
            reason_code=LifecycleReasonCode.CONFIRMED_SALE_NEEDS_VERIFICATION,
        )

    if (
        listing_status == ListingStatus.ACTIVE
        and verified_value
        and requested_analysis
    ):
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.NOT_EVALUATED,
            workflow_status=WorkflowStatus.ACTIVE_OPPORTUNITY,
            verified=True,
            top5_eligible=requested_top5,
            analysis_eligible=True,
            reason_code=LifecycleReasonCode.ACTIVE_READY_FOR_ANALYSIS,
        )

    if state == STRONG_LEAD_REQUIRES_VERIFICATION or requested_top5 or verified_value:
        return LifecycleDecision(
            listing_status=listing_status,
            evaluation_status=EvaluationStatus.REQUIRES_VERIFICATION,
            workflow_status=WorkflowStatus.REQUIRES_VERIFICATION,
            verified=verified_value,
            top5_eligible=(
                requested_top5 and listing_status == ListingStatus.ACTIVE
            ),
            analysis_eligible=False,
            reason_code=LifecycleReasonCode.MISSING_REQUIRED_VERIFICATION,
        )

    return LifecycleDecision(
        listing_status=listing_status,
        evaluation_status=EvaluationStatus.NOT_EVALUATED,
        workflow_status=WorkflowStatus.CANDIDATE,
        verified=verified_value,
        top5_eligible=False,
        analysis_eligible=False,
        reason_code=LifecycleReasonCode.NEW_CANDIDATE,
    )
