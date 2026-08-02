from __future__ import annotations

from opportunity_engine.discovery.germany_venta import DEFAULT_VENTA_INDEX_URL
from opportunity_engine.discovery.germany_venta_active import (
    canonicalize_venta_catalog_page_url,
    run_venta_active_clothing_watch,
)


CLOTHING_CATALOG = (
    "https://auction.venta24.de/browse/search/1/block/"
    "Insolvenz_Modehaus_Nord_801.html"
)
MACHINERY_CATALOG = (
    "https://auction.venta24.de/browse/search/1/block/"
    "Insolvenz_Metallbau_GmbH_802.html"
)
CLOTHING_PAGE_2 = (
    "https://auction.venta24.de/browse.php?block=801&order_by_sort=ends_asc&"
    "page=2&search=1&search_closed=y"
)


def _index_html() -> str:
    return """
    <!doctype html>
    <html><body>
      <h2>Katalogübersicht</h2>
      <section class="catalog-card">
        <a href="/browse/search/1/block/Insolvenz_Modehaus_Nord_801.html">
          Insolvenz-Versteigerung Modehaus Nord GmbH
        </a>
        <p>Kompletter Warenbestand an Damenbekleidung, Schuhen und Textilien.</p>
        <p>Beginn Do 06.08.2026 um 18:00</p>
        <a href="/browse/search/1/block/Insolvenz_Modehaus_Nord_801.html">
          Katalog ansehen
        </a>
      </section>
      <section class="catalog-card">
        <a href="/browse/search/1/block/Insolvenz_Metallbau_GmbH_802.html">
          Insolvenz-Versteigerung Metallbau GmbH
        </a>
        <p>CNC Maschinen, Werkstatteinrichtung und Metalle.</p>
        <p>Beginn Fr 07.08.2026 um 12:00</p>
        <a href="/browse/search/1/block/Insolvenz_Metallbau_GmbH_802.html">
          Katalog ansehen
        </a>
      </section>
      <h2>Vergangene Auktionen</h2>
      <section class="catalog-card">
        <a href="/browse/search/1/block/Insolvenz_Versteigerung_der_Multiply_Apparel_GmbH_Dortmund_789/search_closed/y.html">
          Insolvenz-Versteigerung der Multiply Apparel GmbH, Dortmund
        </a>
        <p>Porsche 911 Targa 4 GTS, Cabriolet, Hybrid Benzin/Elektro.</p>
        <p>Auktion beendet</p>
        <a href="/browse/search/1/block/Insolvenz_Versteigerung_der_Multiply_Apparel_GmbH_Dortmund_789/search_closed/y.html">
          Katalog ansehen
        </a>
      </section>
    </body></html>
    """


def _clothing_page_1() -> str:
    return """
    <!doctype html>
    <html><body>
      <h1>Auktionskatalog Insolvenz-Versteigerung Modehaus Nord GmbH | 06.08.2026 - 18:00</h1>
      <h3>Informationen zur Versteigerung</h3>
      <p>Auslauf der Versteigerung | Donnerstag 6. August 2026 um 18.00 Uhr</p>
      <p>Standort | Modehaus Nord GmbH Hauptstr. 12 44135 Dortmund</p>
      <h3>Kompletter Warenbestand an Damenbekleidung und Schuhen</h3>
      <p>Erster Artikel endet 06.08.2026 - 18:00</p>
      <p>Auktion Nr. 6001</p>
      <p>Seite 1 von 2</p>
      <p>Objekte gesamt: 3</p>
      <a href="/item/id/6001_1_24_Damenjacken_55001.html">6001.1 =&gt; 24 Damenjacken</a>
      <a href="/item/id/6001_2_1_Damenkleid_55002.html">6001.2 =&gt; 1 Damenkleid</a>
      <a href="/browse.php?block=801&amp;order_by_sort=ends_asc&amp;page=2&amp;search=1&amp;search_closed=y">2</a>
    </body></html>
    """


def _clothing_page_2() -> str:
    return """
    <!doctype html>
    <html><body>
      <h1>Auktionskatalog Insolvenz-Versteigerung Modehaus Nord GmbH | 06.08.2026 - 18:00</h1>
      <p>Auslauf der Versteigerung | Donnerstag 6. August 2026 um 18.00 Uhr</p>
      <p>Auktion Nr. 6001</p>
      <p>Seite 2 von 2</p>
      <p>Objekte gesamt: 3</p>
      <a href="/item/id/6001_3_12_Paar_Damenschuhe_55003.html">6001.3 =&gt; 12 Paar Damenschuhe</a>
    </body></html>
    """


def _machinery_page() -> str:
    return """
    <!doctype html>
    <html><body>
      <h1>Auktionskatalog Insolvenz-Versteigerung Metallbau GmbH | 07.08.2026 - 12:00</h1>
      <h3>Informationen zur Versteigerung</h3>
      <p>Auslauf der Versteigerung | Freitag 7. August 2026 um 12.00 Uhr</p>
      <p>Standort | Metallbau GmbH Werkstr. 1 44135 Dortmund</p>
      <h3>CNC Maschinen, Werkstatteinrichtung und Metalle</h3>
      <p>Erster Artikel endet 07.08.2026 - 12:00</p>
      <p>Auktion Nr. 6002</p>
      <p>Seite 1 von 1</p>
      <p>Objekte gesamt: 1</p>
      <p>in Kategorie: Allgemein (26) Metall (87) Textil (0)</p>
      <a href="/item/id/6002_1_1_CNC_Maschine_56001.html">6002.1 =&gt; 1 CNC Maschine</a>
    </body></html>
    """


class _FakeResponse:
    def __init__(self, url: str, text: str, content_type: str = "text/html") -> None:
        self.url = url
        self.status_code = 200
        self.encoding = "utf-8"
        self.content = text.encode("utf-8")
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"unexpected URL: {url}")
        return _FakeResponse(url, self.pages[url])


def _session() -> _FakeSession:
    return _FakeSession(
        {
            DEFAULT_VENTA_INDEX_URL: _index_html(),
            CLOTHING_CATALOG: _clothing_page_1(),
            CLOTHING_PAGE_2: _clothing_page_2(),
            MACHINERY_CATALOG: _machinery_page(),
        }
    )


def test_query_style_catalog_pages_remain_inside_one_catalog_block() -> None:
    identity = canonicalize_venta_catalog_page_url(
        CLOTHING_PAGE_2,
        expected_catalog_block_id="801",
    )

    assert identity is not None
    assert identity.catalog_block_id == "801"
    assert identity.page_number == 2
    assert canonicalize_venta_catalog_page_url(
        CLOTHING_PAGE_2,
        expected_catalog_block_id="802",
    ) is None
    assert canonicalize_venta_catalog_page_url(
        "https://example.de/browse.php?block=801&page=2&search=1",
        expected_catalog_block_id="801",
    ) is None
    assert canonicalize_venta_catalog_page_url(
        "https://auction.venta24.de/login.html?block=801&page=2",
        expected_catalog_block_id="801",
    ) is None


def test_active_watch_crawls_all_catalogs_and_emits_one_clothing_parent() -> None:
    result = run_venta_active_clothing_watch(
        session=_session(),
        catalog_limit=5,
        catalog_page_limit=10,
    )

    report = result.discovery_result["search_run_report"]
    diagnostics = report["venta_active"]
    candidates = result.discovery_result["all_discovered_candidates"]

    assert report["status"] == "PASS"
    assert report["source_mode"] == "VENTA_ACTIVE_WATCH"
    assert report["no_opportunities_found"] is False
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
    assert diagnostics["promoted_bulk_lot_count"] == 0
    assert diagnostics["single_garment_candidate_count"] == 0
    assert diagnostics["company_name_only_false_positive_count"] == 1

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["opportunity_identity"] == "venta-auction:6001"
    assert candidate["page_role"] == "AUCTION_EVENT"
    assert candidate["listing_status"] == "ACTIVE"
    assert candidate["catalog_coverage_complete"] is True
    assert candidate["catalog_pages_fetched"] == 2
    assert candidate["catalog_total_results"] == 3
    assert candidate["catalog_item_url_count"] == 3
    assert candidate["child_lot_count"] == 3
    assert candidate["ordinary_child_lot_count"] == 1
    assert candidate["observed_bulk_lot_count"] == 2
    assert candidate["promoted_bulk_lot_count"] == 0
    assert candidate["top5_eligible"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["price_nok"] is None
    assert candidate["bid_price_nok"] is None
    assert [lot["quantity"] for lot in candidate["child_lots"]] == [24, 1, 12]
    assert sum(lot["bulk_evidence"] for lot in candidate["child_lots"]) == 2
    assert all(lot["promotion_eligible"] is False for lot in candidate["child_lots"])
    assert result.discovery_result["discovery_top5"] == []


def test_textile_zero_filter_and_company_name_do_not_create_clothing_leads() -> None:
    index = """
    <!doctype html><html><body>
      <h2>Katalogübersicht</h2>
      <a href="/browse/search/1/block/Insolvenz_Metallbau_GmbH_802.html">Insolvenz-Versteigerung Metallbau GmbH</a>
      <p>CNC Maschinen und Metalle.</p><p>Beginn Fr 07.08.2026 um 12:00</p>
      <a href="/browse/search/1/block/Insolvenz_Metallbau_GmbH_802.html">Katalog ansehen</a>
      <h2>Vergangene Auktionen</h2>
      <a href="/browse/search/1/block/Insolvenz_Multiply_Apparel_789/search_closed/y.html">Multiply Apparel GmbH</a>
      <p>Porsche 911.</p><p>Auktion beendet</p>
      <a href="/browse/search/1/block/Insolvenz_Multiply_Apparel_789/search_closed/y.html">Katalog ansehen</a>
    </body></html>
    """
    session = _FakeSession(
        {
            DEFAULT_VENTA_INDEX_URL: index,
            MACHINERY_CATALOG: _machinery_page(),
        }
    )

    result = run_venta_active_clothing_watch(
        session=session,
        catalog_limit=5,
        catalog_page_limit=10,
    )
    report = result.discovery_result["search_run_report"]
    diagnostics = report["venta_active"]

    assert report["status"] == "PASS"
    assert report["no_opportunities_found"] is True
    assert report["opportunity_quality_status"] == "NO_VALID_OPPORTUNITIES"
    assert result.discovery_result["all_discovered_candidates"] == []
    assert diagnostics["clothing_catalog_count"] == 0
    assert diagnostics["company_name_only_false_positive_count"] == 1
    assert diagnostics["zero_clothing_results_are_valid"] is True


def test_missing_pagination_page_fails_closed_but_preserves_diagnostics() -> None:
    session = _FakeSession(
        {
            DEFAULT_VENTA_INDEX_URL: _index_html(),
            CLOTHING_CATALOG: _clothing_page_1(),
            MACHINERY_CATALOG: _machinery_page(),
        }
    )

    result = run_venta_active_clothing_watch(
        session=session,
        catalog_limit=5,
        catalog_page_limit=10,
    )
    report = result.discovery_result["search_run_report"]
    diagnostics = report["venta_active"]

    assert report["status"] == "PARTIAL"
    assert diagnostics["failed_catalog_count"] == 1
    assert diagnostics["successful_catalog_count"] == 1
    assert diagnostics["catalog_errors"][0]["catalog_block_id"] == "801"
    assert result.discovery_result["all_discovered_candidates"] == []
