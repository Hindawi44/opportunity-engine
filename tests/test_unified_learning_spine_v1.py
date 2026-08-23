from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.unified_learning_spine import (
    build_unified_learning_spine,
    write_unified_learning_spine,
)


INIT = Path("src/opportunity_engine/discovery/__init__.py")
HOOK = Path("src/opportunity_engine/discovery/unified_learning_spine_cli_hook.py")


def _river_items() -> dict:
    return {
        "schema_version": "unified-intelligence-items-1.0",
        "status": "SUCCESS",
        "generated_at": "2026-08-23T19:30:00+00:00",
        "items": [
            {
                "intelligence_id": "fr-clothing-1",
                "record_kind": "B2B_STOCK_OFFER",
                "source_name": "French Stock Source",
                "source_country": "FR",
                "source_url": "https://example.fr/lot-vetements",
                "title": "Lot de vêtements femme avec stock disponible",
                "commercial_state": "B2B_LEAD_REQUIRES_VERIFICATION",
                "latest_seen": "2026-08-23T19:20:00+00:00",
                "details": {"inventory_type": "CLOTHING"},
                "evidence": [],
            },
            {
                "intelligence_id": "nl-fabric-1",
                "record_kind": "FABRIC_PROCUREMENT_ITEM",
                "source_name": "Dutch Fabric Source",
                "source_country": "NL",
                "source_url": "https://example.nl/stofrollen",
                "title": "Partij stofrollen en stoffen op voorraad",
                "commercial_state": "REQUIRES_VERIFICATION",
                "latest_seen": "2026-08-23T19:21:00+00:00",
                "details": {"inventory_type": "FABRIC"},
                "evidence": [],
            },
            {
                "intelligence_id": "it-clothing-1",
                "record_kind": "AUCTION_LOT",
                "source_name": "Italian Auction Source",
                "source_country": "IT",
                "source_url": "https://example.it/lotto-abbigliamento",
                "title": "Lotto abbigliamento: giacche e pantaloni",
                "commercial_state": "REQUIRES_VERIFICATION",
                "latest_seen": "2026-08-23T19:22:00+00:00",
                "details": {"sale_mode": "AUCTION"},
                "evidence": [],
            },
            {
                "intelligence_id": "de-granite-1",
                "record_kind": "B2B_STOCK_OFFER",
                "source_name": "General Stock Source",
                "source_country": "DE",
                "source_url": "https://example.de/granit",
                "title": "Restposten Granit Baustoffe",
                "commercial_state": "REQUIRES_VERIFICATION",
                "latest_seen": "2026-08-23T19:23:00+00:00",
                "details": {"inventory_type": "BUILDING_MATERIALS"},
                "evidence": [],
            },
        ],
    }


def _search_success_memory() -> dict:
    return {
        "schema_version": "search-success-memory-1.0",
        "run_count": 4,
        "route_learning": [
            {
                "provider": "exa",
                "market_code": "FR",
                "parent_domain": "friptadium.com",
                "pathway": "AGGREGATE_CHILD",
                "query": "France vêtements mode lot prix quantité stock",
                "independent_run_count": 4,
                "supporting_run_ids": ["run-1", "run-2", "run-3", "run-4"],
                "status": "REPLICATED_FOR_REVIEW",
                "verified_exact_lot_url_count": 2,
                "verified_exact_lot_urls": [
                    "https://friptadium.com/products/hauts-femme-au-kilo",
                    "https://friptadium.com/products/robes-femme-au-kilo",
                ],
                "automatic_activation": False,
                "production_query_mutation": False,
            }
        ],
        "automatic_provider_activation": False,
        "production_mutation": False,
    }


def _miss_memory() -> dict:
    return {
        "schema_version": "missed-opportunity-learning-loop-1.0",
        "case_count": 2,
        "cases": [
            {
                "case_id": "MISS-IT-CLOTHING-1",
                "market_code": "IT",
                "discovered_by": "human_review",
                "observed_at": "2026-08-22T10:00:00+00:00",
                "opportunity_type": "CLOTHING_INVENTORY",
                "stock_proven": True,
                "ground_truth": {
                    "company": "Moda Stock SRL",
                    "url": "https://example.it/stock-abbigliamento",
                },
                "trace": {"query_generated": False},
                "learning_evidence_text": "stock abbigliamento giacche pantaloni",
                "root_cause": "QUERY_GAP",
                "learning_status": "DIAGNOSED",
                "repeat_miss": False,
            },
            {
                "case_id": "MISS-DE-GRANITE-1",
                "market_code": "DE",
                "discovered_by": "legacy",
                "observed_at": "2026-08-22T11:00:00+00:00",
                "opportunity_type": "GENERAL_MERCHANDISE",
                "stock_proven": True,
                "ground_truth": {
                    "company": "Stone GmbH",
                    "url": "https://example.de/granit-stock",
                },
                "trace": {"query_generated": False},
                "learning_evidence_text": "Granit Baustoffe Restposten",
                "root_cause": "QUERY_GAP",
                "learning_status": "DIAGNOSED",
                "repeat_miss": False,
            },
        ],
    }


def _daily_learning() -> dict:
    return {
        "schema_version": "daily-learning-operator-1.1",
        "generated_at": "2026-08-23T19:30:00+00:00",
        "known_missed_opportunity_count": 1,
        "out_of_domain_excluded_case_count": 1,
        "shadow_proven_term_count": 0,
        "safe_learning_promotion_eligible_count": 0,
        "automatic_query_activation": False,
    }


def test_spine_normalises_multi_market_evidence_without_losing_market_identity() -> None:
    spine = build_unified_learning_spine(
        unified_intelligence_items=_river_items(),
        search_success_memory=_search_success_memory(),
        missed_opportunity_memory=_miss_memory(),
        daily_learning=_daily_learning(),
    )

    assert spine["schema_version"] == "unified-learning-spine-1.0"
    assert spine["status"] == "SUCCESS"
    assert spine["market_counts"] == {"FR": 2, "IT": 2, "NL": 1}
    assert spine["domain_counts"] == {
        "CLOTHING_INVENTORY": 4,
        "FABRIC_PROCUREMENT": 1,
    }
    assert spine["evidence_kind_counts"] == {
        "MARKET_OBSERVATION": 3,
        "MISSED_OPPORTUNITY": 1,
        "SEARCH_ROUTE_SUCCESS": 1,
    }
    assert spine["out_of_domain_excluded_count"] == 2
    assert set(spine["out_of_domain_excluded_ids"]) == {
        "de-granite-1",
        "MISS-DE-GRANITE-1",
    }

    required = {
        "learning_evidence_id",
        "evidence_kind",
        "market_code",
        "project_domain",
        "source_name",
        "provider",
        "query",
        "url",
        "result_type",
        "outcome",
        "miss_reason",
        "route",
        "source_identity",
        "observed_at",
        "supporting_run_ids",
        "metadata",
    }
    for record in spine["records"]:
        assert required <= set(record)
        assert record["project_domain"] in {
            "CLOTHING_INVENTORY",
            "FABRIC_PROCUREMENT",
        }

    fr_route = next(
        record
        for record in spine["records"]
        if record["evidence_kind"] == "SEARCH_ROUTE_SUCCESS"
    )
    assert fr_route["market_code"] == "FR"
    assert fr_route["provider"] == "exa"
    assert fr_route["route"] == "AGGREGATE_CHILD"
    assert fr_route["outcome"] == "REPLICATED_FOR_REVIEW"
    assert fr_route["metadata"]["independent_run_count"] == 4
    assert fr_route["metadata"]["verified_exact_lot_url_count"] == 2

    it_miss = next(
        record
        for record in spine["records"]
        if record["evidence_kind"] == "MISSED_OPPORTUNITY"
    )
    assert it_miss["market_code"] == "IT"
    assert it_miss["miss_reason"] == "QUERY_GAP"
    assert it_miss["outcome"] == "MISSED"

    assert spine["automatic_query_activation"] is False
    assert spine["automatic_provider_activation"] is False
    assert spine["automatic_source_promotion"] is False
    assert spine["production_query_mutation"] is False
    assert spine["production_mutation"] is False
    assert spine["automatic_contact"] is False
    assert spine["automatic_bid"] is False
    assert spine["automatic_reservation"] is False
    assert spine["automatic_purchase"] is False
    assert spine["automatic_payment"] is False


def test_spine_valid_zero_does_not_invent_memory() -> None:
    spine = build_unified_learning_spine(
        unified_intelligence_items={},
        search_success_memory={},
        missed_opportunity_memory={},
        daily_learning={},
    )

    assert spine["status"] == "VALID_ZERO"
    assert spine["evidence_record_count"] == 0
    assert spine["records"] == []
    assert spine["market_counts"] == {}
    assert spine["domain_counts"] == {}
    assert spine["out_of_domain_excluded_count"] == 0
    assert spine["production_mutation"] is False


def test_spine_writer_reads_current_artifacts_and_attaches_summary(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    learning = input_root / "learning"
    output = tmp_path / "checkpoint"
    learning.mkdir(parents=True)
    output.mkdir(parents=True)

    (output / "unified-intelligence-items.json").write_text(
        json.dumps(_river_items()), encoding="utf-8"
    )
    (learning / "search-success-memory.json").write_text(
        json.dumps(_search_success_memory()), encoding="utf-8"
    )
    (learning / "missed-opportunities.json").write_text(
        json.dumps(_miss_memory()), encoding="utf-8"
    )
    (output / "daily-learning-cycle.json").write_text(
        json.dumps(_daily_learning()), encoding="utf-8"
    )
    (output / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"schema_version": "test", "keep": "yes"}), encoding="utf-8"
    )
    (output / "multi-market-phone-summary.txt").write_text(
        "existing summary\n", encoding="utf-8"
    )

    spine = write_unified_learning_spine(output, input_root=input_root)

    assert spine["status"] == "SUCCESS"
    assert (output / "unified-learning-spine.json").exists()

    brief = json.loads(
        (output / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    assert brief["keep"] == "yes"
    assert brief["unified_learning_spine"]["status"] == "SUCCESS"
    assert brief["unified_learning_spine"]["market_counts"] == {
        "FR": 2,
        "IT": 2,
        "NL": 1,
    }

    phone = (output / "multi-market-phone-summary.txt").read_text(encoding="utf-8")
    assert "UNIFIED LEARNING SPINE:" in phone
    assert "FR=2" in phone
    assert "NL=1" in phone
    assert "IT=2" in phone
    assert phone.count("UNIFIED LEARNING SPINE:") == 1


def test_spine_hook_order_is_river_then_daily_learning_then_spine_then_learning_layer() -> None:
    init = INIT.read_text(encoding="utf-8")
    layer_install = init.index("install_learning_layer_review_cli_hook()")
    spine_install = init.index("install_unified_learning_spine_cli_hook()")
    daily_install = init.index("install_daily_auto_miss_learning_cli_hook()")
    river_install = init.index("install_unified_market_intelligence_river_cli_hook()")

    # atexit is LIFO. Registration order must be:
    # Learning Layer -> Spine -> daily learner -> river.
    # Runtime becomes: river -> daily learner -> Spine -> Learning Layer.
    assert layer_install < spine_install < daily_install < river_install

    hook = HOOK.read_text(encoding="utf-8")
    assert 'Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py"' in hook
    assert "write_unified_learning_spine(" in hook
    assert "run_unified_learning_spine_fail_closed(" in hook
