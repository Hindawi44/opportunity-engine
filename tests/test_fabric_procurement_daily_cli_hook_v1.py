from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.fabric_procurement_watch_cli_hook import (
    write_daily_fabric_procurement_watch,
)


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"
RIVER_FILE = ROOT / "src/opportunity_engine/discovery/unified_market_intelligence_river.py"


def _report() -> dict[str, Any]:
    return {
        "schema_version": "fabric-procurement-watch-1.0",
        "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
        "purpose": "TAILORING_SHOP_FABRIC_PROCUREMENT_INTELLIGENCE",
        "search_language": "en+it",
        "freshness": None,
        "approved_official_domains": [
            "evaresource.com",
            "fabrichouse.com",
            "tessutistockprato.it",
            "tessutiastock.com",
            "bridalfabrics.com",
        ],
        "query_budget_total": 5,
        "requests_made": 5,
        "status_counts": {"SUCCESS": 5},
        "candidate_count": 1,
        "candidates": [
            {
                "candidate_id": "fabric-watch:verian-prato:test",
                "source_name": "Verian Tessuti a Stock",
                "source_country": "IT",
                "source_kind": "PRATO_DEADSTOCK",
                "location": "Prato, IT",
                "title": "Tessuti a stock lana e seta",
                "source_url": "https://www.tessutistockprato.it/il-magazzino",
                "fabric_terms": ["lana", "seta", "tessuti"],
                "bridal_terms": [],
                "price": None,
                "currency": None,
                "quantity": 1000.0,
                "quantity_unit": "m",
                "procurement_relevance_score": 85,
                "recommended_operator_action": "REVIEW_SAMPLE_PRICE_AND_SHIPPING",
            }
        ],
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_daily_hook_disables_freshness_and_attaches_prato_to_existing_brief(
    tmp_path: Path,
) -> None:
    calls: list[tuple[Mapping[str, str], str | None]] = []

    def fake_collector(*, environment: Mapping[str, str], freshness: str | None):
        calls.append((environment, freshness))
        return _report()

    brief_json = tmp_path / "domain-market-intelligence-brief.json"
    brief_json.write_text(json.dumps({"market_coverage": ["NO", "SE", "DE"]}), encoding="utf-8")
    brief_text = tmp_path / "domain-market-intelligence-brief.txt"
    brief_text.write_text("BASE BULLETIN\n", encoding="utf-8")

    report = write_daily_fabric_procurement_watch(
        tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        collector=fake_collector,
    )

    assert calls == [({"BRAVE_SEARCH_API_KEY": "secret"}, None)]
    assert report["candidate_count"] == 1
    artifact = json.loads(
        (tmp_path / "fabric-procurement-watch.json").read_text(encoding="utf-8")
    )
    assert artifact["freshness"] is None
    assert artifact["candidates"][0]["location"] == "Prato, IT"

    brief = json.loads(brief_json.read_text(encoding="utf-8"))
    section = brief["fabric_procurement_watch"]
    assert brief["market_coverage"] == ["NO", "SE", "DE"]
    assert brief["daily_market_visibility"]["countries"] == ["NO", "SE", "DE", "IT"]
    assert brief["daily_market_visibility"]["primary_opportunity_markets"] == [
        "NO",
        "SE",
        "DE",
    ]
    assert brief["daily_market_visibility"]["advisory_markets"] == ["IT"]
    assert brief["daily_market_visibility"]["market_roles"]["IT"] == "FABRIC_PROCUREMENT"
    assert section["market_code"] == "IT"
    assert section["market_role"] == "FABRIC_PROCUREMENT"
    assert section["market_status"] == "ACTIVE"
    assert section["prato_candidate_count"] == 1
    assert section["top_prato_candidates"][0]["source_country"] == "IT"
    assert section["top_prato_candidates"][0]["quantity"] == 1000.0
    assert section["promotion_to_opportunity_allowed"] is False
    assert section["automatic_purchase"] is False

    rendered = brief_text.read_text(encoding="utf-8")
    assert "FABRIC PROCUREMENT WATCH" in rendered
    assert "daily_market_visibility: NO | SE | DE | IT" in rendered
    assert "IT_market_role: FABRIC_PROCUREMENT" in rendered
    assert "[IT/Prato] Verian Tessuti a Stock" in rendered
    assert "purchase_mode: MANUAL_ONLY" in rendered


def test_fabric_hook_is_registered_after_river_so_it_executes_before_river() -> None:
    text = INIT_FILE.read_text(encoding="utf-8")
    river_call = text.index("install_unified_market_intelligence_river_cli_hook()")
    fabric_call = text.index("install_fabric_procurement_watch_cli_hook()")
    assert river_call < fabric_call


def test_existing_unified_river_consumes_fabric_procurement_artifact() -> None:
    text = RIVER_FILE.read_text(encoding="utf-8")
    assert '"fabric-procurement-watch.json"' in text
    assert 'FABRIC_PROCUREMENT_ITEM = "FABRIC_PROCUREMENT_ITEM"' in text
    assert 'family == "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1"' in text
