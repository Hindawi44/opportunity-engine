import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    CONFIRMED_SALE,
    REJECTED_NOISE,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    CLOTHING_INVENTORY_QUERY_MATRIX,
    DiscoveryQuery,
    PageVerification,
    classify_search_hit,
    normalize_public_url,
    run_clothing_inventory_discovery,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.search_provider import SearchHit

NOW = "2026-07-27T12:00:00+00:00"


def query(query_id="test", scenario="COMPANY_BANKRUPTCY", intent="EVENT_LEAD"):
    return DiscoveryQuery(query_id, scenario, intent, "CLOTHING_INVENTORY", "test query")


def test_query_matrix_has_six_sales_six_event_leads_and_four_specialized_queries():
    assert len(CLOTHING_INVENTORY_QUERY_MATRIX) == 16
    assert sum(item.intent == "SALE_INTENT" for item in CLOTHING_INVENTORY_QUERY_MATRIX) == 6
    assert sum(item.intent == "EVENT_LEAD" for item in CLOTHING_INVENTORY_QUERY_MATRIX) == 6
    assert sum(item.intent == "SPECIALIZED" for item in CLOTHING_INVENTORY_QUERY_MATRIX) == 4
    assert all(item.asset_scope == "CLOTHING_INVENTORY" for item in CLOTHING_INVENTORY_QUERY_MATRIX)


def test_axl_like_bankruptcy_is_retained_without_sale_word():
    result = classify_search_hit(
        SearchHit(
            "AXL Sport og Fritid Kolvereid AS konkurs",
            "https://news.example.no/axl?utm_source=test",
            "Klesbutikk og sportsklær. Konkursboet omfatter varelager i Kolvereid.",
            "Fake Search",
        ),
        query(),
    )
    assert result.state == STRONG_LEAD_REQUIRES_VERIFICATION
    assert result.scenario == "COMPANY_BANKRUPTCY"


def test_confirmed_sale_is_classified_confirmed():
    result = classify_search_hit(
        SearchHit(
            "Komplett varelager fra klesbutikk selges",
            "https://auction.example.no/lot/7",
            "Hele lageret med klær og sko selges samlet på auksjon.",
            "Fake Search",
        ),
        query(scenario="AUCTION", intent="SALE_INTENT"),
    )
    assert result.state == CONFIRMED_SALE


@pytest.mark.parametrize(
    ("title", "description", "reason"),
    [
        ("Brukt jakke selges", "Én jakke selges privat.", "ordinary single-item listing"),
        ("Ledig stilling i klesbutikk", "Vi søker medarbeider til butikk.", "job advertisement"),
        ("Hva er et konkursbo?", "Guide og definisjon.", "informational page"),
        ("Ny kolleksjon klær", "Nettbutikk med fri frakt og handle nå.", "ordinary online store"),
    ],
)
def test_noise_is_rejected(title, description, reason):
    result = classify_search_hit(
        SearchHit(title, "https://example.no/page", description, "Fake Search"),
        query(),
    )
    assert result.state == REJECTED_NOISE
    assert reason in result.reason


def test_url_normalization_removes_tracking_and_normalizes_domain_and_path():
    assert normalize_public_url("https://WWW.Example.no//lot/7/?utm_source=x&b=2&a=1#top") == "https://example.no/lot/7?a=1&b=2"
    assert normalize_public_url("http://example.no/lot") == ""


class FakeProvider:
    name = "Fake Search"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query

    def search(self, search_query, *, count=10):
        value = self.hits_by_query.get(search_query, [])
        if isinstance(value, Exception):
            raise value
        return value[:count]


def test_multiple_urls_for_same_company_merge_into_one_candidate_with_all_sources():
    q1 = DiscoveryQuery("q1", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", "first")
    q2 = DiscoveryQuery("q2", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", "second")
    provider = FakeProvider({
        "first": [SearchHit("AXL Sport Kolvereid AS konkurs", "https://news.no/axl", "Klesbutikk med varelager i Kolvereid", "News")],
        "second": [SearchHit("Konkursbo: AXL Sport Kolvereid", "https://estate.no/case/44", "Sportsklær og sko i konkursbo Kolvereid", "Estate")],
    })
    report = run_clothing_inventory_discovery(provider, queries=[q1, q2], discovered_at=NOW)
    candidates = [item for item in report["all_discovered_candidates"] if item["opportunity_state"] != REJECTED_NOISE]
    assert len(candidates) == 1
    assert set(candidates[0]["found_by_queries"]) == {"q1", "q2"}
    assert len(candidates[0]["source_urls"]) == 2
    assert candidates[0]["duplicate_count"] == 1


def test_ended_listing_is_historical_and_not_in_active_top5():
    q = DiscoveryQuery("q", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", "ended")
    provider = FakeProvider({
        "ended": [SearchHit("Varelager klær selges", "https://auction.no/ended", "Auksjonen er avsluttet og lotten er solgt.", "Auction")]
    })
    report = run_clothing_inventory_discovery(provider, queries=[q], discovered_at=NOW)
    assert report["search_run_report"]["ended_or_historical"] == 1
    assert report["discovery_top5"] == []
    assert report["all_discovered_candidates"][0]["listing_status"] == ENDED


def test_missing_price_and_quantity_do_not_delete_the_opportunity():
    q = DiscoveryQuery("q", "STORE_CLOSING", "EVENT_LEAD", "CLOTHING_INVENTORY", "lead")
    provider = FakeProvider({
        "lead": [SearchHit("Klesbutikk stenger i Trondheim", "https://news.no/closure", "Butikken avvikles med varelager klær.", "News")]
    })
    report = run_clothing_inventory_discovery(provider, queries=[q], discovered_at=NOW)
    top = report["discovery_top5"][0]
    assert top["price_nok"] is None
    assert top["quantity"] is None
    assert top["opportunity_state"] == STRONG_LEAD_REQUIRES_VERIFICATION
    assert "price" in top["missing_information"]
    assert "quantity" in top["missing_information"]


def test_public_verification_can_confirm_sale_and_extract_visible_fields():
    q = DiscoveryQuery("q", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", "lead")
    provider = FakeProvider({
        "lead": [SearchHit("Sport AS konkurs", "https://estate.no/sport", "Klesbutikk med varelager.", "Search")]
    })

    def verifier(url):
        return PageVerification(
            url=url,
            title="Sport AS konkursbo — hele varelageret selges",
            text="Sportsklær og sko selges samlet. 2500 stk. Pris NOK 100000. Til salgs i Namsos.",
            location="Namsos",
            inventory_type="sportsklær",
            price_nok=100000,
            quantity=2500,
            listing_status=ACTIVE,
            verified=True,
        )

    report = run_clothing_inventory_discovery(provider, queries=[q], discovered_at=NOW, verifier=verifier)
    top = report["discovery_top5"][0]
    assert top["opportunity_state"] == CONFIRMED_SALE
    assert top["price_nok"] == 100000
    assert top["quantity"] == 2500
    assert top["location"] == "Namsos"


def test_top5_are_unique_traceable_and_ranked_without_financial_fields():
    queries = []
    hits = {}
    for index in range(7):
        query_item = DiscoveryQuery(f"q{index}", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", f"search-{index}")
        queries.append(query_item)
        hits[query_item.query] = [SearchHit(
            f"Bedrift{index} stort klesparti selges",
            f"https://source{index}.no/lot",
            f"Vareparti klær til salgs i Oslo, {100 + index} stk.",
            "Fake Search",
        )]
    report = run_clothing_inventory_discovery(FakeProvider(hits), queries=queries, discovered_at=NOW)
    top5 = report["discovery_top5"]
    assert len(top5) == 5
    assert len({item["source_urls"][0] for item in top5}) == 5
    assert all(item["source_urls"] for item in top5)
    forbidden = {"roi", "expected_profit", "maximum_bid", "BUY_REVIEW", "WATCH", "REJECT"}
    serialized = json.dumps(top5)
    assert all(term not in serialized for term in forbidden)
    assert report["search_run_report"]["financial_ranking_used"] is False


def test_no_results_is_an_honest_success_and_writes_all_four_artifacts(tmp_path: Path):
    q = DiscoveryQuery("q", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", "nothing")
    report = run_clothing_inventory_discovery(FakeProvider({"nothing": []}), queries=[q], discovered_at=NOW)
    assert report["search_run_report"]["no_opportunities_found"] is True
    assert report["search_run_report"]["status"] == "PASS"
    assert report["discovery_top5"] == []
    paths = write_discovery_artifacts(report, tmp_path)
    assert {path.name for path in paths.values()} == {
        "search-run-report.json",
        "all-discovered-candidates.json",
        "discovery-top5.json",
        "operator-summary.txt",
    }
    assert "No active traceable" in paths["operator_summary"].read_text(encoding="utf-8")
