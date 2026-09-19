"""Explicit operator source exclusions never delete source history or imply fraud."""

from opportunity_engine.discovery.brave_search import _parse_hits as brave_hits
from opportunity_engine.discovery.exa_search import _parse_hits as exa_hits
from opportunity_engine.human_listing_review_queue import build_queue, classify_url
from opportunity_engine.operator_source_exclusion import excluded_domain, is_operator_excluded_url


def test_domain_and_subdomains_not_similar_unrelated_hosts():
    assert excluded_domain("https://friptadium.com/products/hauts-femme-premium-au-kilo") == "friptadium.com"
    assert excluded_domain("https://WWW.FRIPTADIUM.COM/products/another") == "friptadium.com"
    assert is_operator_excluded_url("https://shop.friptadium.com/products/test")
    assert is_operator_excluded_url("https://vinqa-grossiste.com/products/box")
    assert not is_operator_excluded_url("https://friptadium.com.evil.example/products/test")
    assert not is_operator_excluded_url("https://notfriptadium.com/products/test")
    assert not is_operator_excluded_url("https://cubecompany.nl/product/test")


def test_exa_and_brave_exclude_operator_domain_without_hiding_other_sources():
    excluded = "https://friptadium.com/products/hauts-femme-premium-au-kilo"
    allowed = "https://cubecompany.nl/product/clothes"
    exa = exa_hits({"results": [{"title": "Excluded", "url": excluded},
                                {"title": "Other", "url": allowed}]})
    brave = brave_hits({"web": {"results": [{"title": "Excluded", "url": excluded},
                                                {"title": "Other", "url": allowed}]}})
    assert [hit.url for hit in exa] == [allowed]
    assert [hit.url for hit in brave] == [allowed]


def test_review_excludes_entire_domain_but_preserves_historical_report():
    excluded = "https://friptadium.com/products/hauts-femme-premium-au-kilo"
    other = "https://salzmann-restwaren.de/product/clothing-lot"
    assert classify_url(excluded) == "EXCLUDED"
    assert classify_url("https://blog.friptadium.com/products/other") == "EXCLUDED"
    report = {"generated_at": "2026-09-18T09:22:00Z", "deduplicated_opportunities": [
        {"opportunity_identity": excluded, "canonical_url": excluded,
         "source_urls": [excluded], "title": "historical", "market_code": "FR", "listing_status": "ACTIVE"},
        {"opportunity_identity": other, "canonical_url": other,
         "source_urls": [other], "title": "independent", "market_code": "DE", "listing_status": "ACTIVE"},
    ]}
    queue = build_queue(report)
    assert len(report["deduplicated_opportunities"]) == 2
    assert [row["source_url"] for row in queue["review_queue"]] == [other]
    assert queue["counts"]["excluded_source"] == 1
    assert queue["held_separately"][0]["reason"] == "EXCLUDED_SOURCE"
    assert queue["automatic_purchase"] is False


def test_rejected_source_cannot_reenter_via_alias_or_historical_final_url():
    excluded = "https://friptadium.com/products/hauts-femme-premium-au-kilo"
    alias = "https://salzmann-restwaren.de/product/other"
    report = {"deduplicated_opportunities": [
        {"opportunity_identity": "old", "canonical_url": alias,
         "source_urls": [alias, excluded], "market_code": "FR", "listing_status": "ACTIVE"},
        {"opportunity_identity": "redirect", "canonical_url": alias,
         "source_urls": [alias], "market_code": "FR", "listing_status": "ACTIVE",
         "pending_investigation": {"final_url": excluded}},
    ]}
    queue = build_queue(report)
    assert not queue["review_queue"]
    assert queue["counts"]["excluded_source"] == 2


def test_lux_operator_exclusion_covers_whole_host_and_subdomains_not_lookalikes():
    item = "https://luxvintagewholesale.com/it/products/mix-abbigliamento-50-60-70"
    assert excluded_domain(item) == "luxvintagewholesale.com"
    assert excluded_domain("https://WWW.LUXVINTAGEWHOLESALE.COM/products/test") == "luxvintagewholesale.com"
    assert is_operator_excluded_url("https://shop.luxvintagewholesale.com/collections/vintage")
    assert classify_url(item) == "EXCLUDED"
    assert classify_url("https://sub.luxvintagewholesale.com/products/lot") == "EXCLUDED"
    assert not is_operator_excluded_url("https://notluxvintagewholesale.com/products/lot")
    assert not is_operator_excluded_url("https://luxvintagewholesale.com.example.org/products/lot")
    assert not is_operator_excluded_url("https://cubecompany.nl/product/lot")


def test_lux_excluded_from_both_provider_discovery_and_review_while_history_remains():
    excluded = "https://luxvintagewholesale.com/it/products/mix-abbigliamento-50-60-70"
    allowed = "https://salzmann-restwaren.de/product/other"
    raw_hits = [{"title": "Past Lux lot", "url": excluded}, {"title": "Allowed lot", "url": allowed}]
    assert [hit.url for hit in exa_hits({"results": raw_hits})] == [allowed]
    assert [hit.url for hit in brave_hits({"web": {"results": raw_hits}})] == [allowed]
    historical_report = {"generated_at": "2026-09-19T06:00:00Z", "deduplicated_opportunities": [
        {"opportunity_identity": excluded, "canonical_url": excluded, "source_urls": [excluded],
         "title": "historical Lux listing", "market_code": "IT", "listing_status": "ACTIVE"},
        {"opportunity_identity": allowed, "canonical_url": allowed, "source_urls": [allowed],
         "title": "independent", "market_code": "DE", "listing_status": "ACTIVE"},
    ]}
    queue = build_queue(historical_report)
    assert len(historical_report["deduplicated_opportunities"]) == 2
    assert [row["source_url"] for row in queue["review_queue"]] == [allowed]
    assert queue["counts"]["excluded_source"] == 1
    assert queue["held_separately"][0]["reason"] == "EXCLUDED_SOURCE"
    assert queue["automatic_purchase"] is False
