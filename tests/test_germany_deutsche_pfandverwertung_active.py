from __future__ import annotations

from opportunity_engine.discovery.germany_deutsche_pfandverwertung import (
    DEFAULT_DPV_INDEX_URL,
)
from opportunity_engine.discovery.germany_deutsche_pfandverwertung_active import (
    canonicalize_dpv_catalog_page_url,
    run_dpv_active_clothing_watch,
)


CLOTHING_CATALOG = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/"
    "modehaus-nord--search-1-block-201-browse.html"
)
MACHINERY_CATALOG = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/"
    "metallbau--search-1-block-202-browse.html"
)
PAGE_2 = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/browse.php?"
    "block=201&order_by_sort=ends_asc&page=2&search=1&search_closed=n"
)
ITEM_1 = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/00-live-versteigerungen/"
    "24-damenjacken-konvolut--id-9101-item.html"
)
ITEM_2 = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/00-live-versteigerungen/"
    "damenmantel--id-9102-item.html"
)
ITEM_3 = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/00-live-versteigerungen/"
    "40-paar-damenschuhe--id-9103-item.html"
)
MACHINE_ITEM = (
    "https://www.versteigerungen-deutsche-pfandverwertung.de/00-live-versteigerungen/"
    "cnc-fraese--id-9201-item.html"
)


def _index_html() -> str:
    return f"""
    <!doctype html><html><body>
      <h2>Katalogübersicht</h2>
      <section>
        <a href="{CLOTHING_CATALOG}">Kompletter Warenbestand Damenbekleidung</a>
        <p>Versteigerung startet am 10.08.2026 um 12:00 Uhr.</p>
        <a href="{CLOTHING_CATALOG}">Katalog ansehen (Anzahl Artikel: 3)</a>
      </section>
      <section>
        <a href="{MACHINERY_CATALOG}">Inventar Metallbau GmbH</a>
        <p>Beginn 11.08.2026, CNC Maschinen und Werkzeuge.</p>
        <a href="{MACHINERY_CATALOG}">Katalog ansehen (Anzahl Artikel: 1)</a>
      </section>
      <h2>Vergangene Versteigerungen</h2>
      <section>
        <a href="/markenrechte-mode--search-1-search_closed-y-block-199-browse.html">
          Markenrechte Mode GmbH
        </a>
        <p>Versteigerung beendet</p>
        <a href="/markenrechte-mode--search-1-search_closed-y-block-199-browse.html">
          Katalog ansehen (Anzahl Artikel: 1)
        </a>
      </section>
    </body></html>
    """


def _catalog_page_1() -> str:
    return f"""
    <!doctype html><html><body>
      <h1>Kompletter Warenbestand Damenbekleidung</h1>
      <h3>Gesamter Warenbestand Bekleidung und Schuhe</h3>
      <p>Seite 1 von 2</p>
      <p>Anzahl Artikel: 3</p>
      <p>Standort: Modehaus Nord, Hauptstr. 12, Dortmund Versteigerung startet am 10.08.2026</p>
      <a href="{PAGE_2}">Seite 2</a>
      <a href="{ITEM_1}">24 Damenjacken Konvolut</a>
      <a href="{ITEM_2}">Damenmantel Größe 42</a>
    </body></html>
    """


def _catalog_page_2() -> str:
    return f"""
    <!doctype html><html><body>
      <h1>Kompletter Warenbestand Damenbekleidung</h1>
      <p>Seite 2 von 2</p>
      <p>Anzahl Artikel: 3</p>
      <a href="{ITEM_3}">40 Paar Damenschuhe</a>
    </body></html>
    """


def _machinery_catalog() -> str:
    return f"""
    <!doctype html><html><body>
      <h1>Inventar Metallbau GmbH</h1>
      <p>Seite 1 von 1</p>
      <p>Anzahl Artikel: 1</p>
      <a href="{MACHINE_ITEM}">CNC Fräse</a>
    </body></html>
    """


def _bulk_item(title: str, quantity: str, amount: str) -> str:
    return f"""
    <!doctype html><html><body>
      <h1>{title}</h1>
      <p>Losnummer: 7</p>
      <p>Versteigerung startet am 10.08.2026</p>
      <p>{quantity}</p>
      <p>Startpreis {amount} EUR</p>
      <p>3 Gebote</p>
      <p>Standort: Dortmund Dieser Eintrag ist öffentlich.</p>
    </body></html>
    """


class _Response:
    def __init__(self, url: str, body: str, *, content_type: str = "text/html") -> None:
        self.url = url
        self.status_code = 200
        self.encoding = "utf-8"
        self.content = body.encode("utf-8")
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


class _Session:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str, **kwargs):
        self.requested.append(url)
        if url not in self.pages:
            raise AssertionError(f"Unexpected URL: {url}")
        return _Response(url, self.pages[url])


def _session() -> _Session:
    return _Session(
        {
            DEFAULT_DPV_INDEX_URL: _index_html(),
            CLOTHING_CATALOG: _catalog_page_1(),
            PAGE_2: _catalog_page_2(),
            MACHINERY_CATALOG: _machinery_catalog(),
            ITEM_1: _bulk_item(
                "24 Damenjacken Konvolut",
                "24 Stück Damenjacken",
                "500,00",
            ),
            ITEM_3: _bulk_item(
                "40 Paar Damenschuhe",
                "40 Paar Damenschuhe",
                "800,00",
            ),
        }
    )


def test_catalog_page_contract_preserves_block_and_page_identity() -> None:
    direct = canonicalize_dpv_catalog_page_url(CLOTHING_CATALOG)
    page_2 = canonicalize_dpv_catalog_page_url(
        PAGE_2,
        expected_catalog_block_id="201",
    )

    assert direct is not None
    assert direct.catalog_block_id == "201"
    assert direct.page_number == 1
    assert page_2 is not None
    assert page_2.page_number == 2
    assert (
        canonicalize_dpv_catalog_page_url(
            PAGE_2,
            expected_catalog_block_id="999",
        )
        is None
    )
    assert (
        canonicalize_dpv_catalog_page_url(
            PAGE_2 + "&redirect=https://example.com",
            expected_catalog_block_id="201",
        )
        is None
    )


def test_active_watch_completes_catalog_and_verifies_bulk_item_pages() -> None:
    session = _session()
    result = run_dpv_active_clothing_watch(
        session=session,
        catalog_limit=10,
        catalog_page_limit=10,
        item_verification_limit=10,
    )

    report = result.discovery_result["search_run_report"]
    diagnostics = result.diagnostics
    candidates = result.discovery_result["all_discovered_candidates"]

    assert report["status"] == "PASS"
    assert report["source_mode"] == "DPV_ACTIVE_WATCH"
    assert report["top5_count"] == 0
    assert diagnostics["auction_entries_discovered"] == 3
    assert diagnostics["active_catalog_entries_discovered"] == 2
    assert diagnostics["selected_catalog_count"] == 2
    assert diagnostics["successful_catalog_count"] == 2
    assert diagnostics["failed_catalog_count"] == 0
    assert diagnostics["clothing_catalog_count"] == 1
    assert diagnostics["catalog_item_url_count"] == 4
    assert diagnostics["clothing_child_lot_count"] == 3
    assert diagnostics["ordinary_child_lot_count"] == 1
    assert diagnostics["observed_bulk_lot_count"] == 2
    assert diagnostics["verified_bulk_lot_count"] == 2
    assert diagnostics["promoted_bulk_lot_count"] == 0
    assert diagnostics["item_verification_error_count"] == 0

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["opportunity_identity"] == "dpv-auction:201"
    assert candidate["catalog_coverage_complete"] is True
    assert candidate["catalog_pages_fetched"] == 2
    assert candidate["catalog_total_results"] == 3
    assert candidate["catalog_item_url_count"] == 3
    assert candidate["top5_eligible"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["price"] is None
    assert candidate["price_nok"] is None
    assert candidate["bid_price_nok"] is None
    assert candidate["verified_bulk_lot_count"] == 2
    assert candidate["promoted_bulk_lot_count"] == 0

    bulk_lots = [lot for lot in candidate["child_lots"] if lot["bulk_evidence"]]
    assert len(bulk_lots) == 2
    assert all(lot["exact_item_verified"] is True for lot in bulk_lots)
    assert all(lot["promotion_eligible"] is False for lot in bulk_lots)
    assert {lot["source_displayed_amount_eur"] for lot in bulk_lots} == {500.0, 800.0}
    assert ITEM_2 not in session.requested


def test_zero_active_catalogs_are_a_valid_reported_outcome() -> None:
    ended_index = """
    <!doctype html><html><body>
      <h2>Katalogübersicht</h2>
      <h2>Vergangene Versteigerungen</h2>
      <a href="/alte-auktion--search-1-search_closed-y-block-88-browse.html">
        Alte Auktion
      </a>
      <p>Versteigerung beendet</p>
      <a href="/alte-auktion--search-1-search_closed-y-block-88-browse.html">
        Katalog ansehen (Anzahl Artikel: 1)
      </a>
    </body></html>
    """
    result = run_dpv_active_clothing_watch(
        session=_Session({DEFAULT_DPV_INDEX_URL: ended_index})
    )

    report = result.discovery_result["search_run_report"]
    assert report["status"] == "PASS"
    assert report["no_opportunities_found"] is True
    assert report["top5_count"] == 0
    assert result.diagnostics["active_catalog_entries_discovered"] == 0
    assert result.diagnostics["selected_catalog_count"] == 0
    assert result.diagnostics["zero_clothing_results_are_valid"] is True
    assert result.discovery_result["all_discovered_candidates"] == []
    assert result.discovery_result["discovery_top5"] == []
