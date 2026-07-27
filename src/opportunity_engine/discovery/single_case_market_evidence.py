"""Verified market-comparable bridge for the Clothing Inventory single-case runner.

This module reuses the existing V2.8 market-comparables engine and the V2.10
verified-financial integration boundary. It accepts only explicitly verified
public observations. Missing or unverified evidence never becomes a market value
or an automatic commercial decision.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from opportunity_engine.external_market_comparables import (
    ComparableCandidate,
    MarketComparablesEngine,
)
from opportunity_engine.verified_financial_integration import (
    integrate_verified_financial_evidence,
)

_REQUIRED_COMPARABLES = 3
_REQUIRED_COST_FIELDS = (
    "auction_fee_nok",
    "vat_nok",
    "transport_cost_nok",
    "dismantling_cost_nok",
    "storage_cost_nok",
)


def _records(payload: object) -> list[dict[str, Any]]:
    """Extract comparable records from supported machine-readable payloads."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("comparables payload must be a list or object")

    direct = payload.get("comparables")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]

    records: list[dict[str, Any]] = []
    opportunities = payload.get("opportunities")
    if isinstance(opportunities, list):
        for opportunity in opportunities:
            if not isinstance(opportunity, dict):
                continue
            candidates = opportunity.get("candidates")
            if isinstance(candidates, list):
                records.extend(item for item in candidates if isinstance(item, dict))
    return records


def _candidate_payload(candidate: ComparableCandidate) -> dict[str, Any]:
    return {
        "title": candidate.title,
        "url": candidate.url,
        "price_nok": candidate.price_nok,
        "source_name": candidate.source_name,
        "observed_at": candidate.observed_at,
        "similarity_score": candidate.similarity_score,
        "condition": candidate.condition,
        "location": candidate.location,
        "verified": True,
    }


def evaluate_verified_market_comparables(
    payload: object,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate explicit verified observations and summarize them with V2.8."""
    raw_records = _records(payload)
    candidates: list[ComparableCandidate] = []
    input_rejections: list[dict[str, Any]] = []

    for index, record in enumerate(raw_records):
        if record.get("verified") is not True:
            input_rejections.append(
                {
                    "index": index,
                    "url": record.get("url"),
                    "reasons": ["comparable_not_explicitly_verified"],
                }
            )
            continue
        try:
            candidates.append(
                ComparableCandidate(
                    title=str(record.get("title") or "").strip(),
                    url=str(record.get("url") or "").strip(),
                    price_nok=record.get("price_nok"),
                    source_name=str(
                        record.get("source_name")
                        or record.get("source")
                        or record.get("domain")
                        or "verified_market_comparable"
                    ).strip(),
                    observed_at=str(
                        record.get("observed_at") or record.get("captured_at") or ""
                    ).strip(),
                    similarity_score=record.get("similarity_score"),
                    condition=(
                        str(record.get("condition")).strip()
                        if record.get("condition") is not None
                        else None
                    ),
                    location=(
                        str(record.get("location")).strip()
                        if record.get("location") is not None
                        else None
                    ),
                )
            )
        except (TypeError, ValueError) as exc:
            input_rejections.append(
                {
                    "index": index,
                    "url": record.get("url"),
                    "reasons": [f"invalid_verified_comparable:{exc}"],
                }
            )

    result = MarketComparablesEngine(minimum_accepted=_REQUIRED_COMPARABLES).analyse(
        candidates,
        now=now,
    )
    engine_rejections = [
        {
            "url": decision.candidate.url,
            "title": decision.candidate.title,
            "reasons": list(decision.reasons),
        }
        for decision in result.rejected
    ]
    accepted = [_candidate_payload(item) for item in result.accepted]
    complete = (
        len(accepted) >= _REQUIRED_COMPARABLES
        and result.conservative_market_value_nok is not None
    )

    return {
        "schema_version": "single-case-market-comparables-v1",
        "required_verified_comparables": _REQUIRED_COMPARABLES,
        "records_received": len(raw_records),
        "verified_input_count": len(candidates),
        "accepted_count": len(accepted),
        "rejected_count": len(input_rejections) + len(engine_rejections),
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "confidence": result.confidence.value,
        "lowest_reliable_price_nok": result.lowest_reliable_price_nok,
        "median_price_nok": result.median_price_nok,
        "price_range_nok": list(result.price_range_nok) if result.price_range_nok else None,
        "conservative_market_value_nok": result.conservative_market_value_nok,
        "warnings": list(result.warnings),
        "accepted": accepted,
        "rejected": [*input_rejections, *engine_rejections],
    }


def apply_verified_market_comparables(
    report: dict[str, Any],
    payload: object,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Attach verified comparisons and safely cross the existing analysis boundary."""
    enriched = deepcopy(report)
    market = evaluate_verified_market_comparables(payload, now=now)
    enriched["market_comparables"] = market

    dossier = enriched.get("dossier")
    eligibility = enriched.get("eligibility")
    if not isinstance(dossier, dict) or not isinstance(eligibility, dict):
        raise ValueError("single-case report is missing dossier or eligibility data")

    if market["status"] == "COMPLETE":
        missing_evidence = dossier.get("missing_evidence", [])
        if isinstance(missing_evidence, list):
            dossier["missing_evidence"] = [
                item for item in missing_evidence if item != "market comparable evidence"
            ]

        missing_requirements = eligibility.get("missing_requirements", [])
        if isinstance(missing_requirements, list):
            eligibility["missing_requirements"] = [
                item for item in missing_requirements if item != "verified market comparables"
            ]
        remaining = eligibility.get("missing_requirements", [])
        eligibility["eligible_for_analysis"] = not remaining
        eligibility["reason"] = (
            "Minimum verified market-comparable evidence is complete."
            if not remaining
            else "Other required evidence remains missing."
        )

    if eligibility.get("eligible_for_analysis") is True:
        seller_claims = dossier.get("seller_claims", {})
        asking_price = (
            seller_claims.get("asking_price_nok")
            if isinstance(seller_claims, dict)
            else None
        )
        supplied: dict[str, Any] = {
            "market_comparables": [
                {
                    "verified": True,
                    "price_nok": item["price_nok"],
                    "source": item["source_name"],
                    "url": item["url"],
                }
                for item in market["accepted"]
            ],
            "auction_price_nok": asking_price,
        }
        supplied.update({field: None for field in _REQUIRED_COST_FIELDS})
        financial = integrate_verified_financial_evidence(
            str(dossier.get("opportunity_id") or "clothing-inventory-single-case"),
            supplied,
        )
        enriched["financial_integration"] = financial.to_dict()
        enriched["analysis_invoked"] = True
        enriched["final_outcome"] = (
            "ANALYSIS_READY"
            if financial.decision_gate == "READY_FOR_FINANCIAL_REVIEW"
            else "EVIDENCE_REQUIRED"
        )
    else:
        enriched["financial_integration"] = {
            "invoked": False,
            "decision_gate": "EVIDENCE_REQUIRED",
            "reason": "eligibility_gate_blocked",
        }
        enriched["analysis_invoked"] = False
        enriched["final_outcome"] = "EVIDENCE_REQUIRED"

    enriched["automatic_purchase_decision"] = False
    enriched["automatic_bid"] = False
    enriched["automatic_contact"] = False
    enriched["automatic_payment"] = False
    return enriched
