import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    CATEGORY_INDEX,
    CLOTHING_INVENTORY_QUERY_MATRIX,
    CONFIRMED_SALE,
    ENDED,
    ITEM_LISTING,
    ORDINARY_STORE,
    REJECTED_NOISE,
    SOURCE_CHANNEL,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    UNKNOWN,
    UNRESOLVED_SOURCE,
    UNVERIFIED_EVENT,
    DiscoveryQuery,
    PageVerification,
    classify_search_hit,
    normalize_public_url,
    run_clothing_inventory_discovery,
    verify_public_html,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.early_opportunity_gate import apply_early_opportunity_gate
from opportunity_engine.discovery.search_provider import SearchHit

NOW = "2026-07-27T12:00:00+00:00"
FIXTURES = Path(__file__).parent / "fixtures/clothing_inventory_discovery_verification"


def query(query_id="test", scenario="COMPANY_BANKRUPTCY", intent="EVENT_LEAD"):
    return DiscoveryQuery(query_id, scenario, intent, "CLOTHING_INVENTORY", "test query")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeProvider:
    name = "Fake Search"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query

    def search(self, search_query, *, count=10):
        value = self.hits_by_query.get(search_query, [])
        if isinstance(value, Exception):
            raise value
        return value[:count]


def test_query_matrix_remains_six_sales_six_event_leads_and_four_specialized():
    assert len(CLOTHING_INVENTORY_QUERY_MATRIX) == 16
    assert sum(item.intent == "SALE_INTENT" for item in CLOTHING_INVENTORY_QUERY_MATRIX) == 6
    assert sum(item.intent == "EVENT_LEAD" for item in CLOTHING_INVENTORY_QUERY_MATRIX) == 6
    assert sum(item.intent == "SPECIALIZED" for item in CLOTHING_INVENTORY_QUERY_MATRIX) == 4


def test_search_snippet_retains_axl_like_lead_but_never_confirms_sale():
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


def test_sale_snippet_is_only_a_lead_until_bounded_verification():
    result = classify_search_hit(
        SearchHit(
            "Komplett varelager fra klesbutikk selges",
            "https://auction.example.no/lot/7001",
            "Hele lageret med klær og sko selges samlet på auksjon.",
            "Fake Search",
        ),
        query(scenario="AUCTION", intent="SALE_INTENT"),
    )
    assert result.state == STRONG_LEAD_REQUIRES_VERIFICATION
    assert result.page_role_hint == ITEM_LISTING


FINN_CLOTHING_LOT_BENCHMARK = (
    (
        "Restlager fra norsk klesmerke – ca. 1000 plagg selges samlet",
        "https://www.finn.no/recommerce/forsale/item/468124077",
    ),
    (
        "Klesparti fra konkursbo: 511plagg med grafisk print (T-skjorter & hettegensere)",
        "https://www.finn.no/recommerce/forsale/item/465971753",
    ),
    (
        "STORT PARTISALG +/- 250 STK STRØMPEBUKSER",
        "https://www.finn.no/recommerce/forsale/item/451674021",
    ),
    (
        "PARTISALG 50 STK ASSORTERTE ARBEIDSJAKKER",
        "https://www.finn.no/recommerce/forsale/item/450281607",
    ),
    (
        "PARTISALG 100 STK ASSORTERTE ARBEIDSKLÆR",
        "https://www.finn.no/recommerce/forsale/item/450279300",
    ),
    (
        "PARTISALG ASSORTERTE PIQUÉ-SKJORTER (KUN SAMLET PARTI)",
        "https://www.finn.no/recommerce/forsale/item/449770891",
    ),
)


@pytest.mark.parametrize(("title", "url"), FINN_CLOTHING_LOT_BENCHMARK)
def test_real_clothing_lot_titles_are_retained_without_needing_a_search_snippet(title, url):
    result = classify_search_hit(
        SearchHit(title, url, "", "Fake Search"),
        query(scenario="LARGE_LOT_SALE", intent="SALE_INTENT"),
    )
    assert result.state == STRONG_LEAD_REQUIRES_VERIFICATION
    assert result.page_role_hint == ITEM_LISTING
    assert result.identity_stable is True


def test_distinct_stable_listing_ids_keep_all_six_benchmark_candidates_separate():
    q = DiscoveryQuery(
        "benchmark",
        "LARGE_LOT_SALE",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "benchmark",
    )
    provider = FakeProvider({
        "benchmark": [
            SearchHit(title, url, "", "Fake Search")
            for title, url in FINN_CLOTHING_LOT_BENCHMARK
        ]
    })

    report = run_clothing_inventory_discovery(
        provider,
        queries=[q],
        discovered_at=NOW,
    )

    assert report["search_run_report"]["merged_candidates"] == 6
    assert report["search_run_report"]["strong_leads_requiring_verification"] == 6
    assert len(report["discovery_top5"]) == 5
    assert {
        item["opportunity_state"] for item in report["all_discovered_candidates"]
    } == {STRONG_LEAD_REQUIRES_VERIFICATION}


@pytest.mark.parametrize(
    "title",
    [
        "PARTISALG +/- 150 STK HVITVINSGLASS",
        "Restlager fra nettbutikk – beauty, leker og diverse småvarer selges samlet",
    ],
)
def test_bulk_sale_vocabulary_alone_does_not_create_clothing_scope(title):
    result = classify_search_hit(
        SearchHit(title, "https://market.example.no/item/9001", "", "Fake Search"),
        query(scenario="LARGE_LOT_SALE", intent="SALE_INTENT"),
    )
    assert result.state == REJECTED_NOISE


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
    assert normalize_public_url(
        "https://WWW.Example.no//lot/7/?utm_source=x&b=2&a=1#top"
    ) == "https://example.no/lot/7?a=1&b=2"
    assert normalize_public_url("http://example.no/lot") == ""


def test_live_regression_auksjonen_category_is_excluded_without_cross_combining_fields():
    result = verify_public_html(
        "https://ny.auksjonen.no/auksjoner/torget/vareparti-og-konkursbo",
        fixture("auksjonen-category.html"),
    )
    assert result.page_role == CATEGORY_INDEX
    assert result.price_nok is None
    assert result.quantity is None
    assert result.location is None
    assert result.inventory_type is None
    assert result.sale_evidence is False


def test_live_regression_proffsport_is_ordinary_store_and_zero_cart_is_not_price():
    result = verify_public_html(
        "https://proffsport.no/pages/om-oss",
        fixture("proffsport-store.html"),
    )
    assert result.page_role == ORDINARY_STORE
    assert result.price_nok is None
    assert result.event_scenario == UNVERIFIED_EVENT
    assert result.sale_evidence is False


def test_live_regression_altpasalg_is_source_channel_not_opportunity():
    result = verify_public_html(
        "https://altpasalg.no/",
        fixture("altpasalg-source-channel.html"),
    )
    assert result.page_role == SOURCE_CHANNEL
    assert result.price_nok is None
    assert result.quantity is None


def test_live_regression_motorcycle_listing_shell_is_unresolved():
    result = verify_public_html(
        "https://auksjonen.no/auksjon/torget/motorsykkel-klaer/445743",
        fixture("motorcycle-auction-shell.html"),
    )
    assert result.page_role == UNRESOLVED_SOURCE
    assert result.verified is False
    assert result.listing_status == UNKNOWN


def test_unavailable_auksjonen_listing_is_ended_without_invented_commercial_fields():
    result = verify_public_html(
        "https://auksjonen.no/auksjon/torget/motorsykkel-klaer/445743",
        fixture("auksjonen-unavailable-445743.html"),
    )

    assert result.page_role == ITEM_LISTING
    assert result.opportunity_identity == "url-id:445743"
    assert result.identity_stable is True
    assert result.listing_status == ENDED
    assert result.verified is True
    assert result.error == "listing unavailable"
    assert result.price_nok is None
    assert result.bid_price_nok is None
    assert result.quantity is None
    assert result.location is None
    assert result.inventory_type is None


def test_unavailable_auksjonen_listing_is_excluded_from_top5_analysis_and_dossier():
    q = DiscoveryQuery("q", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", "lead")
    provider = FakeProvider({
        "lead": [SearchHit(
            "Helt nytt stort vareparti MC utstyr / motorsykkel klær / Crossutstyr",
            "https://auksjonen.no/auksjon/torget/motorsykkel-klaer/445743",
            "Vareparti klær på auksjon.",
            "Search",
        )]
    })
    verification = verify_public_html(
        "https://auksjonen.no/auksjon/torget/motorsykkel-klaer/445743",
        fixture("auksjonen-unavailable-445743.html"),
    )

    raw = run_clothing_inventory_discovery(
        provider,
        queries=[q],
        discovered_at=NOW,
        verifier=lambda url: verification,
    )
    result = apply_early_opportunity_gate(raw)

    candidate = result["all_discovered_candidates"][0]
    assert candidate["listing_status"] == ENDED
    assert candidate["top5_eligible"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["price_nok"] is None
    assert candidate["bid_price_nok"] is None
    assert candidate["quantity"] is None
    assert candidate["location"] is None
    assert result["discovery_top5"] == []
    assert result["search_run_report"]["analysis_eligible_count"] == 0
    assert "dossier" not in result


def test_live_regression_konkursnett_timeout_cannot_promote_generic_portal():
    q = DiscoveryQuery("q", "COMPANY_BANKRUPTCY", "SALE_INTENT", "CLOTHING_INVENTORY", "portal")
    provider = FakeProvider({
        "portal": [SearchHit(
            "Auksjon - konkursbo, partivare, restlager mm.",
            "https://konkursnett.no/",
            "Konkursbo og auksjon.",
            "Search",
        )]
    })

    def verifier(url):
        return PageVerification(
            url=url,
            page_role=UNRESOLVED_SOURCE,
            verified=False,
            error="timed out",
        )

    report = run_clothing_inventory_discovery(
        provider, queries=[q], discovered_at=NOW, verifier=verifier
    )
    assert report["discovery_top5"] == []
    candidate = report["all_discovered_candidates"][0]
    assert candidate["opportunity_state"] == REJECTED_NOISE
    assert candidate["page_role"] == UNRESOLVED_SOURCE


def test_valid_active_specific_listing_becomes_confirmed_sale_with_bounded_fields():
    result = verify_public_html(
        "https://estate.example.no/auksjon/7001",
        fixture("valid-active-item-listing.html"),
    )
    assert result.page_role == ITEM_LISTING
    assert result.identity_stable is True
    assert result.listing_status == ACTIVE
    assert result.clothing_inventory_evidence is True
    assert result.sale_evidence is True
    assert result.price_nok == 100000
    assert result.quantity == 2500
    assert result.location == "Namsos"

    q = DiscoveryQuery("q", "COMPANY_BANKRUPTCY", "EVENT_LEAD", "CLOTHING_INVENTORY", "lead")
    provider = FakeProvider({
        "lead": [SearchHit(
            "Sport AS konkursbo – hele varelageret selges",
            "https://estate.example.no/auksjon/7001",
            "Sportsklær og sko i konkursbo.",
            "Search",
        )]
    })
    report = run_clothing_inventory_discovery(
        provider,
        queries=[q],
        discovered_at=NOW,
        verifier=lambda url: result,
    )
    top = report["discovery_top5"][0]
    assert top["opportunity_state"] == CONFIRMED_SALE
    assert top["page_role"] == ITEM_LISTING
    assert top["top5_eligible"] is True


def test_unknown_status_specific_listing_remains_lead_not_confirmed():
    q = DiscoveryQuery("q", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", "lead")
    provider = FakeProvider({
        "lead": [SearchHit(
            "Helt nytt stort vareparti MC utstyr og motorsykkel klær",
            "https://auction.example.no/auksjon/445743",
            "Vareparti klær på auksjon.",
            "Search",
        )]
    })

    def verifier(url):
        return PageVerification(
            url=url,
            title="Helt nytt stort vareparti MC utstyr og motorsykkel klær",
            text="Vareparti med motorsykkel klær.",
            page_role=ITEM_LISTING,
            opportunity_identity="url-id:445743",
            identity_stable=True,
            clothing_inventory_evidence=True,
            sale_evidence=False,
            listing_status=UNKNOWN,
            event_scenario="AUCTION",
            verified=True,
        )

    report = run_clothing_inventory_discovery(
        provider, queries=[q], discovered_at=NOW, verifier=verifier
    )
    top = report["discovery_top5"][0]
    assert top["opportunity_state"] == STRONG_LEAD_REQUIRES_VERIFICATION
    assert top["listing_status"] == UNKNOWN


def test_unresolved_auksjonen_listing_keeps_independent_clothing_inventory_lead():
    q = DiscoveryQuery("q", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", "lead")
    provider = FakeProvider({
        "lead": [SearchHit(
            "Helt nytt stort vareparti MC utstyr / motorsykkel klær / Crossutstyr",
            "https://auction.example.no/auksjon/445743",
            "Vareparti klær på auksjon.",
            "Search",
        )]
    })

    report = run_clothing_inventory_discovery(
        provider,
        queries=[q],
        discovered_at=NOW,
        verifier=lambda url: PageVerification(
            url=url,
            error="insufficient public listing content",
        ),
    )

    top = report["discovery_top5"][0]
    assert top["opportunity_state"] == STRONG_LEAD_REQUIRES_VERIFICATION
    assert top["top5_eligible"] is True
    assert top["listing_status"] == UNKNOWN


def test_mixed_non_clothing_inventory_listing_cannot_enter_top5():
    q = DiscoveryQuery(
        "q",
        "WAREHOUSE_SURPLUS",
        "SALE_INTENT",
        "CLOTHING_INVENTORY",
        "mixed inventory",
    )
    title = "Varelager fra nedlagt nettbutikk selges samlet – masse nye varer"
    provider = FakeProvider({
        "mixed inventory": [SearchHit(
            title,
            "https://market.example.no/item/465782612",
            "Komplett restlager med beauty, leker og diverse småvarer selges samlet.",
            "Search",
        )]
    })

    report = run_clothing_inventory_discovery(
        provider,
        queries=[q],
        discovered_at=NOW,
        verifier=lambda url: PageVerification(url=url, error="HTTP Error 403: Forbidden"),
    )

    assert report["discovery_top5"] == []
    candidate = next(
        item for item in report["all_discovered_candidates"] if item["title"] == title
    )
    assert candidate["opportunity_state"] == REJECTED_NOISE
    assert candidate["top5_eligible"] is False
    assert set(candidate["evidence_signals"]) == {"restlager", "varelager", "selges"}


def test_ordinary_store_from_bankruptcy_query_does_not_keep_bankruptcy_scenario():
    q = DiscoveryQuery("q", "COMPANY_BANKRUPTCY", "SPECIALIZED", "CLOTHING_INVENTORY", "store")
    provider = FakeProvider({
        "store": [SearchHit(
            "Proffsport - klær og utstyrsleverandør",
            "https://proffsport.example.no/pages/om-oss",
            "Klær, sko og varelager.",
            "Search",
        )]
    })
    verified = verify_public_html(
        "https://proffsport.example.no/pages/om-oss",
        fixture("proffsport-store.html"),
    )
    report = run_clothing_inventory_discovery(
        provider, queries=[q], discovered_at=NOW, verifier=lambda url: verified
    )
    candidate = report["all_discovered_candidates"][0]
    assert candidate["scenario"] == UNVERIFIED_EVENT
    assert candidate["opportunity_state"] == REJECTED_NOISE
    assert candidate["price_nok"] is None


def test_ended_specific_listing_is_historical_only():
    q = DiscoveryQuery("q", "AUCTION", "SALE_INTENT", "CLOTHING_INVENTORY", "ended")
    provider = FakeProvider({
        "ended": [SearchHit(
            "Varelager klær selges",
            "https://auction.example.no/auksjon/7002",
            "Auksjonen er avsluttet og lotten er solgt.",
            "Auction",
        )]
    })

    def verifier(url):
        return PageVerification(
            url=url,
            title="Varelager klær selges",
            text="Hele varelageret med klær. Auksjonen er avsluttet.",
            page_role=ITEM_LISTING,
            opportunity_identity="url-id:7002",
            identity_stable=True,
            clothing_inventory_evidence=True,
            sale_evidence=True,
            listing_status=ENDED,
            event_scenario="AUCTION",
            verified=True,
        )

    report = run_clothing_inventory_discovery(
        provider, queries=[q], discovered_at=NOW, verifier=verifier
    )
    assert report["discovery_top5"] == []
    assert report["search_run_report"]["ended_or_historical"] == 1


def test_top5_contains_up_to_five_specific_listings_and_never_fills_with_generic_pages():
    queries = []
    hits = {}
    verifications = {}
    for index in range(2):
        item_query = DiscoveryQuery(
            f"q{index}", "LARGE_LOT_SALE", "SALE_INTENT",
            "CLOTHING_INVENTORY", f"search-{index}"
        )
        queries.append(item_query)
        url = f"https://source{index}.no/lot/{7000 + index}"
        hits[item_query.query] = [SearchHit(
            f"Bedrift{index} stort klesparti selges",
            url,
            "Vareparti klær til salgs.",
            "Search",
        )]
        verifications[url] = PageVerification(
            url=url,
            title=f"Bedrift{index} stort klesparti selges",
            text="Vareparti med klær til salgs. Budfrist i morgen.",
            page_role=ITEM_LISTING,
            opportunity_identity=f"url-id:{7000 + index}",
            identity_stable=True,
            clothing_inventory_evidence=True,
            sale_evidence=True,
            listing_status=ACTIVE,
            event_scenario="LARGE_LOT_SALE",
            verified=True,
        )
    generic_query = DiscoveryQuery(
        "generic", "COMPANY_BANKRUPTCY", "SALE_INTENT",
        "CLOTHING_INVENTORY", "generic"
    )
    queries.append(generic_query)
    hits["generic"] = [SearchHit(
        "Torget / Vareparti-og-konkursbo",
        "https://portal.example.no/",
        "Varelager, klær, auksjon og høyeste bud.",
        "Search",
    )]
    verifications["https://portal.example.no/"] = verify_public_html(
        "https://portal.example.no/",
        fixture("auksjonen-category.html"),
    )

    report = run_clothing_inventory_discovery(
        FakeProvider(hits),
        queries=queries,
        discovered_at=NOW,
        verifier=lambda url: verifications[url],
    )
    assert len(report["discovery_top5"]) == 2
    assert all(item["page_role"] == ITEM_LISTING for item in report["discovery_top5"])
    assert report["search_run_report"]["generic_pages_excluded"] >= 1


def test_report_splits_execution_health_from_opportunity_quality_and_keeps_safety_fields():
    q = DiscoveryQuery("q", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", "nothing")
    report = run_clothing_inventory_discovery(
        FakeProvider({"nothing": []}),
        queries=[q],
        discovered_at=NOW,
    )
    summary = report["search_run_report"]
    assert summary["execution_status"] == "PASS"
    assert summary["opportunity_quality_status"] == "NO_VALID_OPPORTUNITIES"
    assert summary["status"] == "PASS"
    assert summary["top5_eligible_count"] == 0
    assert summary["automatic_contact"] is False
    assert summary["automatic_purchase_decision"] is False
    assert summary["financial_ranking_used"] is False


def test_no_results_writes_all_four_artifacts_with_honest_summary(tmp_path: Path):
    q = DiscoveryQuery("q", "LARGE_LOT_SALE", "SALE_INTENT", "CLOTHING_INVENTORY", "nothing")
    report = run_clothing_inventory_discovery(
        FakeProvider({"nothing": []}), queries=[q], discovered_at=NOW
    )
    paths = write_discovery_artifacts(report, tmp_path)
    assert {path.name for path in paths.values()} == {
        "search-run-report.json",
        "all-discovered-candidates.json",
        "discovery-top5.json",
        "operator-summary.txt",
    }
    text = paths["operator_summary"].read_text(encoding="utf-8")
    assert "Opportunity quality: NO_VALID_OPPORTUNITIES" in text
    assert "No valid specific" in text
    serialized = json.dumps(report)
    for forbidden in ("roi", "expected_profit", "maximum_bid", "BUY_REVIEW"):
        assert forbidden not in serialized
