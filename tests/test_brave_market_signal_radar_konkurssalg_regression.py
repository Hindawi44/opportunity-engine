from datetime import datetime, timezone

from opportunity_engine.discovery.brave_market_signal_radar import (
    MARKET_QUERIES,
    SOURCE_FOCUS_QUERIES,
    collect_manifest_brave_market_signals,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.market_intelligence import MarketSignalType


def test_norway_radar_keeps_konkurssalg_lagersalg_workwear_signal() -> None:
    hit = SearchHit(
        title="Konkurssalg - 60 % rabatt på arbeidsklær",
        url="https://www.facebook.com/example/posts/123",
        description=(
            "Lagersalg fra konkursbo med stort restlager av arbeidsklær, "
            "vernesko og varer."
        ),
        provider="Brave Search",
    )

    signal = market_signal_from_brave_hit(
        hit,
        market_code="NO",
        query=MARKET_QUERIES["NO"][0],
        rank=1,
        observed_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
    )

    assert signal is not None
    assert signal.signal_type == MarketSignalType.INSOLVENCY_OR_LIQUIDATION
    assert signal.metadata["not_an_opportunity"] is True
    assert "konkurssalg" in signal.metadata["event_terms"]
    assert "arbeidsklær" in signal.metadata["clothing_terms"]


def test_norway_radar_queries_explicitly_cover_konkurssalg_and_lagersalg() -> None:
    combined = " ".join(item.query for item in MARKET_QUERIES["NO"])

    assert "konkurssalg" in combined
    assert "lagersalg" in combined
    assert "vernesko" in combined


def test_norway_source_focus_recovers_the_naerbo_konksalg_miss() -> None:
    query = SOURCE_FOCUS_QUERIES["NO"][0]
    hit = SearchHit(
        title="ALT MÅ BORT. ALLE VARER -80 %! Få dager igjen. Bilder tatt 07/09",
        url=(
            "https://www.facebook.com/konksalg/posts/"
            "alt-m%C3%A5-bort-alle-varer-80-f%C3%A5-dager-igjen/1609123034335109/"
            "?utm_source=test&fbclid=tracking"
        ),
        description=(
            "Nærbø Maskin AS: rundt 150 paller med arbeidstøy og vernesko "
            "i Osloveien 708, Ytre Enebakk."
        ),
        provider="Brave Search",
    )

    signal = market_signal_from_brave_hit(
        hit,
        market_code="NO",
        query=query,
        rank=1,
        observed_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
    )

    assert signal is not None
    assert signal.signal_type == MarketSignalType.WAREHOUSE_SURPLUS
    assert str(signal.source_url).endswith("/1609123034335109")
    assert signal.metadata["source_channel"] == "KONKSALG_FACEBOOK"
    assert signal.metadata["source_scope"] == "NO_KONKSALG_PUBLIC_POST"
    assert signal.metadata["event_terms"] == ["alle varer", "alt må bort"]
    assert signal.metadata["signal_only"] is True
    assert signal.metadata["not_an_opportunity"] is True
    assert signal.evidence[0].verified is False


def test_norway_source_focus_rejects_non_konksalg_facebook_pages() -> None:
    query = SOURCE_FOCUS_QUERIES["NO"][0]
    common = {
        "title": "ALT MÅ BORT. ALLE VARER -80 %!",
        "description": "Arbeidstøy og vernesko selges.",
        "provider": "Brave Search",
    }

    for url in (
        "https://www.facebook.com/other-shop/posts/123456789",
        "https://www.facebook.com/konksalg",
    ):
        signal = market_signal_from_brave_hit(
            SearchHit(url=url, **common),
            market_code="NO",
            query=query,
            rank=1,
            observed_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
        )
        assert signal is None


def test_norway_marketplace_source_focus_accepts_only_bounded_public_sale_pages() -> None:
    query = SOURCE_FOCUS_QUERIES["NO"][1]
    observed_at = datetime(2026, 9, 8, tzinfo=timezone.utc)
    valid_urls = {
        "https://www.finn.no/recommerce/forsale/item/474822486?utm_source=test": (
            "FINN_PUBLIC_ITEM"
        ),
        "https://www.finn.no/475586663": "FINN_PUBLIC_ITEM",
        "https://norskavvikling.no/produkt/vareparti-med-arbeidstoy/": (
            "NORSK_AVVIKLING_PUBLIC_SALE"
        ),
        "https://resalg.com/listing/vinter-klaer-barn/": "RESALG_PUBLIC_LISTING",
    }

    for url, expected_channel in valid_urls.items():
        signal = market_signal_from_brave_hit(
            SearchHit(
                title="Konkurssalg av varelager",
                url=url,
                description="Vareparti med arbeidstøy og vernesko.",
                provider="Brave Search",
            ),
            market_code="NO",
            query=query,
            rank=1,
            observed_at=observed_at,
        )
        assert signal is not None
        assert signal.metadata["source_channel"] == expected_channel
        assert signal.metadata["not_an_opportunity"] is True

    for url in (
        "https://www.finn.no/recommerce/forsale/search?q=arbeidstoy",
        "https://norskavvikling.no/nyheter/konkurssalg",
    ):
        signal = market_signal_from_brave_hit(
            SearchHit(
                title="Konkurssalg av varelager",
                url=url,
                description="Vareparti med arbeidstøy og vernesko.",
                provider="Brave Search",
            ),
            market_code="NO",
            query=query,
            rank=1,
            observed_at=observed_at,
        )
        assert signal is None


def test_norway_source_focus_query_pack_is_explicit_and_bounded() -> None:
    queries = SOURCE_FOCUS_QUERIES["NO"]
    combined = " ".join(item.query for item in queries)

    assert len(queries) == 2
    assert "site:facebook.com/konksalg/posts" in combined
    assert "site:finn.no/recommerce/forsale/item" in combined
    assert "site:resalg.com/listing" in combined
    assert "site:norskavvikling.no/aktive-salg" in combined
    assert "arbeidstøy" in combined
    assert all(item.source_scope for item in queries)
    assert SOURCE_FOCUS_QUERIES["SE"] == ()
    assert SOURCE_FOCUS_QUERIES["DE"] == ()


def test_resalg_finn_mirror_lot_is_recovered_as_a_clothing_lot_signal() -> None:
    query = SOURCE_FOCUS_QUERIES["NO"][1]
    signal = market_signal_from_brave_hit(
        SearchHit(
            title=(
                "Vareparti med vinterklær, hjelmer og leker til barn "
                "NETTAUKSJON"
            ),
            url="https://www.finn.no/recommerce/forsale/item/475586663",
            description=(
                "Vinterklær Barn. Ski-Doo, Lynx, Squadron og Scott. "
                "Auksjon hos ReSalg."
            ),
            provider="Brave Search",
        ),
        market_code="NO",
        query=query,
        rank=1,
        observed_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )

    assert signal is not None
    assert signal.signal_type == MarketSignalType.WAREHOUSE_SURPLUS
    assert signal.metadata["source_channel"] == "FINN_PUBLIC_ITEM"
    assert signal.metadata["source_scope"] == "NO_CLEARANCE_MARKETPLACE_PUBLIC_SALE"
    assert signal.metadata["not_an_opportunity"] is True


def test_resalg_exact_lot_is_recovered_as_a_bounded_public_signal() -> None:
    query = SOURCE_FOCUS_QUERIES["NO"][1]
    signal = market_signal_from_brave_hit(
        SearchHit(
            title="Vinterklær Barn – nettauksjon",
            url="https://resalg.com/listing/vinter-klaer-barn/",
            description="Vareparti med vinterklær, hjelmer og leker til barn.",
            provider="Brave Search",
        ),
        market_code="NO",
        query=query,
        rank=1,
        observed_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )

    assert signal is not None
    assert signal.signal_type == MarketSignalType.WAREHOUSE_SURPLUS
    assert signal.metadata["source_channel"] == "RESALG_PUBLIC_LISTING"
    assert str(signal.source_url).endswith("/listing/vinter-klaer-barn")


def test_rejected_generic_hit_can_be_recovered_by_later_source_focus_query(
    tmp_path,
) -> None:
    """A generic rejection must not poison URL deduplication for the strict lane."""
    miss = SearchHit(
        title="ALT MÅ BORT. ALLE VARER -80 %! Få dager igjen.",
        url="https://www.facebook.com/konksalg/posts/1609123034335109",
        description="Nærbø Maskin AS har 150 paller med arbeidstøy og vernesko.",
        provider="Brave Search",
    )

    class Provider:
        name = "Fake Brave"

        def __init__(self, market: str) -> None:
            self.market = market

        def search(self, query: str, *, count: int = 10):
            if self.market == "NO" and query in {
                MARKET_QUERIES["NO"][0].query,
                SOURCE_FOCUS_QUERIES["NO"][0].query,
            }:
                return [miss]
            return []

    manifest = {
        "sources": [
            {"market_code": "NO", "artifact_dir": "no"},
            {"market_code": "SE", "artifact_dir": "se"},
            {"market_code": "DE", "artifact_dir": "de"},
        ]
    }
    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        observed_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: Provider(market),
    )

    norway = next(
        source for source in report["sources"] if source["source_country"] == "NO"
    )
    assert report["requests_made"] == 8
    assert norway["accepted_signal_count"] == 1
    assert norway["rejected_result_count"] == 1
    assert norway["signals"][0]["metadata"]["source_channel"] == (
        "KONKSALG_FACEBOOK"
    )
