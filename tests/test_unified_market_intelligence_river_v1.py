from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.unified_market_intelligence_river import (
    BRIEF_FILENAME,
    CASES_FILENAME,
    DECISION_OWNER,
    ITEMS_FILENAME,
    IntelligenceRecordKind,
    MarketCaseType,
    build_unified_market_intelligence_river,
    write_unified_market_intelligence_river,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"
HOOK_FILE = ROOT / "src/opportunity_engine/discovery/unified_market_intelligence_river_cli_hook.py"


def _signal(*, signal_id: str = "official:123", company: str = "Example AS") -> dict:
    return {
        "signal_id": signal_id,
        "signal_type": "INSOLVENCY_OR_LIQUIDATION",
        "value": f"{company} is being liquidated",
        "source": "Official register",
        "source_country": "NO",
        "source_url": "https://register.example/entities/123",
        "title": f"Liquidation: {company}",
        "company_name": company,
        "seller_name": None,
        "location": "Oslo",
        "first_observed_at": NOW.isoformat(),
        "latest_observed_at": NOW.isoformat(),
        "observed_at": NOW.isoformat(),
        "status": "WATCH",
        "confidence": 0.95,
        "evidence": [],
        "metadata": {"organisation_number": "123456789", "signal_only": True},
    }


def _opportunity() -> dict:
    return {
        "opportunity_identity": "auction:lot-1",
        "title": "Example AS clothing stock lot",
        "market_code": "NO",
        "source_name": "Auction House",
        "source_url": "https://auction.example/lots/1",
        "workflow_status": "ACTIVE_OPPORTUNITY",
        "listing_status": "ACTIVE",
        "discovery_score": 82,
        "company_name": "Example AS",
        "seller_name": None,
        "location": "Oslo",
        "quantity": 500,
        "related_signal_id": "official:123",
        "organisation_number": "123456789",
    }


def _stockhurt_candidate(*, candidate_id: str, url: str, title: str, brand: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "feed_family": "STOCKHURT_OFFICIAL_CATALOG_ENRICHMENT_V1",
        "source_name": "Stock-Hurt",
        "source_country": "PL",
        "source_url": url,
        "title": title,
        "seller_name": "Stock-Hurt",
        "listing_status": "ACTIVE_REQUIRES_VERIFICATION",
        "opportunity_state": "EARLY_B2B_SIGNAL_REQUIRES_VERIFICATION",
        "b2b_relevance_score": 70,
        "quantity": None,
        "quantity_unit": None,
        "minimum_order": 20,
        "minimum_order_unit": "kg",
        "currency": "EUR",
        "unit_price": None,
        "brands": [brand],
        "stock_location": "Poland",
        "manifest_available": False,
        "missing_information": ["VISIBLE_PRICE_OR_BID", "MANIFEST_OR_PACKING_LIST"],
        "source_evidence": [
            {
                "field": "official_product_page",
                "source_url": url,
                "page_sha256": "abc123",
            }
        ],
        "page_sha256": "abc123",
        "observed_at": NOW.isoformat(),
    }


def _fabric_candidate() -> dict:
    return {
        "candidate_id": "fabric:lace-1",
        "source_name": "Bridal Fabrics",
        "source_country": "GB",
        "source_url": "https://fabric.example/bridal-lace",
        "title": "Bridal lace collection",
        "observed_at": NOW.isoformat(),
        "procurement_relevance_score": 90,
        "fabric_terms": ["lace", "tulle"],
        "bridal_terms": ["bridal"],
        "missing_information": ["VISIBLE_PRICE", "SHIPPING_TO_NORWAY"],
    }


def _artifacts() -> dict[str, dict]:
    signal = _signal()
    stock_1 = _stockhurt_candidate(
        candidate_id="stock:1",
        url="https://stockhurt.com/en/product/brand-a/",
        title="Brand A Grade A Clothing",
        brand="Brand A",
    )
    stock_1_duplicate = dict(stock_1)
    stock_1_duplicate["candidate_id"] = "search-result:1"
    stock_1_duplicate["page_sha256"] = None
    stock_1_duplicate["source_evidence"] = []
    stock_2 = _stockhurt_candidate(
        candidate_id="stock:2",
        url="https://stockhurt.com/en/product/brand-b/",
        title="Brand B Grade A Clothing",
        brand="Brand B",
    )
    return {
        "domain-market-intelligence-brief.json": {
            "generated_at": NOW.isoformat(),
            "current_direct_opportunities": [_opportunity()],
            "early_signals_to_watch": [signal],
        },
        "brave-market-signal-radar.json": {
            "generated_at": NOW.isoformat(),
            "sources": [{"signals": [signal]}],
        },
        "fabric-procurement-watch.json": {
            "generated_at": NOW.isoformat(),
            "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
            "candidates": [_fabric_candidate()],
        },
        "stockhurt-b2b-feed.json": {
            "generated_at": NOW.isoformat(),
            "feed_family": "STOCK_HURT_B2B_FEED_V1",
            "candidates": [stock_1_duplicate],
        },
        "stockhurt-official-catalog-enrichment.json": {
            "generated_at": NOW.isoformat(),
            "feed_family": "STOCKHURT_OFFICIAL_CATALOG_ENRICHMENT_V1",
            "candidates": [stock_1, stock_2],
        },
    }


def test_builds_one_river_without_promoting_or_duplicating() -> None:
    result = build_unified_market_intelligence_river(_artifacts(), generated_at=NOW)
    items = result["items"]
    cases = result["cases"]
    brief = result["brief"]

    assert items["source_observation_count"] == 7
    assert items["deduplicated_item_count"] == 5
    assert items["duplicate_observation_count"] == 2
    assert items["record_kind_counts"] == {
        "B2B_STOCK_OFFER": 2,
        "BUSINESS_EVENT_SIGNAL": 1,
        "CANONICAL_OPPORTUNITY": 1,
        "FABRIC_PROCUREMENT_ITEM": 1,
    }
    assert all(item["decision_owner"] == DECISION_OWNER for item in items["items"])
    assert items["promotion_to_opportunity_allowed"] is False
    assert items["automatic_purchase"] is False

    company_cases = [case for case in cases["cases"] if case["case_type"] == MarketCaseType.COMPANY_LIQUIDATION]
    assert len(company_cases) == 1
    assert company_cases[0]["item_count"] == 2
    assert company_cases[0]["grouping_basis"] == "ORGANISATION"

    stock_cases = [case for case in cases["cases"] if case["case_type"] == MarketCaseType.B2B_INVENTORY]
    assert len(stock_cases) == 1
    assert stock_cases[0]["item_count"] == 2
    assert stock_cases[0]["grouping_basis"] == "SELLER"

    relationship_types = {item["relationship_type"] for item in cases["relationships"]}
    assert "SAME_ORGANISATION_NUMBER" in relationship_types
    assert "SAME_SELLER" in relationship_types
    assert "SUPPORTS" in relationship_types

    assert brief["counts"]["source_observations"] == 7
    assert brief["counts"]["deduplicated_items"] == 5
    assert brief["counts"]["market_cases"] == 3
    assert brief["decision_owner"] == DECISION_OWNER
    assert brief["truthful_zero_result"] is False


def test_record_kinds_keep_fabric_signals_and_opportunities_distinct() -> None:
    result = build_unified_market_intelligence_river(_artifacts(), generated_at=NOW)
    kinds = {item["record_kind"] for item in result["items"]["items"]}
    assert IntelligenceRecordKind.FABRIC_PROCUREMENT_ITEM in kinds
    assert IntelligenceRecordKind.BUSINESS_EVENT_SIGNAL in kinds
    assert IntelligenceRecordKind.CANONICAL_OPPORTUNITY in kinds
    assert IntelligenceRecordKind.B2B_STOCK_OFFER in kinds


def test_writer_creates_three_artifacts_and_attaches_summary(tmp_path: Path) -> None:
    for filename, payload in _artifacts().items():
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "domain-market-intelligence-brief.txt").write_text("BASE\n", encoding="utf-8")

    brief = write_unified_market_intelligence_river(tmp_path)

    for filename in (ITEMS_FILENAME, CASES_FILENAME, BRIEF_FILENAME):
        assert (tmp_path / filename).exists()
    domain_brief = json.loads((tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8"))
    assert domain_brief["unified_market_intelligence_river"]["status"] == "SUCCESS"
    assert domain_brief["unified_market_intelligence_river"]["output_files"] == [
        ITEMS_FILENAME,
        CASES_FILENAME,
        BRIEF_FILENAME,
    ]
    rendered = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert "UNIFIED MARKET INTELLIGENCE RIVER" in rendered
    assert brief["automatic_purchase"] is False


def test_empty_inputs_are_a_truthful_zero() -> None:
    result = build_unified_market_intelligence_river({}, generated_at=NOW)
    assert result["items"]["status"] == "VALID_ZERO"
    assert result["items"]["deduplicated_item_count"] == 0
    assert result["cases"]["case_count"] == 0
    assert result["brief"]["truthful_zero_result"] is True
    assert result["brief"]["top_decision_card"] is None


def test_existing_bulletin_cli_installs_post_run_river_hook() -> None:
    init_text = INIT_FILE.read_text(encoding="utf-8")
    hook_text = HOOK_FILE.read_text(encoding="utf-8")
    assert "install_unified_market_intelligence_river_cli_hook" in init_text
    assert "build_domain_market_intelligence_feed.py" in hook_text
    assert "atexit.register" in hook_text
    assert "write_unified_market_intelligence_river(output_dir)" in hook_text
