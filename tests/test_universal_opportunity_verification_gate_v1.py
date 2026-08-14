from __future__ import annotations

from opportunity_engine.discovery.central_intelligence_orchestrator import (
    build_central_intelligence_brief,
)
from opportunity_engine.discovery.universal_opportunity_verification_gate import (
    ACTIONABLE_NOW,
    MARKET_WATCH,
    STUDY_REQUIRED,
    VERIFICATION_REQUIRED,
    classify_opportunity_verification,
)


def _card(
    case_type: str,
    *,
    direct: int = 0,
    offers: int = 0,
    status: str = "WATCH",
    price: bool = False,
    quantity: bool = False,
    source: bool = True,
    **extra: object,
) -> dict:
    return {
        "case_id": "case:test",
        "headline": "Test commercial case",
        "case_type": case_type,
        "case_status": status,
        "direct_opportunity_count": direct,
        "offer_count": offers,
        "commercial_snapshot": {
            "prices": [{"amount": 100, "currency": "NOK"}] if price else [],
            "quantities": [{"quantity": 10, "unit": "items"}] if quantity else [],
            "brands": [],
        },
        "source_urls": ["https://example.test/case"] if source else [],
        "missing_information": [],
        "risk_flags": [],
        **extra,
    }


def test_direct_profile_uses_lifecycle_verification_not_generic_matrix() -> None:
    verified = classify_opportunity_verification(
        _card(
            "DIRECT_OPPORTUNITY",
            direct=1,
            status="ACTIVE_REQUIRES_VERIFICATION",
        )
    )
    unverified = classify_opportunity_verification(
        _card("DIRECT_OPPORTUNITY", direct=1, status="WATCH")
    )

    assert verified["route"] == ACTIONABLE_NOW
    assert unverified["route"] == VERIFICATION_REQUIRED
    assert "verified lifecycle state" in unverified["missing_required_evidence"]


def test_auction_profile_never_invents_quantity_from_vague_lot_wording() -> None:
    result = classify_opportunity_verification(
        _card(
            "AUCTION_INVENTORY",
            offers=1,
            price=True,
            quantity=False,
        )
    )

    assert result["route"] == VERIFICATION_REQUIRED
    assert result["missing_required_evidence"] == ["exact lot quantity"]
    assert result["estimated_values_added"] is False


def test_nonstandard_commercial_case_is_studied_not_rejected() -> None:
    result = classify_opportunity_verification(
        _card(
            "BUSINESS_TRANSFER_WITH_STOCK_SHARE",
            offers=1,
            price=False,
            quantity=False,
        )
    )

    assert result["route"] == STUDY_REQUIRED
    assert result["study_required"] is True
    assert result["known_standard_profile"] is False
    assert result["required_evidence"] == [
        "define what is actually being acquired",
        "define source-specific verification evidence",
        "define the commercial cost/value model",
    ]
    assert result["automatic_purchase"] is False


def test_early_liquidation_signal_remains_market_watch() -> None:
    result = classify_opportunity_verification(
        _card("COMPANY_LIQUIDATION", offers=0, direct=0)
    )
    assert result["route"] == MARKET_WATCH


def test_central_operator_prioritises_verification_then_study_before_watch() -> None:
    verification = {
        **_card("AUCTION_INVENTORY", offers=1, price=True, quantity=False),
        "decision_lane": VERIFICATION_REQUIRED,
        "verification_gate": {
            "missing_required_evidence": ["exact lot quantity"],
            "required_evidence": ["source URL", "price or current bid", "exact lot quantity"],
        },
    }
    study = {
        **_card("OTHER_COMMERCIAL_CASE", offers=1),
        "case_id": "case:study",
        "headline": "Unusual stock partnership",
        "decision_lane": STUDY_REQUIRED,
        "verification_gate": {
            "study_required": True,
            "required_evidence": ["define what is actually being acquired"],
        },
    }
    watch = {
        **_card("COMPANY_LIQUIDATION"),
        "case_id": "case:watch",
        "headline": "Closure signal",
        "decision_lane": MARKET_WATCH,
    }
    unified = {
        "status": "SUCCESS",
        "priority_counts": {
            "ACTIONABLE_NOW": 0,
            VERIFICATION_REQUIRED: 1,
            STUDY_REQUIRED: 1,
            MARKET_WATCH: 1,
            "HISTORICAL_EVIDENCE": 0,
        },
        "actionable_now": [],
        "verification_required": [verification],
        "study_required": [study],
        "market_watch": [watch],
        "top_verification_required_card": verification,
        "top_study_required_card": study,
        "top_market_watch_card": watch,
        "universal_verification_gate_enabled": True,
    }

    brief = build_central_intelligence_brief(
        {"market_coverage": ["NO", "SE", "DE"]},
        unified,
        fabric_report={"candidate_count": 0, "candidates": []},
    )

    assert brief["top_verification_required_opportunity"]["headline"] == "Test commercial case"
    assert brief["top_study_required_opportunity"]["headline"] == "Unusual stock partnership"
    assert brief["primary_human_action"]["action_type"] == (
        "COMPLETE_STANDARD_OPPORTUNITY_VERIFICATION"
    )
    assert brief["primary_human_action"]["verification_focus"] == ["exact lot quantity"]
    assert brief["nonstandard_opportunities_are_preserved_for_study"] is True
