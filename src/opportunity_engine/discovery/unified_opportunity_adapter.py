"""Map discovery candidate dictionaries into canonical opportunity records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from opportunity_engine.opportunity_lifecycle import (
    candidate_is_verified,
    classify_opportunity_lifecycle,
)
from opportunity_engine.unified_models import (
    Evidence,
    MarketSignal,
    MissingInformation,
    OpportunityRecord,
)


def _verification_items(candidate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = candidate.get("verification") or []
    return [item for item in items if isinstance(item, Mapping)]


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
                    "verification_content_match": item.get(
                        "verification_content_match"
                    ),
                    "historical_data_fields_trusted": item.get(
                        "historical_data_fields_trusted"
                    ),
                    "exclude_from_historical_price_analysis": item.get(
                        "exclude_from_historical_price_analysis"
                    ),
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


def _trusted_historical_bid_price(
    candidate: Mapping[str, Any],
    *,
    currency: str,
) -> float | None:
    """Return only a source-native bid explicitly trusted for historical analysis."""
    direct_nok = candidate.get("bid_price_nok")
    if direct_nok is not None:
        return float(direct_nok)

    if candidate.get("bid_price_trusted") is not True:
        return None
    if candidate.get("exclude_from_historical_price_analysis") is True:
        return None

    source_currency = str(candidate.get("bid_price_currency") or "").upper()
    canonical_currency = str(currency).upper()
    if source_currency != canonical_currency:
        return None

    source_field = {
        "SEK": "bid_price_sek",
    }.get(source_currency)
    if source_field is None:
        return None

    value = candidate.get(source_field)
    return float(value) if value is not None else None


def _string_list(candidate: Mapping[str, Any], key: str) -> list[str]:
    raw = candidate.get(key) or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _metadata(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve source trust and occurrence identity without estimating values."""
    return {
        "discovery_score": candidate.get("discovery_score"),
        "discovery_band": candidate.get("discovery_band"),
        "page_role": candidate.get("page_role"),
        "reason": candidate.get("reason"),
        "opportunity_state": candidate.get("opportunity_state")
        or candidate.get("state"),
        "historical_market_evidence_eligible": candidate.get(
            "historical_market_evidence_eligible"
        )
        is True,
        "verification_content_match": candidate.get("verification_content_match"),
        "historical_data_fields_trusted": candidate.get(
            "historical_data_fields_trusted"
        ),
        "exclude_from_historical_price_analysis": candidate.get(
            "exclude_from_historical_price_analysis"
        ),
        "historical_price_analysis_exclusion_reason": candidate.get(
            "historical_price_analysis_exclusion_reason"
        ),
        "bid_price_trusted": candidate.get("bid_price_trusted"),
        "reference_value_trusted": candidate.get("reference_value_trusted"),
        "bid_price_sek": candidate.get("bid_price_sek"),
        "bid_price_currency": candidate.get("bid_price_currency"),
        "reference_value_sek": candidate.get("reference_value_sek"),
        "reference_value_kind": candidate.get("reference_value_kind"),
        "reference_value_is_current_sale_price": candidate.get(
            "reference_value_is_current_sale_price"
        ),
        "source_object_id": candidate.get("source_object_id"),
        "auction_occurrence_id": candidate.get("auction_occurrence_id"),
        "price_kind": candidate.get("price_kind"),
        "verification_blockers": _string_list(candidate, "verification_blockers"),
        "analysis_tasks": _string_list(candidate, "analysis_tasks"),
    }


def opportunity_record_from_discovery_candidate(
    candidate: Mapping[str, Any],
    *,
    discovered_at: datetime,
    market_code: str = "NO",
    currency: str = "NOK",
    domain: str = "TEXTILE_AND_SEWING",
) -> OpportunityRecord:
    """Build one validated record without estimating missing public facts."""
    verified = candidate_is_verified(candidate)
    lifecycle = classify_opportunity_lifecycle(candidate, verified=verified)
    metadata = _metadata(candidate)
    metadata["lifecycle_reason_code"] = lifecycle.reason_code.value

    return OpportunityRecord(
        opportunity_id=str(candidate.get("opportunity_identity") or "").strip(),
        market_code=market_code,
        domain=domain,
        category=str(candidate.get("textile_category") or "UNCLASSIFIED"),
        title=str(candidate.get("title") or "").strip(),
        source_provider=_source_provider(candidate),
        source_url=_source_url(candidate),
        listing_status=lifecycle.listing_status,
        evaluation_status=lifecycle.evaluation_status,
        workflow_status=lifecycle.workflow_status,
        scenario=candidate.get("scenario"),
        company_name=candidate.get("company_name"),
        location=candidate.get("location"),
        inventory_type=candidate.get("inventory_type"),
        currency=currency,
        price=candidate.get("price_nok"),
        bid_price=_trusted_historical_bid_price(candidate, currency=currency),
        quantity=candidate.get("quantity"),
        published_at=candidate.get("published_at"),
        discovered_at=discovered_at,
        identity_stable=candidate.get("identity_stable") is True,
        verified=lifecycle.verified,
        analysis_eligible=lifecycle.analysis_eligible,
        top5_eligible=lifecycle.top5_eligible,
        market_signals=_market_signals(candidate),
        evidence=_evidence(candidate),
        missing_information=_missing_information(candidate),
        metadata=metadata,
    )
