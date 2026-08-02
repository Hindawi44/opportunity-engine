import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.germany_venta import (
    ACTIVE,
    ENDED,
    DEFAULT_VENTA_INDEX_URL,
    canonicalize_venta_url,
    fetch_venta_auction_index,
    parse_venta_auction_index,
    parse_venta_catalog_metadata,
)


ROOT = Path(__file__).resolve().parents[1]


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


def _catalog_html() -> str:
    return """
    <!doctype html>
    <html><body>
      <h1>Auktionskatalog Insolvenz-Versteigerung Modehaus Nord GmbH | 06.08.2026 - 18:00</h1>
      <h3>Informationen zur Versteigerung</h3>
      <p>Auslauf der Versteigerung | Donnerstag 6. August 2026 um 18.00 Uhr</p>
      <p>Standort | Modehaus Nord GmbH Hauptstr. 12 44135 Dortmund</p>
      <h3>Zur Beachtung</h3>
      <h3>Kompletter Warenbestand an Damenbekleidung und Schuhen</h3>
      <p>Auktion Nr. 6001</p>
      <p>Seite 1 von 2</p>
      <p>Objekte gesamt: 25</p>
      <a href="/item/id/6001_1_24_Damenjacken_55001.html">6001.1 =&gt; 24 Damenjacken</a>
      <a href="/item/id/6001_2_40_Paar_Damenschuhe_55002.html">6001.2 =&gt; 40 Paar Damenschuhe</a>
      <a href="/item/id/6001_1_24_Damenjacken_55001.html">mehr</a>
    </body></html>
    """


def test_venta_url_contract_separates_catalog_block_auction_and_object_identity():
    index = canonicalize_venta_url("http://auction.venta24.de/index.html?x=1")
    active = canonicalize_venta_url(
        "https://auction.venta24.de/browse/search/1/block/Example_792.html?sort=1"
    )
    closed = canonicalize_venta_url(
        "https://auction.venta24.de/browse/search/1/block/Example_789/search_closed/y.html"
    )
    item = canonicalize_venta_url(
        "https://auction.venta24.de/item/id/5214_559_1_PKW_Porsche_54138.html"
    )

    assert index is not None and index.kind == "AUCTION_INDEX"
    assert index.canonical_url == DEFAULT_VENTA_INDEX_URL
    assert active is not None and active.catalog_block_id == "792"
    assert active.closed_catalog is False
    assert closed is not None and closed.catalog_block_id == "789"
    assert closed.closed_catalog is True
    assert item is not None and item.kind == "ITEM_DETAIL"
    assert item.catalog_number == "5214"
    assert item.lot_number == "559"
    assert item.object_id == "54138"
    assert canonicalize_venta_url("https://example.de/browse/search/1/block/x_1.html") is None
    assert canonicalize_venta_url("https://auction.venta24.de/login.html") is None


def test_index_parser_requires_explicit_inventory_evidence_not_company_name():
    entries = parse_venta_auction_index(DEFAULT_VENTA_INDEX_URL, _index_html())

    assert [entry.catalog_block_id for entry in entries] == ["801", "802", "789"]
    clothing, machinery, apparel_name_only = entries
    assert clothing.listing_status == ACTIVE
    assert clothing.clothing_evidence is True
    assert set(clothing.clothing_terms) >= {"bekleidung", "textilien", "schuhe"}
    assert machinery.clothing_evidence is False
    assert apparel_name_only.title.startswith("Insolvenz-Versteigerung der Multiply Apparel")
    assert apparel_name_only.listing_status == ENDED
    assert apparel_name_only.clothing_evidence is False


def test_catalog_parser_resolves_stable_auction_and_item_identities():
    metadata = parse_venta_catalog_metadata(
        "https://auction.venta24.de/browse/search/1/block/Insolvenz_Modehaus_Nord_801.html",
        _catalog_html(),
    )

    assert metadata.catalog_block_id == "801"
    assert metadata.auction_number == "6001"
    assert metadata.opportunity_identity == "venta-auction:6001"
    assert metadata.listing_status == ACTIVE
    assert metadata.total_results == 25
    assert metadata.page_count == 2
    assert metadata.location == "Modehaus Nord GmbH Hauptstr. 12 44135 Dortmund"
    assert metadata.item_object_ids == ("55001", "55002")
    assert metadata.clothing_evidence is True
    assert set(metadata.clothing_terms) >= {"bekleidung", "schuhe"}


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
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response

    def get(self, url: str, **kwargs):
        return self.response


def test_index_fetch_fails_closed_on_redirect_or_non_html():
    with pytest.raises(ValueError, match="public VENTA auction index"):
        fetch_venta_auction_index(
            session=_FakeSession(
                _FakeResponse("https://auction.venta24.de/login.html", _index_html())
            )
        )

    with pytest.raises(RuntimeError, match="content type"):
        fetch_venta_auction_index(
            session=_FakeSession(
                _FakeResponse(DEFAULT_VENTA_INDEX_URL, _index_html(), "application/json")
            )
        )


def test_venta_source_contract_remains_planned_until_live_clothing_validation():
    contract = json.loads(
        (ROOT / "config" / "sources" / "de_venta_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract["source_id"] == "DE_VENTA_V1"
    assert contract["runtime_status"] == "PLANNED"
    assert contract["audit_decision"] == "GO_FOR_BOUNDED_INDEX_AND_CATALOG_ADAPTER"
    assert contract["filter_contract"]["company_name_is_clothing_evidence"] is False
    assert contract["identity_contract"]["auction_number_required_for_stable_opportunity"] is True
    assert contract["activation_requirements"]["live_clothing_catalog_required"] is True
    assert contract["activation_requirements"]["production_ready"] is False
    assert all(value is False for value in contract["safety_contract"].values())
