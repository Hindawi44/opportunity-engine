"""Rule-based qualification for Norwegian textile and sewing discovery."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult
from opportunity_engine.discovery.opportunity_maps import (
    CLOTHING_INVENTORY_MAP,
    SCENARIO_RECORD_TYPES,
)
from opportunity_engine.discovery.textile_taxonomy import (
    TaxonomyDecision,
    classify_textile_opportunity,
)

_SINGLE_ITEM_TERMS = (
    "jakke", "kjole", "bukse", "skjorte", "genser", "frakk", "dress",
)
_SALE_TERMS = (
    "til salgs", "selges", "auksjon", "bud", "pris", "opphørssalg",
    "tømmesalg", "samlet salg", "overtas",
)

# Event-specific scenarios outrank generic lot descriptions when both appear.
_SCENARIO_PRIORITY: dict[str, int] = {
    "COMPANY_BANKRUPTCY": 100,
    "BRANCH_CLOSURE": 95,
    "INVENTORY_LIQUIDATION": 92,
    "STORE_CLOSING": 90,
    "AUCTION": 80,
    "IMPORTER_LIQUIDATION": 75,
    "MANUFACTURER_EXCESS": 70,
    "WAREHOUSE_SURPLUS": 65,
    "BUSINESS_MODEL_CHANGE": 60,
    "LARGE_LOT_SALE": 10,
}

_TAXONOMY_EVENT_SCENARIOS = {
    "BANKRUPTCY": "COMPANY_BANKRUPTCY",
    "LIQUIDATION": "INVENTORY_LIQUIDATION",
    "AUCTION": "AUCTION",
    "SURPLUS": "WAREHOUSE_SURPLUS",
    "SALE": "LARGE_LOT_SALE",
}


def _normalized(candidate: DiscoveryCandidate) -> str:
    return " ".join(f"{candidate.title} {candidate.text}".casefold().split())


def _scenario(
    text: str,
    taxonomy: TaxonomyDecision,
) -> tuple[str | None, tuple[str, ...]]:
    matches: list[tuple[str, str]] = []
    for scenario, phrases in CLOTHING_INVENTORY_MAP.items():
        for phrase in phrases:
            if phrase in text:
                matches.append((scenario, phrase))

    taxonomy_matches: list[tuple[str, str]] = []
    for signal in taxonomy.event_signals:
        event_kind, _, phrase = signal.partition(":")
        if event_kind == "CLOSURE":
            scenario = (
                "BRANCH_CLOSURE"
                if taxonomy.primary_category == "CLOTHING_CHAIN_OR_BRANCH_CLOSURE"
                else "STORE_CLOSING"
            )
        else:
            scenario = _TAXONOMY_EVENT_SCENARIOS.get(event_kind)
        if scenario:
            taxonomy_matches.append((scenario, phrase or event_kind.casefold()))

    matches.extend(taxonomy_matches)
    if not matches:
        return None, ()

    scenario, _ = max(
        matches,
        key=lambda match: (_SCENARIO_PRIORITY.get(match[0], 0), len(match[1])),
    )
    evidence = tuple(
        dict.fromkeys(
            phrase
            for matched_scenario, phrase in matches
            if matched_scenario == scenario
        )
    )
    return scenario, evidence


def _taxonomy_evidence(taxonomy: TaxonomyDecision) -> tuple[str, ...]:
    values = (
        *taxonomy.event_signals,
        *taxonomy.sector_signals,
        *taxonomy.inventory_signals,
        *(f"CATEGORY:{category}" for category in taxonomy.matched_categories),
    )
    return tuple(dict.fromkeys(values))


def classify_candidate(candidate: DiscoveryCandidate) -> DiscoveryResult:
    """Classify a public candidate without inventing missing values."""
    if not candidate.title.strip() or not candidate.url.startswith("https://"):
        return DiscoveryResult(
            candidate,
            "UNKNOWN",
            "REJECTED_RESULT",
            "REJECTED",
            "missing public title or HTTPS URL",
        )

    text = _normalized(candidate)
    taxonomy = classify_textile_opportunity(candidate.title, candidate.text)
    scenario, scenario_evidence = _scenario(text, taxonomy)
    has_sale_signal = any(term in text for term in _SALE_TERMS) or candidate.price_nok is not None

    if taxonomy.status != "IN_SCOPE":
        single_item = any(
            re.search(rf"\b{re.escape(term)}\b", text)
            for term in _SINGLE_ITEM_TERMS
        )
        reason = (
            "ordinary single-item listing"
            if single_item
            else taxonomy.reason
        )
        return DiscoveryResult(
            candidate,
            "UNKNOWN",
            "REJECTED_RESULT",
            "REJECTED",
            reason,
            taxonomy_reason=taxonomy.reason,
        )

    scenario = scenario or "LARGE_LOT_SALE"
    record_type = SCENARIO_RECORD_TYPES.get(scenario, "LIQUIDATION_LEAD")
    evidence = tuple(
        dict.fromkeys((*scenario_evidence, *_taxonomy_evidence(taxonomy)))
    )

    if record_type == "SALE_LISTING" and has_sale_signal:
        return DiscoveryResult(
            candidate,
            scenario,
            record_type,
            "SALE_CONFIRMED",
            "textile-sector commercial sale signal found",
            evidence,
            category=taxonomy.primary_category,
            taxonomy_reason=taxonomy.reason,
        )
    if has_sale_signal and scenario in {"STORE_CLOSING", "BRANCH_CLOSURE"}:
        return DiscoveryResult(
            candidate,
            scenario,
            "SALE_LISTING",
            "SALE_CONFIRMED",
            "closure includes a public sale signal",
            evidence,
            category=taxonomy.primary_category,
            taxonomy_reason=taxonomy.reason,
        )
    return DiscoveryResult(
        candidate,
        scenario,
        record_type,
        "CONTACT_REQUIRED",
        "relevant textile-sector lead; asset sale is not yet confirmed",
        evidence,
        category=taxonomy.primary_category,
        taxonomy_reason=taxonomy.reason,
    )


def to_canonical_opportunity(result: DiscoveryResult) -> dict[str, Any] | None:
    """Convert confirmed sales only to the V3.6-compatible opportunity boundary."""
    if result.status != "SALE_CONFIRMED":
        return None
    candidate = result.candidate
    digest = hashlib.sha256(candidate.url.encode("utf-8")).hexdigest()[:20]
    return {
        "schema_version": "discovery-1.0",
        "opportunity_id": f"discovery-{digest}",
        "captured_at": candidate.discovered_at,
        "discovery": {
            "domain": "TEXTILE_AND_SEWING",
            "category": result.category,
            "scenario": result.scenario,
            "record_type": result.record_type,
            "status": result.status,
            "evidence": list(result.evidence),
        },
        "source": {
            "name": candidate.source,
            "listing_id": digest,
            "url": candidate.url,
            "title": candidate.title,
            "description": candidate.text or None,
            "location": candidate.location,
            "listing_status": "ACTIVE",
            "asking_price_nok": candidate.price_nok,
        },
        "discovery_data": {
            "quantity": candidate.quantity,
            "contact": candidate.contact,
        },
        "market_price_sources": [],
        "verified_cost_evidence": {
            "auction_price_nok": candidate.price_nok,
            "auction_fee_nok": None,
            "vat_nok": None,
            "transport_cost_nok": None,
            "dismantling_cost_nok": None,
            "storage_cost_nok": None,
        },
        "automatic_purchase_decision": False,
    }
