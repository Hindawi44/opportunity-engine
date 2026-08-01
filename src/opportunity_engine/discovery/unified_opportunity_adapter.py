"""Map discovery candidate dictionaries into canonical opportunity records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from opportunity_engine.unified_models import (
    EvaluationStatus,
    Evidence,
    ListingStatus,
    MarketSignal,
    MissingInformation,
    OpportunityRecord,
    WorkflowStatus,
)

_CONFIRMED_SALE = "CONFIRMED_SALE"
_STRONG_LEAD = "STRONG_LEAD_REQUIRES_VERIFICATION"
_REJECTED = "REJECTED_NOISE"


def _listing_status(value: object) -> ListingStatus:
    try:
        return ListingStatus(str(value or "UNKNOWN"))
    except ValueError:
        return ListingStatus.UNKNOWN


def _lifecycle(
    candidate: Mapping[str, Any],
    verified: bool,
) -> tuple[EvaluationStatus, WorkflowStatus]:
    state = str(candidate.get("opportunity_state") or candidate.get("state") or "")
    status = _listing_status(candidate.get("listing_status"))

    if state == _REJECTED:
        return EvaluationStatus.REJECTED, WorkflowStatus.REJECTED
    if status in {ListingStatus.ENDED, ListingStatus.SOLD, ListingStatus.UNAVAILABLE}:
        return EvaluationStatus.REQUIRES_VERIFICATION, WorkflowStatus.CLOSED
    if state == _CONFIRMED_SALE and verified and status == ListingStatus.ACTIVE:
        return EvaluationStatus.QUALIFIED, WorkflowStatus.QUALIFIED_OPPORTUNITY
    if state == _STRONG_LEAD:
        return EvaluationStatus.REQUIRES_VERIFICATION, WorkflowStatus.REQUIRES_VERIFICATION
    return EvaluationStatus.NOT_EVALUATED, WorkflowStatus.CANDIDATE


def _verification_items(candidate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = candidate.get("verification") or []
    return [item for item in items if isinstance(item, Mapping)]


def _verified(candidate: Mapping[str, Any]) -> bool:
    return any(item.get("verified") is True for item in _verification_items(candidate))


def _source_url(candidate: Mapping[str, Any]) -> str:
    urls = candidate.get("source_urls") or []
    if not urls:
        raise ValueError("discovery candidate must contain one source URL")
    return str(urls[0])


def _source_provider(candidate: Mapping[str, Any]) -> str:
    providers = candidate.get("source_providers") or []
    return str(providers[0]) if providers else "UNKNOWN_SOURCE"


def _evidence(candidate: Mapping[str, Any]) -> list[Evidence]:
    records: list[Evidence] = []
    for item in _verification_items(candidate):
        value = item.get("bounded_context") or item.get("text") or item.get("title")
        url = item.get("url")
        if not value or not url:
            continue
        records.append(
            Evidence(
                evidence_type="PUBLIC_PAGE",
                value=str(value),
                source_url=str(url),
                verified=item.get("verified") is True,
                metadata={
                    "page_role": item.get("page_role"),
                    "listing_status": item.get("listing_status"),
                    "event_scenario": item.get("event_scenario"),
                },
            )
        )
    return records


def _market_signals(candidate: Mapping[str, Any]) -> list[MarketSignal]:
    signals = candidate.get("evidence_signals") or []
    return [
        MarketSignal(
            signal_type=str(candidate.get("scenario") or "UNVERIFIED_EVENT"),
            value=str(signal),
            source=_source_provider(candidate),
        )
        for signal in signals
        if str(signal).strip()
    ]


def _missing_information(candidate: Mapping[str, Any]) -> list[MissingInformation]:
    fields = candidate.get("missing_information") or []
    return [
        MissingInformation(field_name=str(field))
        for field in fields
        if str(field).strip()
    ]


def opportunity_record_from_discovery_candidate(
    candidate: Mapping[str, Any],
    *,
    discovered_at: datetime,
    market_code: str = "NO",
    currency: str = "NOK",
    domain: str = "TEXTILE_AND_SEWING",
) -> OpportunityRecord:
    """Build one validated record without estimating missing public facts."""
    verified = _verified(candidate)
    evaluation_status, workflow_status = _lifecycle(candidate, verified)
    listing_status = _listing_status(candidate.get("listing_status"))

    return OpportunityRecord(
        opportunity_id=str(candidate.get("opportunity_identity") or "").strip(),
        market_code=market_code,
        domain=domain,
        category=str(candidate.get("textile_category") or "UNCLASSIFIED"),
        title=str(candidate.get("title") or "").strip(),
        source_provider=_source_provider(candidate),
        source_url=_source_url(candidate),
        listing_status=listing_status,
        evaluation_status=evaluation_status,
        workflow_status=workflow_status,
        scenario=candidate.get("scenario"),
        company_name=candidate.get("company_name"),
        location=candidate.get("location"),
        inventory_type=candidate.get("inventory_type"),
        currency=currency,
        price=candidate.get("price_nok"),
        bid_price=candidate.get("bid_price_nok"),
        quantity=candidate.get("quantity"),
        published_at=candidate.get("published_at"),
        discovered_at=discovered_at,
        identity_stable=candidate.get("identity_stable") is True,
        verified=verified,
        analysis_eligible=candidate.get("analysis_eligible") is True,
        top5_eligible=candidate.get("top5_eligible") is True,
        market_signals=_market_signals(candidate),
        evidence=_evidence(candidate),
        missing_information=_missing_information(candidate),
        metadata={
            "discovery_score": candidate.get("discovery_score"),
            "discovery_band": candidate.get("discovery_band"),
            "page_role": candidate.get("page_role"),
            "reason": candidate.get("reason"),
        },
    )
