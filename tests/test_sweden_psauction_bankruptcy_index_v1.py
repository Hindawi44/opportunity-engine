from __future__ import annotations

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ITEM_LISTING,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    run_clothing_inventory_discovery,
    verify_public_html,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_clothing_inventory import (
    SwedenLocalizedSearchProvider,
    enrich_sweden_page_verification,
)
from opportunity_engine.discovery.sweden_psauction import (
    build_psauction_clothing_queries,
)
from opportunity_engine.discovery.sweden_psauction_bankruptcy_index import (
    PSAUCTION_BANKRUPTCY_INDEX_URL,
    BankruptcyIndexFetch,
    PSAuctionBankruptcyIndexAugmentedProvider,
    PSAuctionBankruptcyIndexCollector,
    is_approved_psauction_bankruptcy_index_url,
)
from opportunity_engine.discovery.sweden_psauction_prefetch import (
    PSAuctionPrefetchedSearchProvider,
)


VAXJO_URL = (
    "https://psauction.se/auction/68986/"
    "vaxjo-inunder-ab-i-konkurs"
)
INDEX_HTML = """
<html><body>
  <a href="/auction/68986/vaxjo-inunder-ab-i-konkurs">
    <article>
      <h3>Växjö Inunder AB i konkurs</h3>
      <p>Inga reservationspriser</p>
      <p>Auktionen innehåller butiksinredning, möbler och kläder såsom
      skyltdockor, klädställningar, underkläder och badkläder.</p>
      <span>35 objekt</span><span>35246 Växjö</span><span>1D 15H 15M</span>
    </article>
  </a>
  <a href="/auction/68000/avslutad-modebutik">
    <article>
      <h3>Modebutik AB i konkurs</h3>
      <p>Auktionen innehåller kläder och butiksinredning. 24 objekt.</p>
      <span>Avslutad</span>
    </article>
  </a>
  <a href="/auction/68999/verkstadsutrustning-i-konkurs">
    <article>
      <h3>Verkstadsbolag AB i konkurs</h3>
      <p>Auktionen innehåller svarv, svets och verktyg. 40 objekt.</p>
      <span>2D 4H</span>
    </article>
  </a>
  <a href="/auction/69000/enstaka-klader">
    <article>
      <h3>Kläder från modebutik</h3>
      <p>Ett plagg säljs på auktion.</p>
      <span>1 objekt</span><span>2D 4H</span>
    </article>
  </a>
  <a href="/auctions?bankruptcy=1">Alla konkursauktioner</a>
</body></html>
"""


def _fetch_index(_url: str, _timeout: float) -> BankruptcyIndexFetch:
    return BankruptcyIndexFetch(
        final_url=PSAUCTION_BANKRUPTCY_INDEX_URL,
        html=INDEX_HTML,
    )


class _BaseProvider:
    name = "base"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return (
            SearchHit(
                title="Brave fallback",
                url="https://psauction.se/auction/69001/brave-fallback",
                description="Kläder i parti. 20 objekt.",
                provider="Brave",
            ),
        )


class _EmptyProvider:
    name = "empty"

    def search(self, query: str, *, count: int = 10):
        return ()


def test_index_scope_is_exact_and_rejects_nearby_routes() -> None:
    assert is_approved_psauction_bankruptcy_index_url(
        PSAUCTION_BANKRUPTCY_INDEX_URL
    )
    assert not is_approved_psauction_bankruptcy_index_url(
        "https://psauction.se/auctions"
    )
    assert not is_approved_psauction_bankruptcy_index_url(
        "https://example.com/auctions?bankruptcy=1"
    )


def test_bankruptcy_index_keeps_vaxjo_and_rejects_ended_and_nonclothing() -> None:
    collection = PSAuctionBankruptcyIndexCollector(
        fetch_index=_fetch_index
    ).collect()

    assert [hit.url for hit in collection.hits] == [VAXJO_URL]
    assert collection.hits[0].title == "Växjö Inunder AB i konkurs"
    assert collection.rows_seen == 4
    assert collection.rejected_hits == 3
    assert collection.rejection_reasons == {
        "specific clothing item lacks bulk inventory evidence": 1,
        "specific PS Auction item is ended or sold": 1,
        "specific PS Auction listing lacks clothing evidence": 1,
    }
    diagnostics = collection.diagnostics()
    assert diagnostics["index_requests"] == 1
    assert diagnostics["paid_search_used"] is False
    assert diagnostics["automatic_bid"] is False
    assert diagnostics["automatic_purchase_decision"] is False


def test_waf_challenge_uses_one_bounded_rendered_index_fallback() -> None:
    render_calls: list[tuple[str, float, float]] = []

    def challenge_fetch(_url: str, _timeout: float) -> BankruptcyIndexFetch:
        return BankruptcyIndexFetch(
            final_url=PSAUCTION_BANKRUPTCY_INDEX_URL,
            html="",
            status_code=202,
            waf_action="challenge",
        )

    def render_index(
        url: str,
        delay_seconds: float,
        timeout_seconds: float,
    ) -> BankruptcyIndexFetch:
        render_calls.append((url, delay_seconds, timeout_seconds))
        return BankruptcyIndexFetch(
            final_url=url,
            html=INDEX_HTML,
            transport="SYSTEM_CHROMIUM",
        )

    collection = PSAuctionBankruptcyIndexCollector(
        fetch_index=challenge_fetch,
        render_index=render_index,
    ).collect()

    assert [hit.url for hit in collection.hits] == [VAXJO_URL]
    assert render_calls == [(PSAUCTION_BANKRUPTCY_INDEX_URL, 8.0, 45.0)]
    diagnostics = collection.diagnostics()
    assert diagnostics["http_status"] == 202
    assert diagnostics["waf_action"] == "challenge"
    assert diagnostics["rendered_requests"] == 1
    assert diagnostics["rendered_succeeded"] is True
    assert diagnostics["selected_transport"] == "SYSTEM_CHROMIUM"
    assert diagnostics["errors"] == []


def test_waf_challenge_fails_closed_when_rendering_is_unavailable() -> None:
    def challenge_fetch(_url: str, _timeout: float) -> BankruptcyIndexFetch:
        return BankruptcyIndexFetch(
            final_url=PSAUCTION_BANKRUPTCY_INDEX_URL,
            html="",
            status_code=202,
            waf_action="challenge",
        )

    def unavailable_renderer(
        _url: str,
        _delay_seconds: float,
        _timeout_seconds: float,
    ) -> BankruptcyIndexFetch:
        raise RuntimeError("no system Chrome/Chromium executable found")

    collection = PSAuctionBankruptcyIndexCollector(
        fetch_index=challenge_fetch,
        render_index=unavailable_renderer,
    ).collect()

    assert collection.hits == ()
    assert collection.rendered_requests == 1
    assert collection.rendered_succeeded is False
    assert "AWS WAF challenge" in collection.errors[0]["error"]
    assert "rendered index fallback failed" in collection.errors[0]["error"]


def test_native_index_hits_are_prioritized_without_removing_brave_fallback() -> None:
    queries = build_psauction_clothing_queries(2)
    base = _BaseProvider()
    native_hits = tuple(
        SearchHit(
            title=f"Klädbutik {index} AB i konkurs",
            url=f"https://psauction.se/auction/{68980 + index}/kladbutik-{index}",
            description="Auktionen innehåller kläder. 20 objekt.",
            provider="native",
        )
        for index in range(4)
    )
    provider = PSAuctionBankruptcyIndexAugmentedProvider(
        base,
        target_queries=tuple(query.query for query in queries),
        current_hits=native_hits,
    )

    first = tuple(provider.search(queries[0].query, count=3))
    second = tuple(provider.search(queries[1].query, count=3))

    assert [hit.url for hit in first[:2]] == [native_hits[0].url, native_hits[2].url]
    assert [hit.url for hit in second[:2]] == [native_hits[1].url, native_hits[3].url]
    assert first[-1].provider == "Brave"
    assert second[-1].provider == "Brave"
    assert base.calls == [(queries[0].query, 3), (queries[1].query, 3)]


def test_vaxjo_current_auction_page_is_verified_as_active_inventory() -> None:
    html = """
    <html><head>
      <title>Växjö Inunder AB i konkurs</title>
      <meta name="description" content="Kläder och butiksinredning, 35 objekt">
    </head><body><main>
      <h1>Auktionen slutar</h1><p>Torsdag, 2026-09-10</p>
      <h2>Växjö Inunder AB i konkurs</h2>
      <p>Auktionen innehåller butiksinredning, möbler och kläder såsom
      underkläder och badkläder.</p><p>35 objekt</p><p>35246 Växjö</p>
    </main></body></html>
    """

    verification = enrich_sweden_page_verification(
        verify_public_html(VAXJO_URL, html)
    )

    assert verification.verified is True
    assert verification.page_role == ITEM_LISTING
    assert verification.opportunity_identity == "url-id:68986"
    assert verification.listing_status == ACTIVE
    assert verification.clothing_inventory_evidence is True
    assert verification.sale_evidence is True


def test_vaxjo_native_hit_reaches_discovery_as_a_traceable_strong_lead() -> None:
    collection = PSAuctionBankruptcyIndexCollector(
        fetch_index=_fetch_index
    ).collect()
    queries = build_psauction_clothing_queries(2)
    augmented = PSAuctionBankruptcyIndexAugmentedProvider(
        _EmptyProvider(),
        target_queries=tuple(query.query for query in queries),
        current_hits=collection.hits,
    )
    prefetched = PSAuctionPrefetchedSearchProvider(
        augmented,
        queries=queries,
        request_budget=2,
    )

    result = run_clothing_inventory_discovery(
        SwedenLocalizedSearchProvider(prefetched),
        queries=queries,
        results_per_query=10,
    )

    candidates = result["all_discovered_candidates"]
    vaxjo = next(
        item
        for item in candidates
        if item["opportunity_identity"] == "url-id:68986"
    )
    assert vaxjo["opportunity_state"] == STRONG_LEAD_REQUIRES_VERIFICATION
    assert vaxjo["source_urls"] == [VAXJO_URL]
