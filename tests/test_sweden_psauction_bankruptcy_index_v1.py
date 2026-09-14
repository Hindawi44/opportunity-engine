from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    CONFIRMED_SALE,
    ITEM_LISTING,
    RESELLABLE_INVENTORY,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    PageVerification,
    apply_post_verification_top5_hard_gate,
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
    PSAUCTION_ACTIVE_INDEX_POLICY,
    PSAUCTION_ACTIVE_INDEX_URL,
    BankruptcyIndexFetch,
    PSAuctionBankruptcyIndexAugmentedProvider,
    PSAuctionBankruptcyIndexCollector,
    is_approved_psauction_active_index_url,
)
from opportunity_engine.discovery.sweden_psauction_prefetch import (
    PSAuctionPrefetchedSearchProvider,
)
from scripts import run_sweden_clothing_inventory_discovery_search as sweden_runner


VAXJO_URL = (
    "https://psauction.se/auction/68986/"
    "vaxjo-inunder-ab-i-konkurs"
)
CAROLINE_URL = (
    "https://psauction.se/auction/68961/"
    "by-caroline-s-fashion-ab-i-konkurs"
)
PINKOHOLIC_URL = (
    "https://psauction.se/auction/69086/"
    "butikslager-med-shakers-klader-hygienprodukter-och-tillbehor-1"
)
CHILDRENS_DRESSES_URL = (
    "https://psauction.se/auction/68929/"
    "avyttring-parti-med-exklusiva-barnklanningar-1"
)
DESIGN_FURNITURE_URL = (
    "https://psauction.se/auction/69010/designmobler-fran-konkursbo"
)
PAINT_AND_LEISURE_STORE_URL = (
    "https://psauction.se/auction/69073/"
    "avyttring-fran-maleri-och-fritidsbutik"
)
STORES_FOR_YOU_URL = (
    "https://psauction.se/auction/69208/stores-for-you-ab-i-konkurs"
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
  <a href="/auction/68961/by-caroline-s-fashion-ab-i-konkurs">
    <article>
      <h3>by Caroline S Fashion AB i konkurs</h3>
      <p>Auktionen innehåller varulager med cirka 170 st damkläder,
      klänningar, blusar och accessoarer.</p>
      <span>12 objekt</span><span>3D 4H</span>
    </article>
  </a>
  <a href="/auction/69086/butikslager-med-shakers-klader-hygienprodukter-och-tillbehor-1">
    <article>
      <h3>Butikslager med shakers, kläder, hygienprodukter och tillbehör</h3>
      <p>Auktionen innehåller cirka 4 000 st kläder och 700 accessoarer
      från ett butikslager.</p>
      <span>5 objekt</span><span>43430 Kungsbacka</span><span>10D 4H</span>
    </article>
  </a>
  <a href="/auction/68929/avyttring-parti-med-exklusiva-barnklanningar-1">
    <article>
      <h3>Avyttring parti med exklusiva barnklänningar</h3>
      <p>Parti med cirka 118 st nya barnklänningar för vidareförsäljning.</p>
      <span>1 objekt</span><span>70341 Örebro</span><span>1D 4H</span>
    </article>
  </a>
  <a href="/auction/69010/designmobler-fran-konkursbo">
    <article>
      <h3>Designmöbler från konkursbo</h3>
      <p>Auktionen innehåller bord, stolar och soffor.</p>
      <span>6 objekt</span><span>2D 4H</span>
    </article>
  </a>
  <a href="/auction/69073/avyttring-fran-maleri-och-fritidsbutik">
    <article>
      <h3>Avyttring från måleri- och fritidsbutik</h3>
      <p>Färg, penslar och fritidsprodukter från butik.</p>
      <span>90 objekt</span><span>2D 4H</span>
    </article>
  </a>
  <a href="/auction/69208/stores-for-you-ab-i-konkurs">
    <article>
      <h3>Stores For You AB i konkurs</h3>
      <p>Varulager från tre webbshoppar och e-handelsbutiker.
      Inköpsvärdet uppgår till 4 600 000 SEK.</p>
      <span>162 objekt</span><span>Auktionen slutar 2026-09-18</span>
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
  <a href="/auctions">Alla auktioner</a>
</body></html>
"""


def _fetch_index(_url: str, _timeout: float) -> BankruptcyIndexFetch:
    return BankruptcyIndexFetch(
        final_url=PSAUCTION_ACTIVE_INDEX_URL,
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


def test_active_index_scope_is_exact_and_rejects_filtered_or_foreign_routes() -> None:
    assert is_approved_psauction_active_index_url(
        PSAUCTION_ACTIVE_INDEX_URL
    )
    assert not is_approved_psauction_active_index_url(
        "https://psauction.se/auctions?bankruptcy=1"
    )
    assert not is_approved_psauction_active_index_url(
        "https://example.com/auctions"
    )


def test_active_index_recovers_full_resale_scope_and_rejects_excluded_assets() -> None:
    collection = PSAuctionBankruptcyIndexCollector(
        fetch_index=_fetch_index
    ).collect()

    assert [hit.url for hit in collection.hits] == [
        VAXJO_URL,
        CAROLINE_URL,
        PINKOHOLIC_URL,
        CHILDRENS_DRESSES_URL,
        DESIGN_FURNITURE_URL,
        PAINT_AND_LEISURE_STORE_URL,
        STORES_FOR_YOU_URL,
    ]
    assert collection.hits[0].title == "Växjö Inunder AB i konkurs"
    assert collection.rows_seen == 10
    assert collection.rejected_hits == 3
    assert collection.rejection_reasons == {
        "specific target item lacks bulk inventory evidence": 1,
        "specific PS Auction item is ended or sold": 1,
        "vehicle or heavy machinery scope excluded": 1,
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
            final_url=PSAUCTION_ACTIVE_INDEX_URL,
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

    assert [hit.url for hit in collection.hits] == [
        VAXJO_URL,
        CAROLINE_URL,
        PINKOHOLIC_URL,
        CHILDRENS_DRESSES_URL,
        DESIGN_FURNITURE_URL,
        PAINT_AND_LEISURE_STORE_URL,
        STORES_FOR_YOU_URL,
    ]
    assert render_calls == [(PSAUCTION_ACTIVE_INDEX_URL, 8.0, 45.0)]
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
            final_url=PSAUCTION_ACTIVE_INDEX_URL,
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


def test_full_query_pack_preserves_more_than_twenty_native_active_auctions() -> None:
    queries = build_psauction_clothing_queries(8)
    native_hits = tuple(
        SearchHit(
            title=f"Klädlager {index} i konkurs",
            url=f"https://psauction.se/auction/{70000 + index}/kladlager-{index}",
            description="Auktionen innehåller kläder och skor. 20 objekt.",
            provider=PSAUCTION_ACTIVE_INDEX_POLICY,
        )
        for index in range(25)
    )
    augmented = PSAuctionBankruptcyIndexAugmentedProvider(
        _EmptyProvider(),
        target_queries=tuple(query.query for query in queries),
        current_hits=native_hits,
    )
    prefetched = PSAuctionPrefetchedSearchProvider(
        augmented,
        queries=queries,
        request_budget=len(queries),
    )

    returned = tuple(
        hit
        for query in queries
        for hit in prefetched.search(query.query, count=10)
    )

    assert {hit.url for hit in returned} == {hit.url for hit in native_hits}
    diagnostics = prefetched.diagnostics()
    assert len(diagnostics["current_window_item_ids"]) == 25
    assert diagnostics["current_window_priority_applied"] is True


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


def test_native_only_runner_recovers_full_resale_scope_without_brave(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = PSAuctionBankruptcyIndexCollector(fetch_index=_fetch_index).collect()

    class _FixtureCollector:
        def collect(self):
            return collection

    def _forbidden_brave(*_args, **_kwargs):
        raise AssertionError("Brave must not be constructed in native-only mode")

    output_dir = tmp_path / "se-psauction"
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr(
        sweden_runner,
        "PSAuctionBankruptcyIndexCollector",
        _FixtureCollector,
    )
    monkeypatch.setattr(sweden_runner, "BraveSearchProvider", _forbidden_brave)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sweden_clothing_inventory_discovery_search.py",
            "--source",
            "psauction",
            "--query-budget",
            "2",
            "--output-dir",
            str(output_dir),
            "--paid-brave-disabled-reason",
            "MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED",
        ],
    )

    assert sweden_runner.main() == 0
    report = json.loads((output_dir / "search-run-report.json").read_text())
    candidates = json.loads(
        (output_dir / "all-discovered-candidates.json").read_text()
    )
    identities = {candidate["opportunity_identity"] for candidate in candidates}

    assert {
        "url-id:68986",
        "url-id:68961",
        "url-id:69086",
        "url-id:68929",
        "url-id:69010",
        "url-id:69073",
        "url-id:69208",
    } <= identities
    assert {
        candidate["asset_scope"]
        for candidate in candidates
        if candidate["opportunity_identity"] in identities
    } == {RESELLABLE_INVENTORY}
    assert report["status"] == "PASS"
    assert report["domain"] == RESELLABLE_INVENTORY
    assert report["native_discovery_status"] == "SUCCESS"
    assert report["cost_guard_status"] == "PAID_BRAVE_FALLBACK_SKIPPED"
    assert report["paid_search_used"] is False
    assert report["paid_brave_requests"] == 0
    assert report["source_diagnostics"]["active_index"]["source_mode"] == (
        "NATIVE_ACTIVE_INDEX"
    )
    assert "bankruptcy_index" not in report["source_diagnostics"]


@pytest.mark.parametrize(
    ("url", "title", "text", "inventory_type"),
    (
        (
            STORES_FOR_YOU_URL,
            "Stores For You AB i konkurs",
            (
                "Auktionen slutar 2026-09-18. Varulager från tre webbshoppar "
                "och e-handelsbutiker. 162 objekt."
            ),
            "store_inventory",
        ),
        (
            DESIGN_FURNITURE_URL,
            "Designmöbler från konkursbo",
            "Auktionen slutar 2026-09-18. Bord, stolar och soffor. 6 objekt.",
            "furniture",
        ),
    ),
)
def test_non_clothing_reference_auction_survives_final_verification_gate(
    url: str,
    title: str,
    text: str,
    inventory_type: str,
) -> None:
    query = build_psauction_clothing_queries(1)[0]

    class _OneHitProvider:
        name = "PS Auction regression fixture"

        def search(self, _query: str, *, count: int = 10):
            return (
                SearchHit(
                    title=title,
                    url=url,
                    description=text,
                    provider=self.name,
                ),
            )

    verification = enrich_sweden_page_verification(
        PageVerification(
            url=url,
            title=title,
            text=text,
            listing_status=ACTIVE,
            page_role=ITEM_LISTING,
            opportunity_identity=f"url-id:{url.split('/')[4]}",
            identity_stable=True,
            verified=True,
        )
    )
    assert verification.clothing_inventory_evidence is False
    assert verification.resale_inventory_evidence is True
    assert verification.inventory_type == inventory_type

    result = run_clothing_inventory_discovery(
        SwedenLocalizedSearchProvider(_OneHitProvider()),
        queries=(query,),
        verifier=lambda _url: verification,
    )
    hardened = apply_post_verification_top5_hard_gate(result)
    candidate = hardened["all_discovered_candidates"][0]

    assert candidate["asset_scope"] == RESELLABLE_INVENTORY
    assert candidate["opportunity_state"] == CONFIRMED_SALE
    assert candidate["top5_eligible"] is True
    assert hardened["discovery_top5"][0]["opportunity_identity"] == (
        f"url-id:{url.split('/')[4]}"
    )
