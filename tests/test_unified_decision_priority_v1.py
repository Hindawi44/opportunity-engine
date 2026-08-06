from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.unified_decision_priority import (
    ACTIONABLE_NOW,
    HISTORICAL_EVIDENCE,
    MARKET_WATCH,
    PRIORITY_SCHEMA_VERSION,
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
        "source_urls": [f"https://example.test/{case_id}"],
        "decision_owner": "HUMAN_OPERATOR",
    }


def test_direct_opportunity_outranks_stronger_liquidation_signal() -> None:
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

    all_cards, actionable, watch, historical = prioritise_decision_cards([signal, direct])

    assert all_cards[0]["case_id"] == "direct"
    assert actionable[0]["case_id"] == "direct"
    assert actionable[0]["decision_lane"] == ACTIONABLE_NOW
    assert actionable[0]["actionability_score"] > watch[0]["actionability_score"]
    assert watch[0]["case_id"] == "signal"
    assert watch[0]["decision_lane"] == MARKET_WATCH
    assert historical == []


def test_actionable_lane_orders_direct_then_b2b_then_auction_then_fabric() -> None:
    cards = [
        _card(case_id="fabric", headline="Fabric", case_type="FABRIC_PROCUREMENT", strength=95, offers=1),
        _card(case_id="auction", headline="Auction", case_type="AUCTION_INVENTORY", strength=95, offers=1),
        _card(case_id="b2b", headline="B2B", case_type="B2B_INVENTORY", strength=20, offers=1, prices=True, quantities=True),
        _card(case_id="direct", headline="Direct", case_type="DIRECT_OPPORTUNITY", strength=0, direct=1),
    ]

    _, actionable, _, _ = prioritise_decision_cards(cards)

    assert [card["case_id"] for card in actionable] == ["direct", "b2b", "auction", "fabric"]
    assert [card["actionability_tier"] for card in actionable] == [3, 4, 6, 7]


def test_historical_case_never_enters_actionable_or_watch_lane() -> None:
    historical_card = _card(
        case_id="old",
        headline="Ended lot",
        case_type="HISTORICAL_MARKET_EVIDENCE",
        strength=100,
        status="HISTORICAL_ONLY",
    )

    all_cards, actionable, watch, historical = prioritise_decision_cards([historical_card])

    assert actionable == []
    assert watch == []
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


def test_river_brief_exposes_separate_actionable_and_watch_lanes() -> None:
    result = build_unified_market_intelligence_river(_artifacts(), generated_at=NOW)
    brief = result["brief"]

    assert brief["priority_schema_version"] == PRIORITY_SCHEMA_VERSION
    assert brief["priority_rule"] == "ACTIONABILITY_BEFORE_SOURCE_SIGNAL_STRENGTH"
    assert brief["priority_counts"] == {
        ACTIONABLE_NOW: 1,
        MARKET_WATCH: 1,
        HISTORICAL_EVIDENCE: 0,
    }
    assert brief["top_actionable_card"]["headline"] == "Current clothing stock"
    assert brief["top_market_watch_card"]["headline"] == "High-confidence insolvency signal"
    assert brief["top_decision_card"] == brief["top_actionable_card"]
    assert brief["decision_cards"][0]["decision_lane"] == ACTIONABLE_NOW
    assert result["cases"]["cases"][0]["decision_lane"] == ACTIONABLE_NOW


def test_writer_attaches_priority_summary_to_existing_bulletin(tmp_path: Path) -> None:
    for filename, payload in _artifacts().items():
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "domain-market-intelligence-brief.txt").write_text("BASE\n", encoding="utf-8")

    brief = write_unified_market_intelligence_river(tmp_path)

    domain = json.loads((tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8"))
    attached = domain["unified_market_intelligence_river"]
    assert attached["priority_schema_version"] == PRIORITY_SCHEMA_VERSION
    assert attached["top_actionable_card"]["headline"] == "Current clothing stock"
    assert attached["top_market_watch_card"]["headline"] == "High-confidence insolvency signal"
    text = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert "UNIFIED DECISION PRIORITY" in text
    assert "top_actionable: Current clothing stock" in text
    assert brief["top_decision_card"] == brief["top_actionable_card"]


def test_priority_installs_before_existing_river_cli_hook() -> None:
    text = INIT_FILE.read_text(encoding="utf-8")
    assert "install_unified_decision_priority" in text
    assert text.index("install_unified_decision_priority()") < text.index(
        "install_unified_market_intelligence_river_cli_hook()"
    )
