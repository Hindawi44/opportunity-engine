from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.unified_decision_priority import (
    ACTIONABLE_NOW,
    HISTORICAL_EVIDENCE,
    MARKET_WATCH,
    PRIORITY_SCHEMA_VERSION,
    STUDY_REQUIRED,
    VERIFICATION_REQUIRED,
    prioritise_decision_cards,
)
from opportunity_engine.discovery.unified_market_intelligence_river import (
    build_unified_market_intelligence_river,
    write_unified_market_intelligence_river,
)

NOW = datetime(2026, 8, 6, 13, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"


def _card(
    *,
    case_id: str,
    headline: str,
    case_type: str,
    strength: float,
    direct: int = 0,
    offers: int = 0,
    status: str = "WATCH",
    prices: bool = False,
    quantities: bool = False,
    source_urls: bool = True,
    **extra: object,
) -> dict:
    return {
        "case_id": case_id,
        "headline": headline,
        "case_type": case_type,
        "case_status": status,
        "commercial_strength": strength,
        "direct_opportunity_count": direct,
        "offer_count": offers,
        "signal_count": 1 if not direct and not offers else 0,
        "commercial_snapshot": {
            "prices": [{"amount": 100, "currency": "EUR"}] if prices else [],
            "quantities": [{"quantity": 50, "unit": "items"}] if quantities else [],
            "brands": [],
        },
        "missing_information": [],
        "risk_flags": [],
        "recommended_next_action": "REVIEW",
        "source_urls": [f"https://example.test/{case_id}"] if source_urls else [],
        "decision_owner": "HUMAN_OPERATOR",
        **extra,
    }


def test_verified_direct_opportunity_outranks_stronger_liquidation_signal() -> None:
    signal = _card(
        case_id="signal",
        headline="Very strong insolvency signal",
        case_type="COMPANY_LIQUIDATION",
        strength=99,
    )
    direct = _card(
        case_id="direct",
        headline="Current clothing stock opportunity",
        case_type="DIRECT_OPPORTUNITY",
        strength=0,
        direct=1,
        status="ACTIVE_REQUIRES_VERIFICATION",
    )

    all_cards, actionable, review, historical = prioritise_decision_cards([signal, direct])

    assert all_cards[0]["case_id"] == "direct"
    assert actionable[0]["case_id"] == "direct"
    assert actionable[0]["decision_lane"] == ACTIONABLE_NOW
    assert review[0]["case_id"] == "signal"
    assert review[0]["decision_lane"] == MARKET_WATCH
    assert historical == []


def test_unverified_direct_opportunity_enters_verification_required() -> None:
    direct = _card(
        case_id="direct",
        headline="Exact quantity missing",
        case_type="DIRECT_OPPORTUNITY",
        strength=80,
        direct=1,
        status="WATCH",
    )

    all_cards, actionable, review, historical = prioritise_decision_cards([direct])

    assert actionable == []
    assert historical == []
    assert review[0]["case_id"] == "direct"
    assert review[0]["decision_lane"] == VERIFICATION_REQUIRED
    assert review[0]["priority_class"] == "DIRECT_OPPORTUNITY_VERIFICATION_REQUIRED"
    assert review[0]["verification_gate"]["gate_passed"] is False
    assert all_cards == review


def test_standard_b2b_requires_price_and_quantity_before_actionable() -> None:
    incomplete = _card(
        case_id="b2b-incomplete",
        headline="B2B stock without manifest quantity",
        case_type="B2B_INVENTORY",
        strength=90,
        offers=1,
        prices=True,
        quantities=False,
    )
    complete = _card(
        case_id="b2b-complete",
        headline="B2B stock with price and quantity",
        case_type="B2B_INVENTORY",
        strength=60,
        offers=1,
        prices=True,
        quantities=True,
    )

    all_cards, actionable, review, _ = prioritise_decision_cards([incomplete, complete])

    assert actionable[0]["case_id"] == "b2b-complete"
    assert review[0]["case_id"] == "b2b-incomplete"
    assert review[0]["decision_lane"] == VERIFICATION_REQUIRED
    assert review[0]["verification_gate"]["missing_required_evidence"] == ["quantity"]
    assert all_cards[0]["case_id"] == "b2b-complete"


def test_nonstandard_real_commercial_case_is_preserved_for_study() -> None:
    unusual = _card(
        case_id="unusual",
        headline="Store contents transfer with revenue-share terms",
        case_type="OTHER_COMMERCIAL_CASE",
        strength=92,
        offers=1,
        prices=False,
        quantities=False,
    )

    all_cards, actionable, review, historical = prioritise_decision_cards([unusual])

    assert actionable == []
    assert historical == []
    assert review[0]["decision_lane"] == STUDY_REQUIRED
    assert review[0]["verification_gate"]["study_required"] is True
    assert review[0]["verification_gate"]["known_standard_profile"] is False
    assert review[0]["verification_gate"]["reason_code"] == (
        "CREDIBLE_COMMERCIAL_CASE_NEEDS_CUSTOM_STUDY_PROFILE"
    )
    assert all_cards == review


def test_actionable_lane_orders_direct_then_b2b_then_auction_then_fabric() -> None:
    cards = [
        _card(case_id="fabric", headline="Fabric", case_type="FABRIC_PROCUREMENT", strength=95, offers=1),
        _card(
            case_id="auction",
            headline="Auction",
            case_type="AUCTION_INVENTORY",
            strength=95,
            offers=1,
            prices=True,
            quantities=True,
        ),
        _card(
            case_id="b2b",
            headline="B2B",
            case_type="B2B_INVENTORY",
            strength=20,
            offers=1,
            prices=True,
            quantities=True,
        ),
        _card(
            case_id="direct",
            headline="Direct",
            case_type="DIRECT_OPPORTUNITY",
            strength=0,
            direct=1,
            status="ACTIVE_REQUIRES_VERIFICATION",
        ),
    ]

    _, actionable, _, _ = prioritise_decision_cards(cards)

    assert [card["case_id"] for card in actionable] == ["direct", "b2b", "auction", "fabric"]
    assert [card["actionability_tier"] for card in actionable] == [2, 4, 6, 7]


def test_historical_case_never_enters_active_review_lanes() -> None:
    historical_card = _card(
        case_id="old",
        headline="Ended lot",
        case_type="HISTORICAL_MARKET_EVIDENCE",
        strength=100,
        status="HISTORICAL_ONLY",
    )

    all_cards, actionable, review, historical = prioritise_decision_cards([historical_card])

    assert actionable == []
    assert review == []
    assert historical[0]["decision_lane"] == HISTORICAL_EVIDENCE
    assert historical[0]["actionability_score"] == 0
    assert all_cards == historical


def _artifacts() -> dict[str, dict]:
    return {
        "domain-market-intelligence-brief.json": {
            "generated_at": NOW.isoformat(),
            "current_direct_opportunities": [
                {
                    "opportunity_identity": "current:1",
                    "title": "Current clothing stock",
                    "market_code": "NO",
                    "source_name": "Auction House",
                    "source_url": "https://auction.example/current/1",
                    "workflow_status": "REQUIRES_VERIFICATION",
                    "listing_status": "ACTIVE",
                    "discovery_score": 0,
                    "missing_information": ["EXACT LOT QUANTITY"],
                }
            ],
            "early_signals_to_watch": [
                {
                    "signal_id": "liquidation:1",
                    "signal_type": "INSOLVENCY_OR_LIQUIDATION",
                    "value": "Company is insolvent",
                    "source": "Official register",
                    "source_country": "NO",
                    "source_url": "https://register.example/1",
                    "title": "High-confidence insolvency signal",
                    "first_observed_at": NOW.isoformat(),
                    "latest_observed_at": NOW.isoformat(),
                    "status": "WATCH",
                    "confidence": 0.99,
                }
            ],
        }
    }


def test_river_brief_separates_verification_required_from_market_watch() -> None:
    result = build_unified_market_intelligence_river(_artifacts(), generated_at=NOW)
    brief = result["brief"]

    assert brief["priority_schema_version"] == PRIORITY_SCHEMA_VERSION
    assert brief["priority_rule"] == (
        "VERIFIED_ACTIONABILITY_THEN_VERIFICATION_THEN_STUDY_THEN_WATCH"
    )
    assert brief["priority_counts"] == {
        ACTIONABLE_NOW: 0,
        VERIFICATION_REQUIRED: 1,
        STUDY_REQUIRED: 0,
        MARKET_WATCH: 1,
        HISTORICAL_EVIDENCE: 0,
    }
    assert brief["top_actionable_card"] is None
    assert brief["top_verification_required_card"]["headline"] == "Current clothing stock"
    assert brief["top_market_watch_card"]["headline"] == "High-confidence insolvency signal"
    assert brief["top_decision_card"] == brief["top_verification_required_card"]
    assert brief["decision_cards"][0]["decision_lane"] == VERIFICATION_REQUIRED
    assert result["cases"]["cases"][0]["decision_lane"] == VERIFICATION_REQUIRED


def test_writer_attaches_all_verification_lanes_to_existing_bulletin(tmp_path: Path) -> None:
    for filename, payload in _artifacts().items():
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "domain-market-intelligence-brief.txt").write_text("BASE\n", encoding="utf-8")

    brief = write_unified_market_intelligence_river(tmp_path)

    domain = json.loads((tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8"))
    attached = domain["unified_market_intelligence_river"]
    assert attached["priority_schema_version"] == PRIORITY_SCHEMA_VERSION
    assert attached["top_actionable_card"] is None
    assert attached["top_verification_required_card"]["headline"] == "Current clothing stock"
    assert attached["top_market_watch_card"]["headline"] == "High-confidence insolvency signal"
    assert attached["universal_verification_gate_enabled"] is True
    text = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert "UNIFIED DECISION PRIORITY" in text
    assert "top_actionable: NONE" in text
    assert "top_verification_required: Current clothing stock" in text
    assert "top_market_watch: High-confidence insolvency signal" in text
    assert brief["top_decision_card"] == brief["top_verification_required_card"]


def test_priority_installs_before_existing_river_cli_hook() -> None:
    text = INIT_FILE.read_text(encoding="utf-8")
    assert "install_unified_decision_priority" in text
    assert text.index("install_unified_decision_priority()") < text.index(
        "install_unified_market_intelligence_river_cli_hook()"
    )
