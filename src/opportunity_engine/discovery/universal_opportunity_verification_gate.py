"""Source-agnostic verification routing for real commercial opportunities.

The gate sits above source-specific collectors. It does not fetch pages, estimate
missing facts, contact sellers, bid, buy, reserve, or pay. Its job is only to
route each unified market case into the right human-review lane:

* ACTIONABLE_NOW: a known opportunity profile passed its minimum verification gate;
* VERIFICATION_REQUIRED: a known profile is real but missing standard evidence;
* STUDY_REQUIRED: a credible commercial case does not fit a known verification profile;
* MARKET_WATCH: an early signal, not yet a direct commercial case;
* HISTORICAL_EVIDENCE: inactive reference material.

A non-standard opportunity is never rejected merely because it does not fit the
standard quantity/condition/price/shipping matrix. It is preserved for study.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "universal-opportunity-verification-gate-1.0"

ACTIONABLE_NOW = "ACTIONABLE_NOW"
VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
STUDY_REQUIRED = "STUDY_REQUIRED"
MARKET_WATCH = "MARKET_WATCH"
HISTORICAL_EVIDENCE = "HISTORICAL_EVIDENCE"

_PROFILE_DIRECT = "DIRECT_STOCK_OPPORTUNITY"
_PROFILE_B2B = "B2B_STOCK_OFFER"
_PROFILE_AUCTION = "AUCTION_LOT"
_PROFILE_FABRIC = "FABRIC_PROCUREMENT_ADVISORY"
_PROFILE_NONSTANDARD = "NONSTANDARD_COMMERCIAL_OPPORTUNITY"
_PROFILE_WATCH = "MARKET_SIGNAL_WATCH"
_PROFILE_HISTORICAL = "HISTORICAL_REFERENCE"

_STANDARD_COMMERCIAL_TYPES = {
    "DIRECT_OPPORTUNITY",
    "B2B_INVENTORY",
    "AUCTION_INVENTORY",
}
_WATCH_TYPES = {
    "COMPANY_LIQUIDATION",
    "BRIDAL_LIQUIDATION",
    "MARKET_SIGNAL_WATCH",
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _snapshot(card: Mapping[str, Any]) -> Mapping[str, Any]:
    value = card.get("commercial_snapshot")
    return value if isinstance(value, Mapping) else {}


def _has_values(card: Mapping[str, Any], key: str) -> bool:
    value = _snapshot(card).get(key)
    return isinstance(value, list) and bool(value)


def _source_present(card: Mapping[str, Any]) -> bool:
    return bool([value for value in card.get("source_urls") or [] if _compact(value)])


def _commercial_candidate(card: Mapping[str, Any]) -> bool:
    case_type = _compact(card.get("case_type")).upper()
    if int(card.get("direct_opportunity_count") or 0) > 0:
        return True
    if int(card.get("offer_count") or 0) > 0:
        return True
    if case_type in _STANDARD_COMMERCIAL_TYPES:
        return True
    if case_type == "FABRIC_PROCUREMENT":
        return True
    if _has_values(card, "prices") or _has_values(card, "quantities"):
        return True
    return bool(card.get("commercial_candidate_hint") is True)


def _explicit_nonstandard(card: Mapping[str, Any]) -> bool:
    profile = _compact(card.get("verification_profile")).upper()
    return bool(
        card.get("study_required") is True
        or card.get("nonstandard_opportunity") is True
        or profile in {"NONSTANDARD", "STUDY_REQUIRED", _PROFILE_NONSTANDARD}
    )


def _result(
    *,
    route: str,
    profile: str,
    reason_code: str,
    required: list[str] | None = None,
    missing: list[str] | None = None,
    known_standard_profile: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "route": route,
        "profile": profile,
        "reason_code": reason_code,
        "known_standard_profile": known_standard_profile,
        "gate_passed": route == ACTIONABLE_NOW,
        "study_required": route == STUDY_REQUIRED,
        "required_evidence": list(required or []),
        "missing_required_evidence": list(missing or []),
        "decision_owner": "HUMAN_OPERATOR",
        "estimated_values_added": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def classify_opportunity_verification(card: Mapping[str, Any]) -> dict[str, Any]:
    """Return one conservative, source-agnostic verification route for a case."""
    case_type = _compact(card.get("case_type")).upper()
    case_status = _compact(card.get("case_status")).upper()

    if case_type == "HISTORICAL_MARKET_EVIDENCE" or case_status == "HISTORICAL_ONLY":
        return _result(
            route=HISTORICAL_EVIDENCE,
            profile=_PROFILE_HISTORICAL,
            reason_code="HISTORICAL_REFERENCE_ONLY",
            known_standard_profile=True,
        )

    if case_type == "FABRIC_PROCUREMENT":
        # Fabric procurement already has its own advisory verification contract.
        # ACTIONABLE_NOW here means "ready for human procurement review", never buy.
        return _result(
            route=ACTIONABLE_NOW,
            profile=_PROFILE_FABRIC,
            reason_code="SEPARATE_FABRIC_PROCUREMENT_REVIEW_CONTRACT",
            known_standard_profile=True,
        )

    commercial = _commercial_candidate(card)
    if not commercial and case_type in _WATCH_TYPES:
        return _result(
            route=MARKET_WATCH,
            profile=_PROFILE_WATCH,
            reason_code="EARLY_SIGNAL_NOT_DIRECT_COMMERCIAL_CASE",
            known_standard_profile=True,
        )
    if not commercial:
        return _result(
            route=MARKET_WATCH,
            profile=_PROFILE_WATCH,
            reason_code="NO_DIRECT_COMMERCIAL_EVIDENCE_YET",
            known_standard_profile=False,
        )

    if _explicit_nonstandard(card) or case_type not in _STANDARD_COMMERCIAL_TYPES:
        return _result(
            route=STUDY_REQUIRED,
            profile=_PROFILE_NONSTANDARD,
            reason_code="CREDIBLE_COMMERCIAL_CASE_NEEDS_CUSTOM_STUDY_PROFILE",
            required=[
                "define what is actually being acquired",
                "define source-specific verification evidence",
                "define the commercial cost/value model",
            ],
            known_standard_profile=False,
        )

    if case_type == "DIRECT_OPPORTUNITY":
        required = ["verified lifecycle state", "source URL"]
        missing: list[str] = []
        if case_status not in {"ACTIVE_REQUIRES_VERIFICATION", "QUALIFIED_OPPORTUNITY"}:
            missing.append("verified lifecycle state")
        if not _source_present(card):
            missing.append("source URL")
        if missing:
            return _result(
                route=VERIFICATION_REQUIRED,
                profile=_PROFILE_DIRECT,
                reason_code="DIRECT_OPPORTUNITY_STANDARD_EVIDENCE_INCOMPLETE",
                required=required,
                missing=missing,
                known_standard_profile=True,
            )
        return _result(
            route=ACTIONABLE_NOW,
            profile=_PROFILE_DIRECT,
            reason_code="DIRECT_OPPORTUNITY_STANDARD_GATE_PASSED",
            required=required,
            known_standard_profile=True,
        )

    if case_type == "B2B_INVENTORY":
        required = ["source URL", "price", "quantity"]
        missing = []
        if not _source_present(card):
            missing.append("source URL")
        if not _has_values(card, "prices"):
            missing.append("price")
        if not _has_values(card, "quantities"):
            missing.append("quantity")
        if missing:
            return _result(
                route=VERIFICATION_REQUIRED,
                profile=_PROFILE_B2B,
                reason_code="B2B_STANDARD_EVIDENCE_INCOMPLETE",
                required=required,
                missing=missing,
                known_standard_profile=True,
            )
        return _result(
            route=ACTIONABLE_NOW,
            profile=_PROFILE_B2B,
            reason_code="B2B_STANDARD_GATE_PASSED",
            required=required,
            known_standard_profile=True,
        )

    # AUCTION_INVENTORY
    required = ["source URL", "price or current bid", "exact lot quantity"]
    missing = []
    if not _source_present(card):
        missing.append("source URL")
    if not _has_values(card, "prices"):
        missing.append("price or current bid")
    if not _has_values(card, "quantities"):
        missing.append("exact lot quantity")
    if missing:
        return _result(
            route=VERIFICATION_REQUIRED,
            profile=_PROFILE_AUCTION,
            reason_code="AUCTION_STANDARD_EVIDENCE_INCOMPLETE",
            required=required,
            missing=missing,
            known_standard_profile=True,
        )
    return _result(
        route=ACTIONABLE_NOW,
        profile=_PROFILE_AUCTION,
        reason_code="AUCTION_STANDARD_GATE_PASSED",
        required=required,
        known_standard_profile=True,
    )
