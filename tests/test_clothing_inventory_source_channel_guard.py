from pathlib import Path

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ITEM_LISTING,
    REJECTED_NOISE,
    SOURCE_CHANNEL,
    UNVERIFIED_EVENT,
    DiscoveryQuery,
    PageVerification,
    run_clothing_inventory_discovery,
    verify_public_html,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.source_channel_guard import (
    enforce_source_channel_identity,
)

NOW = "2026-07-28T12:00:00+00:00"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures/clothing_inventory_discovery_verification"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeProvider:
    name = "Fake Search"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query

    def search(self, search_query, *, count=10):
        return self.hits_by_query.get(search_query, [])[:count]


def test_miko_trading_regression_is_source_channel_not_one_opportunity():
    raw = verify_public_html(
        "https://miko-trading.no/",
        fixture("miko-trading-source-channel.html"),
    )
    result = enforce_source_channel_identity(raw)

    assert result.page_role == SOURCE_CHANNEL
    assert result.opportunity_identity is None
    assert result.identity_stable is False
    assert result.event_scenario == UNVERIFIED_EVENT
    assert result.location is None
    assert result.inventory_type is None
    assert result.price_nok is None
    assert result.quantity is None
    assert result.sale_evidence is False
    assert result.clothing_inventory_evidence is False
    assert result.verified is True


def test_miko_trading_regression_cannot_enter_discovery_top5():
    query = DiscoveryQuery(
        "lead-02",
        "STORE_CLOSING",
        "EVENT_LEAD",
        "CLOTHING_INVENTORY",
        "klesbutikk avvikling Norge",
    )
    url = "https://miko-trading.no/"
    provider = FakeProvider({
        query.query: [SearchHit(
            "Kjøp og salg av varepartier - Miko Trading AS",
            url,
            "Klesbutikk, varelager, vareparti og avvikling.",
            "Fake Search",
        )]
    })

    verified = enforce_source_channel_identity(
        verify_public_html(url, fixture("miko-trading-source-channel.html"))
    )
    report = run_clothing_inventory_discovery(
        provider,
        queries=[query],
        discovered_at=NOW,
        verifier=lambda candidate_url: verified,
    )

    assert report["discovery_top5"] == []
    candidate = report["all_discovered_candidates"][0]
    assert candidate["page_role"] == SOURCE_CHANNEL
    assert candidate["opportunity_state"] == REJECTED_NOISE
    assert candidate["top5_eligible"] is False
    assert candidate["identity_stable"] is False
    assert candidate["opportunity_identity"] is None
    assert candidate["scenario"] == UNVERIFIED_EVENT
    assert candidate["location"] is None
    assert candidate["inventory_type"] is None
    assert report["search_run_report"]["top5_eligible_count"] == 0
    assert report["search_run_report"]["opportunity_quality_status"] == "NO_VALID_OPPORTUNITIES"


def test_guard_preserves_a_specific_non_root_item_listing():
    result = PageVerification(
        url="https://estate.example.no/auksjon/7001",
        title="Sport AS konkursbo – hele varelageret selges",
        text="2500 plagg til salgs. Budfrist i morgen.",
        location="Namsos",
        inventory_type="klær",
        price_nok=100000,
        quantity=2500,
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:7001",
        identity_stable=True,
        clothing_inventory_evidence=True,
        sale_evidence=True,
        event_scenario="COMPANY_BANKRUPTCY",
        bounded_context="2500 plagg til salgs. Budfrist i morgen.",
        verified=True,
    )

    assert enforce_source_channel_identity(result) == result


def test_live_structured_discovery_runner_applies_the_guard():
    script = (
        REPOSITORY_ROOT / "scripts/run_clothing_inventory_discovery_search.py"
    ).read_text(encoding="utf-8")

    assert "enforce_source_channel_identity" in script
    assert "def _guarded_public_verifier" in script
    assert "return enforce_source_channel_identity(verify_public_page(url))" in script
    assert "verifier=_guarded_public_verifier if args.verify_pages else None" in script
