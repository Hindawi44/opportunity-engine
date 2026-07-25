"""Rule-based qualification for Clothing Inventory Discovery V1."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult
from opportunity_engine.discovery.opportunity_maps import CLOTHING_INVENTORY_MAP, SCENARIO_RECORD_TYPES

_SINGLE_ITEM_TERMS = (
    "jakke", "kjole", "bukse", "skjorte", "genser", "frakk", "dress",
)
_COMMERCIAL_TERMS = (
    "varelager", "vareparti", "klesparti", "parti med klær", "komplett lager",
    "hele lageret", "butikk", "grossist", "importør", "auksjon", "konkursbo",
    "opphørssalg", "avvikling", "tømmesalg", "restlager", "overskuddslager",
)
_SALE_TERMS = ("til salgs", "selges", "auksjon", "bud", "pris", "opphørssalg", "tømmesalg")


def _normalized(candidate: DiscoveryCandidate) -> str:
    return " ".join(f"{candidate.title} {candidate.text}".lower().split())


def _scenario(text: str) -> tuple[str | None, tuple[str, ...]]:
    matches: list[tuple[str, str]] = []
    for scenario, phrases in CLOTHING_INVENTORY_MAP.items():
        for phrase in phrases:
            if phrase in text:
                matches.append((scenario, phrase))
    if not matches:
        return None, ()

    # Prefer the most specific matching signal rather than dictionary order.
    # Example: "lageravvikling klær" must outrank the generic substring
    # "avvikling", otherwise an inventory-liquidation listing is incorrectly
    # classified as STORE_CLOSING.
    scenario, _ = max(matches, key=lambda match: len(match[1]))
    evidence = tuple(
        dict.fromkeys(
            phrase
            for matched_scenario, phrase in matches
            if matched_scenario == scenario
        )
    )
    return scenario, evidence


def classify_candidate(candidate: DiscoveryCandidate) -> DiscoveryResult:
    """Classify a public candidate without inventing missing values."""
    if not candidate.title.strip() or not candidate.url.startswith("https://"):
        return DiscoveryResult(candidate, "UNKNOWN", "REJECTED_RESULT", "REJECTED", "missing public title or HTTPS URL")

    text = _normalized(candidate)
    scenario, evidence = _scenario(text)
    has_commercial_signal = any(term in text for term in _COMMERCIAL_TERMS)
    has_sale_signal = any(term in text for term in _SALE_TERMS) or candidate.price_nok is not None

    if not has_commercial_signal:
        single_item = any(re.search(rf"\b{re.escape(term)}\b", text) for term in _SINGLE_ITEM_TERMS)
        reason = "ordinary single-item listing" if single_item else "no clothing-inventory commercial signal"
        return DiscoveryResult(candidate, "UNKNOWN", "REJECTED_RESULT", "REJECTED", reason)

    scenario = scenario or "LARGE_LOT_SALE"
    record_type = SCENARIO_RECORD_TYPES.get(scenario, "LIQUIDATION_LEAD")
    if record_type == "SALE_LISTING" and has_sale_signal:
        return DiscoveryResult(candidate, scenario, record_type, "SALE_CONFIRMED", "commercial inventory sale signal found", evidence)
    if has_sale_signal and scenario in {"STORE_CLOSING", "BRANCH_CLOSURE"}:
        return DiscoveryResult(candidate, scenario, "SALE_LISTING", "SALE_CONFIRMED", "closure includes a public sale signal", evidence)
    return DiscoveryResult(candidate, scenario, record_type, "CONTACT_REQUIRED", "relevant lead; asset sale is not yet confirmed", evidence)


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
            "domain": "CLOTHING_INVENTORY",
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
