"""Conservative commercial-readiness gate for verified Italy exact lots.

ITALY_COMMERCIAL_QUALIFICATION_V1 consumes only rows already proven by
ITALY_EXACT_LOT_VERIFICATION_V1 to be active, entity-linked clothing lots. It
never converts missing economics into estimates. The gate records exact source
facts, derives only arithmetic facts mathematically implied by them, and names
the existing project evidence lanes that must run before any financial decision.

The exact-lot parser can observe a listed price, auction base price or minimum
offer. Therefore this module deliberately calls it a *source listed price*, not
a purchase price. Dividing that value by a source-page quantity creates only a
unit reference; it is never a final payable unit cost.

No FX rate, auction fee, VAT, freight, resale value, margin, ROI, bid ceiling or
purchase decision is guessed here. Italy remains outside the canonical
NO/SE/DE Top-5 lane in V1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "italy-commercial-qualification-1.0"
ENGINE_VERSION = "ITALY_COMMERCIAL_QUALIFICATION_V1"
DECISION_OWNER = "HUMAN_OPERATOR"

_EXACT_LOT_ENGINE = "ITALY_EXACT_LOT_VERIFICATION_V1"
_VERIFIED_STATUS = "VERIFIED_ACTIVE_EXACT_LOT_LEAD"

_DOWNSTREAM_EVIDENCE_LANES = (
    "market_comparables_benchmark",
    "source_logistics_hydration",
    "single_case_market_evidence",
    "single_case_cost_evidence",
    "one_opportunity_commercial_analysis",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if parsed >= 0 else None
    return None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value.is_integer() and value > 0:
        return int(value)
    return None


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _verified_exact_lot(row: Mapping[str, Any]) -> bool:
    return bool(
        _compact(row.get("source_page_verification_status")) == _VERIFIED_STATUS
        and row.get("source_page_verified") is True
        and row.get("entity_link_verified") is True
        and row.get("exact_lot_evidence") is True
        and _compact(row.get("sale_status")).upper() == "ACTIVE"
        and row.get("commercial_lead_verified") is True
    )


def _inventory_category(row: Mapping[str, Any]) -> str:
    terms = {
        _compact(value).casefold()
        for value in row.get("clothing_terms") or []
        if _compact(value)
    }
    if terms.intersection({"abiti da sposa", "campionario sposa"}):
        return "BRIDAL"
    if terms.intersection({"calzature", "scarpe"}):
        return "FOOTWEAR"
    return "CLOTHING"


def _source_fact_missing(row: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if _positive_int(row.get("quantity")) is None:
        missing.append("source quantity")
    if _number(row.get("source_price_eur")) is None:
        missing.append("source listed/base price EUR")
    if not _compact(row.get("location")):
        missing.append("source location")
    if not _compact(row.get("sale_deadline_text")):
        missing.append("sale deadline")
    return missing


def _decision_evidence_missing(row: Mapping[str, Any]) -> list[str]:
    """Name facts required by existing financial engines but absent here."""
    missing = [
        "verified EUR/NOK FX observation",
        "final payable price NOK including fees and VAT",
        "verified transport or pickup cost NOK",
        "at least 3 verified market comparables",
        "conservative resale value NOK from verified comparables",
        "verified inventory condition",
    ]
    if row.get("buyer_premium_percent") in (None, ""):
        missing.append("verified buyer/auction fee")
    if row.get("vat_percent") in (None, ""):
        missing.append("verified VAT treatment")
    return missing


def _qualification_row(row: Mapping[str, Any], *, generated_at: datetime) -> dict[str, Any]:
    quantity = _positive_int(row.get("quantity"))
    listed_price_eur = _number(row.get("source_price_eur"))
    unit_reference_eur = None
    if quantity is not None and listed_price_eur is not None:
        unit_reference_eur = round(listed_price_eur / quantity, 6)

    source_missing = _source_fact_missing(row)
    decision_missing = _decision_evidence_missing(row)
    category = _inventory_category(row)
    verification_id = _compact(row.get("verification_id"))
    stable = verification_id or _compact(row.get("canonical_source_url"))
    qualification_id = "italy-commercial-qualification:" + sha256(
        stable.encode("utf-8")
    ).hexdigest()[:24]

    if quantity is not None and listed_price_eur is not None:
        state = "SOURCE_PRICE_AND_QUANTITY_PRESENT"
    else:
        state = "SOURCE_ECONOMICS_INCOMPLETE"

    return {
        "qualification_id": qualification_id,
        "verification_id": row.get("verification_id"),
        "case_id": row.get("case_id"),
        "case_title": row.get("case_title"),
        "title": row.get("title") or row.get("search_result_title"),
        "source_url": row.get("canonical_source_url") or row.get("source_url"),
        "source_country": "IT",
        "inventory_category": category,
        "sale_status": "ACTIVE",
        "source_page_verified": True,
        "entity_link_verified": True,
        "exact_lot_evidence": True,
        "commercial_lead_verified": True,
        "qualification_state": state,
        "source_facts": {
            "quantity": quantity,
            "quantity_unit": "ITEM" if quantity is not None else None,
            "source_listed_price_eur": listed_price_eur,
            "source_price_semantics": (
                "LISTED_OR_AUCTION_BASE_OR_MINIMUM_OFFER_NOT_FINAL_PAYABLE"
                if listed_price_eur is not None
                else None
            ),
            "source_listed_unit_reference_eur": unit_reference_eur,
            "currency": "EUR" if listed_price_eur is not None else None,
            "location": _compact(row.get("location")) or None,
            "sale_deadline_text": _compact(row.get("sale_deadline_text")) or None,
            "response_sha256": row.get("response_sha256"),
        },
        "derived_facts": {
            "source_listed_unit_reference_eur": unit_reference_eur,
            "derivation": (
                "SOURCE_PAGE_LISTED_PRICE_EUR_DIVIDED_BY_SOURCE_PAGE_QUANTITY"
                if unit_reference_eur is not None
                else None
            ),
            "final_payable_unit_cost": False,
            "estimated": False,
        },
        "missing_source_facts": source_missing,
        "missing_decision_evidence": decision_missing,
        "downstream_evidence_lanes": list(_DOWNSTREAM_EVIDENCE_LANES),
        "ready_for_market_comparables": True,
        "ready_for_logistics_evidence": bool(_compact(row.get("location"))),
        "ready_for_financial_decision": False,
        "financial_decision": None,
        "final_payable_price_nok": None,
        "profit_nok": None,
        "roi": None,
        "margin": None,
        "maximum_bid": None,
        "fx_rate_assumed": False,
        "shipping_cost_assumed": False,
        "resale_value_assumed": False,
        "promotion_to_opportunity_allowed": False,
        "top5_eligible": False,
        "analysis_eligible": False,
        "decision_owner": DECISION_OWNER,
        "generated_at": generated_at.isoformat(),
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def run_italy_commercial_qualification(
    exact_lot_report: Mapping[str, Any],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Qualify verified Italy exact lots for later evidence collection only."""
    now = _utc(observed_at)
    all_rows = _rows(exact_lot_report.get("verifications"))
    eligible = [row for row in all_rows if _verified_exact_lot(row)]
    qualifications = [_qualification_row(row, generated_at=now) for row in eligible]

    unit_reference_count = sum(
        item.get("qualification_state") == "SOURCE_PRICE_AND_QUANTITY_PRESENT"
        for item in qualifications
    )
    with_location = sum(
        bool((item.get("source_facts") or {}).get("location"))
        for item in qualifications
    )

    if not all_rows:
        status = "VALID_ZERO_NO_EXACT_LOT_ROWS"
    elif not eligible:
        status = "VALID_ZERO_NO_VERIFIED_ACTIVE_EXACT_LOTS"
    else:
        status = "SUCCESS"

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "input_engine_version": exact_lot_report.get("engine_version") or _EXACT_LOT_ENGINE,
        "generated_at": now.isoformat(),
        "status": status,
        "purpose": "QUALIFY_VERIFIED_ITALY_EXACT_LOTS_FOR_EXISTING_MARKET_LOGISTICS_AND_COST_ENGINES",
        "input_exact_lot_row_count": len(all_rows),
        "verified_active_exact_lot_input_count": len(eligible),
        "qualification_count": len(qualifications),
        "source_unit_reference_derived_count": unit_reference_count,
        "source_location_known_count": with_location,
        "financial_decision_ready_count": 0,
        "qualifications": qualifications,
        "existing_downstream_engines_reused": list(_DOWNSTREAM_EVIDENCE_LANES),
        "source_price_never_treated_as_final_payable": True,
        "missing_values_are_never_estimated": True,
        "fx_rate_assumed": False,
        "shipping_cost_assumed": False,
        "resale_value_assumed": False,
        "promotion_to_opportunity_allowed": False,
        "top5_eligible": False,
        "analysis_eligible": False,
        "canonical_market_coverage_unchanged": ["NO", "SE", "DE"],
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
