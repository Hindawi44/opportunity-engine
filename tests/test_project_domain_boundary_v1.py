from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.automatic_query_gap_miss_scout import PublicPage
from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from opportunity_engine.discovery.exa_shadow_page_verification import _classify_page
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learned_query_overlay import build_learned_query_overlay, save_learned_query_overlay
from opportunity_engine.learning_promotion_gate import select_promoted_query_overlay
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    OUT_OF_DOMAIN,
    classify_project_domain,
)
from opportunity_engine.promoted_learned_core_discovery import collect_promoted_learned_core_opportunities
from opportunity_engine.promoted_source_production import _candidate_from_detail
from opportunity_engine.source_discovery_shadow import build_source_shadow_candidates


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
TERM = "avviklingssalg"


def test_domain_classifier_accepts_project_scope_and_rejects_unrelated_goods() -> None:
    assert classify_project_domain(category="APPAREL") == CLOTHING_INVENTORY
    assert classify_project_domain(category="CLOTHING") == CLOTHING_INVENTORY
    assert classify_project_domain(category="FOOTWEAR") == CLOTHING_INVENTORY
    assert classify_project_domain(category="FABRIC") == FABRIC_PROCUREMENT
    assert classify_project_domain(category="TEXTILES") == FABRIC_PROCUREMENT

    assert classify_project_domain(category="BUILDING_MATERIALS") == OUT_OF_DOMAIN
    assert classify_project_domain(category="APPLIANCES") == OUT_OF_DOMAIN
    assert classify_project_domain(category="GENERAL_MERCHANDISE") == OUT_OF_DOMAIN

    assert (
        classify_project_domain(
            text="Restparti kläder säljes, 500 st jackor och byxor i lager"
        )
        == CLOTHING_INVENTORY
    )
    assert (
        classify_project_domain(
            text="Tessuti a stock, 1200 metri di lana disponibili in magazzino"
        )
        == FABRIC_PROCUREMENT
    )
    assert (
        classify_project_domain(
            text="Restparti poolkantsten i grå granit, komplett paket för 3x6 meter"
        )
        == OUT_OF_DOMAIN
    )


def test_source_learning_uses_only_in_domain_ground_truth() -> None:
    benchmark = {
        "schema_version": "external-ground-truth-benchmark-1.0",
        "opportunities": [
            {
                "case_id": "worldwise-apparel-1",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/apparel-1/",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "APPAREL"},
            },
            {
                "case_id": "worldwise-flooring",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/flooring/",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "BUILDING_MATERIALS"},
            },
            {
                "case_id": "worldwise-apparel-2",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/apparel-2/",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "APPAREL"},
            },
            {
                "case_id": "stocklear-general",
                "source_name": "Stocklear",
                "source_url": "https://joblot.stocklear.eu/auction/general",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "GENERAL_MERCHANDISE"},
            },
            {
                "case_id": "stocklear-appliance",
                "source_name": "Stocklear",
                "source_url": "https://joblot.stocklear.eu/auction/appliance",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "APPLIANCES"},
            },
        ],
    }
    result = {
        "cases": [
            {"case_id": item["case_id"], "confirmed_miss": True, "root_cause": "SOURCE_GAP"}
            for item in benchmark["opportunities"]
        ]
    }

    report = build_source_shadow_candidates(benchmark, result)
    by_domain = {row["source_domain"]: row for row in report["source_candidates"]}

    assert by_domain["www.worldwiseusa.com"]["status"] == "VALIDATED_SOURCE"
    assert by_domain["www.worldwiseusa.com"]["verified_opportunity_count"] == 2
    assert by_domain["www.worldwiseusa.com"]["categories"] == ["APPAREL"]
    assert "joblot.stocklear.eu" not in by_domain
    assert report["out_of_domain_evidence_count"] == 3
    assert set(report["out_of_domain_case_ids"]) == {
        "worldwise-flooring",
        "stocklear-general",
        "stocklear-appliance",
    }


def _stocklear_detail(title: str, body: str) -> str:
    return f"""
    <html><head><title>{title}</title></head><body>
    Starting price € 2,000. Number of pallets 2. 111 units.
    Quality: New in original packaging. RRP € 14,922.
    {body}
    </body></html>
    """


def test_promoted_stocklear_production_rejects_general_merchandise_and_keeps_clothing() -> None:
    appliance = _candidate_from_detail(
        "https://joblot.stocklear.eu/auction/30001",
        _stocklear_detail("111 Bosch Siemens appliances", "Kitchen appliances and household electronics"),
        "111 Bosch Siemens appliances",
        NOW.isoformat(),
    )
    clothing = _candidate_from_detail(
        "https://joblot.stocklear.eu/auction/30002",
        _stocklear_detail("Mixed fashion clothing stock", "500 jackets, trousers and shirts. Apparel stocklot."),
        "Mixed fashion clothing stock",
        NOW.isoformat(),
    )

    assert appliance is None
    assert clothing is not None
    assert clothing["inventory_focus"] == CLOTHING_INVENTORY
    assert clothing["project_domain"] == CLOTHING_INVENTORY


def _active_overlay(path: Path) -> None:
    evaluation = KeywordEvaluationResult(
        term=TERM,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=("holdout-1", "holdout-2"),
        raw_hit_count=4,
        verified_relevant_count=2,
        precision=0.5,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
        support_case_ids=("support-1",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )
    shadow = build_learned_query_overlay([evaluation])
    active = select_promoted_query_overlay(shadow, {("NO", TERM): "PROMOTED"})
    save_learned_query_overlay(path, active)


def test_promoted_learned_query_cannot_turn_bauhaus_into_project_opportunity(tmp_path: Path) -> None:
    overlay = tmp_path / "active-keyword-overlay.json"
    _active_overlay(overlay)

    def search(query: str):
        return [
            SearchHit(
                title="BAUHAUS Norge avvikler virksomheten",
                url="https://www.bauhaus.no/avvikling",
                description="Avviklingssalg. Hele lagerbeholdningen skal ut.",
                provider="Fake Brave",
            )
        ]

    def fetch_page(url: str) -> PublicPage:
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=(
                "<html><body><h1>BAUHAUS Norge avvikler virksomheten</h1>"
                "<p>Avviklingssalg. Hele lagerbeholdningen med byggematerialer, verktøy, "
                "fliser og trelast skal ut.</p></body></html>"
            ),
        )

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "source",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay),
        },
        search_override=search,
        fetch_page=fetch_page,
        observed_at=NOW,
    )

    assert report["verified_opportunity_count"] == 0
    assert report["out_of_domain_page_count"] == 1


def test_promoted_learned_query_keeps_verified_clothing_liquidation(tmp_path: Path) -> None:
    overlay = tmp_path / "active-keyword-overlay.json"
    _active_overlay(overlay)

    def search(query: str):
        return [
            SearchHit(
                title="Senze of Joy avviklingssalg",
                url="https://example.no/senze-avvikling",
                description="Klesbutikk stenger. Hele varelageret av klær selges ut.",
                provider="Fake Brave",
            )
        ]

    def fetch_page(url: str) -> PublicPage:
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=(
                "<html><body><h1>Senze of Joy stenger butikken</h1>"
                "<p>Vi avvikler virksomheten og har avviklingssalg. Hele varelageret av "
                "klær, jakker og bukser skal ut.</p></body></html>"
            ),
        )

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "source",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay),
        },
        search_override=search,
        fetch_page=fetch_page,
        observed_at=NOW,
    )

    assert report["verified_opportunity_count"] == 1
    assert report["out_of_domain_page_count"] == 0


def test_exa_exact_lot_queries_are_domain_anchored_in_every_market() -> None:
    expected_anchor = {
        "NO": ("klær", "mote"),
        "SE": ("kläder", "mode"),
        "DE": ("kleidung", "mode"),
        "FR": ("vêtements", "mode"),
        "IT": ("abbigliamento", "moda"),
        "NL": ("kleding", "mode"),
    }
    for market, query in MARKET_EXACT_LOT_QUERIES.items():
        folded = query.casefold()
        assert any(anchor in folded for anchor in expected_anchor[market])


def test_exa_exact_lot_verifier_rejects_granite_even_with_price_quantity_and_item_url() -> None:
    classification, evidence = _classify_page(
        title="Restparti poolkantsten i grå granit",
        text="Restparti säljes 9 281 kr. Mängd 30 st raka stenar + 4 st hörn. Nytt skick.",
        url="https://www.blocket.se/recommerce/forsale/item/24362849",
    )

    assert classification == OUT_OF_DOMAIN
    assert evidence["project_domain"] == OUT_OF_DOMAIN
    assert evidence["domain_evidence"] is False
