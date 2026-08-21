from opportunity_engine.ods.web_discovery import (
    WebSearchResult,
    build_discovery_leads,
    canonicalize_url,
)


def test_canonicalize_url_removes_query_fragment_and_trailing_slash():
    assert canonicalize_url("HTTPS://Example.com/path/?utm_source=x#part") == "https://example.com/path"


def test_build_discovery_leads_classifies_deduplicates_and_ranks():
    results = (
        WebSearchResult(
            title="Butikkinnredning selges ved avvikling",
            url="https://example.no/ad/1?utm_source=x",
            snippet="Varelager og kontormøbler i Trondheim",
            city="Trondheim",
            published_at="2026-07-22T06:00:00Z",
            image_count=4,
            price_nok=12000,
        ),
        WebSearchResult(
            title="Duplicate lower quality",
            url="https://example.no/ad/1#duplicate",
            snippet="butikk inventar",
        ),
    )
    leads = build_discovery_leads(results)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.canonical_url == "https://example.no/ad/1"
    assert "shop_equipment" in lead.categories
    assert "inventory" in lead.categories
    assert lead.city == "Trondheim"
    assert lead.price_nok == 12000
    assert lead.priority_score > 50


def test_build_discovery_leads_excludes_irrelevant_vehicle_result():
    results = (
        WebSearchResult(
            title="Bruktbil til salgs",
            url="https://example.no/car/1",
            snippet="konkurs",
        ),
    )
    assert build_discovery_leads(results) == ()


def test_build_discovery_leads_classifies_clothing_shop_fixtures():
    leads = build_discovery_leads((
        WebSearchResult(
            title="Klesoppheng og utstillingsdukker selges",
            url="https://www.finn.no/recommerce/forsale/item/470000001",
            snippet="Butikkinnredning fra klesbutikk i Trondheim.",
            city="Trondheim",
            price_nok=5000,
        ),
    ))

    assert len(leads) == 1
    assert "clothing_shop_fixtures" in leads[0].categories
    assert leads[0].priority_score >= 30


def test_konkurssalg_lagersalg_workwear_result_is_kept_and_ranked():
    leads = build_discovery_leads((
        WebSearchResult(
            title="Konkurssalg - 60 % rabatt",
            url="https://www.facebook.com/example/posts/123",
            snippet=(
                "Lagersalg med stort restlager. Arbeidsklær, vernesko og varer "
                "fra konkursbo selges fra lager."
            ),
            city="Ytre Enebakk",
            published_at="2026-08-21T08:00:00Z",
            image_count=6,
        ),
    ))

    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "Facebook"
    assert "bankruptcy" in lead.categories
    assert "liquidation" in lead.categories
    assert "inventory" in lead.categories
    assert "sale_listing" in lead.categories
    assert lead.priority_score >= 50


def test_missing_values_remain_none():
    lead = build_discovery_leads((
        WebSearchResult(
            title="Konkursbo med butikk inventar",
            url="https://example.no/lead/1",
        ),
    ))[0]
    assert lead.city is None
    assert lead.published_at is None
    assert lead.image_count is None
    assert lead.price_nok is None
