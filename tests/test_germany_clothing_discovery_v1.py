from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.clothing_inventory_search import (
    ENDED,
    ITEM_LISTING,
    PageVerification,
    REJECTED_NOISE,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    classify_search_hit,
)
from opportunity_engine.discovery import germany_clothing_inventory as germany_discovery
from opportunity_engine.discovery.germany_clothing_inventory import (
    GERMANY_CLOTHING_QUERY_MATRIX,
    GermanyLocalizedSearchProvider,
    build_germany_clothing_inventory_queries,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.unified_opportunity_report import (
    build_unified_opportunity_report,
)
from opportunity_engine.markets.germany import (
    build_germany_market_profile_snapshot,
    load_germany_market_profile,
)
from scripts.run_market_clothing_inventory_discovery import select_market_runner


ROOT = Path(__file__).resolve().parents[1]


class StaticProvider:
    name = "static"

    def __init__(self, hits):
        self.hits = hits

    def search(self, query: str, *, count: int = 10):
        return self.hits[:count]


def _candidate():
    return {
        "title": "Kompletter Warenbestand mit Bekleidung zu verkaufen",
        "scenario": "INVENTORY_LIQUIDATION",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": "German commercial signal",
        "page_role": "ITEM_LISTING",
        "opportunity_identity": "url-id:de-12345",
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "discovery_score": 60,
        "discovery_band": "REVIEW",
        "location": None,
        "company_name": None,
        "inventory_type": "Bekleidung",
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "published_at": None,
        "listing_status": "UNKNOWN",
        "source_urls": ["https://example.de/auktion/de-12345"],
        "source_providers": ["Brave Search"],
        "evidence_signals": ["Bekleidung", "Warenbestand", "Versteigerung"],
        "missing_information": ["price", "quantity"],
        "textile_category": "CLOTHING_INVENTORY",
        "verification": [],
    }


def test_germany_profile_loads_cross_border_identity_and_planned_sources():
    profile = load_germany_market_profile(ROOT)
    snapshot = build_germany_market_profile_snapshot(ROOT)

    assert profile.market_code == "DE"
    assert profile.currency_code == "EUR"
    assert profile.language_codes == ("de",)
    assert profile.fallback_language_codes == ("en",)
    assert profile.transaction_scope == "CROSS_BORDER"
    assert profile.tax_policy["calculation_enabled"] is False
    assert profile.customs_policy["calculation_enabled"] is False
    assert profile.logistics_policy["calculation_enabled"] is False
    assert profile.customs_policy["cross_border_import_supported"] is True

    sources = snapshot["source_registry_snapshot"]["sources"]
    assert {row["source"] for row in sources} == {
        "Riegermann",
        "VENTA Industrieversteigerungen",
        "Deutsche Pfandverwertung",
    }
    assert all(row["runtime_status"] == "PLANNED" for row in sources)
    assert all(row["qualification_mode"] == "SIGNAL_ONLY" for row in sources)


def test_germany_query_pack_is_bounded_unique_and_clothing_only():
    queries = build_germany_clothing_inventory_queries()

    assert len(queries) == 16
    assert len({query.query_id for query in queries}) == 16
    assert all(query.asset_scope == "CLOTHING_INVENTORY" for query in queries)
    assert all("Deutschland" in query.query for query in queries)
    assert {query.scenario for query in queries} >= {
        "INVENTORY_LIQUIDATION",
        "LARGE_LOT_SALE",
        "AUCTION",
        "WAREHOUSE_SURPLUS",
        "COMPANY_BANKRUPTCY",
        "STORE_CLOSING",
        "BRANCH_CLOSURE",
    }

    with pytest.raises(ValueError, match="query_budget"):
        build_germany_clothing_inventory_queries(0)
    with pytest.raises(ValueError, match="query_budget"):
        build_germany_clothing_inventory_queries(17)


def test_german_commercial_snippet_reuses_existing_classifier():
    query = GERMANY_CLOTHING_QUERY_MATRIX[0]
    provider = GermanyLocalizedSearchProvider(
        StaticProvider(
            [
                SearchHit(
                    title="Bekleidungsgeschäft verkauft kompletten Warenbestand",
                    url="https://example.de/auktion/de-12345",
                    description=(
                        "Bekleidung und Schuhe als Lagerposten durch Versteigerung "
                        "zu verkaufen."
                    ),
                    provider="Static",
                )
            ]
        )
    )

    localized_hit = provider.search(query.query)[0]
    observation = classify_search_hit(localized_hit, query)

    assert "klesbutikk" in localized_hit.description
    assert "varelager" in localized_hit.description
    assert "klær" in localized_hit.description
    assert "auksjon" in localized_hit.description
    assert observation.state == STRONG_LEAD_REQUIRES_VERIFICATION
    assert observation.identity_stable is True


def test_german_job_noise_is_rejected():
    query = GERMANY_CLOTHING_QUERY_MATRIX[6]
    provider = GermanyLocalizedSearchProvider(
        StaticProvider(
            [
                SearchHit(
                    title="Stellenangebot im Bekleidungsgeschäft",
                    url="https://example.de/jobs/de-12345",
                    description="Karriere im Onlineshop für Bekleidung.",
                    provider="Static",
                )
            ]
        )
    )

    observation = classify_search_hit(provider.search(query.query)[0], query)

    assert observation.state == REJECTED_NOISE
    assert observation.reason == "job advertisement"


def test_germany_verifier_enriches_only_verified_specific_item(monkeypatch):
    base = PageVerification(
        url="https://example.de/auktion/de-12345",
        title="Insolvenzversteigerung Bekleidung Warenbestand",
        text="Die Versteigerung ist beendet. Kompletter Warenbestand mit Bekleidung.",
        bounded_context=(
            "Insolvenzversteigerung beendet. Kompletter Warenbestand mit "
            "Bekleidung verkauft."
        ),
        listing_status="UNKNOWN",
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:de-12345",
        identity_stable=True,
        verified=True,
    )
    monkeypatch.setattr(germany_discovery, "verify_public_page", lambda url: base)

    verified = germany_discovery.verify_germany_public_page(base.url)

    assert verified.listing_status == ENDED
    assert verified.clothing_inventory_evidence is True
    assert verified.sale_evidence is True
    assert verified.event_scenario == "COMPANY_BANKRUPTCY"


def test_brave_country_target_is_explicit_for_germany():
    captured = {}

    def transport(request, timeout):
        captured["url"] = request.full_url
        return b'{"web":{"results":[]}}'

    provider = BraveSearchProvider(
        "secret",
        country="de",
        transport=transport,
        max_retries=0,
    )
    assert provider.search("Bekleidung Versteigerung") == []

    params = parse_qs(urlparse(captured["url"]).query)
    assert params["country"] == ["DE"]


def test_germany_unified_report_carries_de_and_eur_without_conversion():
    report = build_unified_opportunity_report(
        {"all_discovered_candidates": [_candidate()]},
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        market_code="DE",
        currency="EUR",
        domain="CLOTHING_INVENTORY",
    )

    assert report["market_code"] == "DE"
    assert report["currency"] == "EUR"
    assert report["record_count"] == 1
    assert report["records"][0]["market_code"] == "DE"
    assert report["records"][0]["currency"] == "EUR"
    assert report["records"][0]["price"] is None


def test_zero_result_germany_report_is_valid():
    report = build_unified_opportunity_report(
        {"all_discovered_candidates": []},
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        market_code="DE",
        currency="EUR",
        domain="CLOTHING_INVENTORY",
    )

    assert report["record_count"] == 0
    assert report["conversion_error_count"] == 0
    assert report["records"] == []


def test_market_selector_adds_germany_without_changing_existing_markets():
    assert select_market_runner("NO").__module__ == (
        "scripts.run_clothing_inventory_discovery_search"
    )
    assert select_market_runner("SE").__module__ == (
        "scripts.run_sweden_clothing_inventory_discovery_search"
    )
    assert select_market_runner("de").__module__ == (
        "scripts.run_germany_clothing_inventory_discovery_search"
    )
    with pytest.raises(ValueError, match="unsupported market"):
        select_market_runner("DK")
