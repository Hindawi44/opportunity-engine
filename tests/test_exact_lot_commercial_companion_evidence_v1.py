from __future__ import annotations

from opportunity_engine.discovery.exact_lot_child_link_resolution import AggregateHtmlFetchResult
from opportunity_engine.discovery.exact_lot_commercial_companion_evidence import (
    capture_same_domain_commercial_companion_evidence,
    extract_same_domain_commercial_companion_links,
)


def _ok(url: str, html: str) -> AggregateHtmlFetchResult:
    return AggregateHtmlFetchResult(url, url, True, 200, html)


def test_extracts_only_bounded_same_domain_commercial_companions() -> None:
    html = """
    <a href="https://other.example/contact">external</a>
    <a href="/catalog/clothes">catalog</a>
    <a href="/kontakt">Kontakt</a>
    <a href="/frakt">Frakt</a>
    <a href="/kopvillkor">Köpvillkor</a>
    """
    rows = extract_same_domain_commercial_companion_links(
        page_url="https://www.example.se/restpartier",
        html_text=html,
    )
    assert rows == [
        {"url": "https://www.example.se/frakt", "role": "FULFILMENT"},
        {"url": "https://www.example.se/kontakt", "role": "SELLER_IDENTITY"},
    ]


def test_www_cosmetic_variant_is_same_domain_but_subdomain_is_not() -> None:
    html = """
    <a href="https://example.se/leverans">delivery</a>
    <a href="https://shop.example.se/kontakt">shop contact</a>
    """
    rows = extract_same_domain_commercial_companion_links(
        page_url="https://www.example.se/restpartier",
        html_text=html,
    )
    assert rows == [{"url": "https://example.se/leverans", "role": "FULFILMENT"}]


def test_capture_collects_explicit_seller_and_fulfilment_without_promoting_condition() -> None:
    links = [
        {"url": "https://example.se/frakt", "role": "FULFILMENT"},
        {"url": "https://example.se/kontakt", "role": "SELLER_IDENTITY"},
    ]
    pages = {
        "https://example.se/frakt": "<p>Frakt: tillkommer enligt offert</p>",
        "https://example.se/kontakt": (
            "<p>Företag: Example Grossist AB</p><p>Organisationsnummer: 556677-8899</p>"
            "<p>Skick: gäller inte en enskild vara</p>"
        ),
    }

    def fetch(url: str) -> AggregateHtmlFetchResult:
        return _ok(url, pages[url])

    result = capture_same_domain_commercial_companion_evidence(
        links,
        root_url="https://www.example.se/restpartier",
        aggregate_fetcher=fetch,
    )
    assert result["status"] == "SUCCESS"
    assert result["page_fetches_attempted"] == 2
    assert result["page_fetches_succeeded"] == 2
    assert "Frakt: tillkommer enligt offert" in result["fulfilment_candidates"]
    assert "Företag: Example Grossist AB" in result["seller_identity_candidates"]
    assert result["observed_condition_candidates"] == ["Skick: gäller inte en enskild vara"]
    assert result["lot_condition_evidence_allowed"] is False
    assert result["companion_evidence_is_qualification_evidence"] is False
    assert result["paid_search_request_count"] == 0


def test_capture_fails_closed_on_cross_domain_redirect() -> None:
    links = [{"url": "https://example.se/kontakt", "role": "SELLER_IDENTITY"}]

    def fetch(url: str) -> AggregateHtmlFetchResult:
        return AggregateHtmlFetchResult(
            url,
            "https://other.example/contact",
            True,
            200,
            "<p>Företag: Wrong AB</p>",
        )

    result = capture_same_domain_commercial_companion_evidence(
        links,
        root_url="https://example.se/restpartier",
        aggregate_fetcher=fetch,
    )
    assert result["status"] == "VALID_ZERO"
    assert result["seller_identity_candidates"] == []
    assert result["page_fetches_attempted"] == 1
    assert result["page_fetches_succeeded"] == 0


def test_capture_does_not_infer_from_generic_words() -> None:
    links = [{"url": "https://example.no/kontakt", "role": "SELLER_IDENTITY"}]

    def fetch(url: str) -> AggregateHtmlFetchResult:
        return _ok(url, "<p>Vi er en seller og tilbyr shipping i hele landet.</p>")

    result = capture_same_domain_commercial_companion_evidence(
        links,
        root_url="https://example.no/lager",
        aggregate_fetcher=fetch,
    )
    assert result["status"] == "VALID_ZERO"
    assert result["seller_identity_candidates"] == []
    assert result["fulfilment_candidates"] == []


def test_norwegian_and_german_companion_paths_are_recognized() -> None:
    no_rows = extract_same_domain_commercial_companion_links(
        page_url="https://example.no/lager",
        html_text='<a href="/levering">Levering</a><a href="/om-oss">Om oss</a>',
    )
    de_rows = extract_same_domain_commercial_companion_links(
        page_url="https://example.de/lager",
        html_text='<a href="/versand">Versand</a><a href="/impressum">Impressum</a>',
    )
    assert no_rows == [
        {"url": "https://example.no/levering", "role": "FULFILMENT"},
        {"url": "https://example.no/om-oss", "role": "SELLER_IDENTITY"},
    ]
    assert de_rows == [
        {"url": "https://example.de/versand", "role": "FULFILMENT"},
        {"url": "https://example.de/impressum", "role": "SELLER_IDENTITY"},
    ]
