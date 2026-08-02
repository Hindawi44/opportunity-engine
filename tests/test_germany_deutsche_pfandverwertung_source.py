import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.germany_deutsche_pfandverwertung import (
    ACTIVE,
    ENDED,
    DEFAULT_DPV_INDEX_URL,
    canonicalize_dpv_url,
    fetch_dpv_auction_index,
    parse_dpv_auction_index,
    parse_dpv_item_metadata,
)


ROOT = Path(__file__).resolve().parents[1]


def _index_html() -> str:
    return """
    <!doctype html>
    <html><body>
      <h2>Katalogübersicht</h2>
      <section class="catalog-card">
        <a href="/schuhhaus-warenbestand--search-1-block-183-browse.html">
          Öffentliche Versteigerung Schuhhaus Warenbestand
        </a>
        <p>Großkonvolut 3.741 Paar Schuhe, Schals, Taschen und Socken.</p>
        <p>Beginn Do 06.08.2026 um 12:00</p>
        <p>LIVE</p>
        <a href="/schuhhaus-warenbestand--search-1-block-183-browse.html">
          Katalog ansehen (Anzahl Artikel: 2)
        </a>
      </section>
      <section class="catalog-card">
        <a href="/porsche-restaurierungsobjekt--search-1-block-184-browse.html">
          1 PKW Porsche Restaurierungsobjekt
        </a>
        <p>Fahrzeug und Ersatzteile.</p>
        <p>Beginn Fr 07.08.2026 um 12:00</p>
        <a href="/porsche-restaurierungsobjekt--search-1-block-184-browse.html">
          Katalog ansehen (Anzahl Artikel: 1)
        </a>
      </section>
      <h2>Vergangene Versteigerungen</h2>
      <section class="catalog-card">
        <a href="/markenrechte-hallhuber--search-1-search_closed-y-block-150-browse.html">
          Markenrechte Hallhuber und Donna Hallhuber
        </a>
        <p>62 Markenrechte und 28 Domains.</p>
        <p>Versteigerung beendet</p>
        <a href="/markenrechte-hallhuber--search-1-search_closed-y-block-150-browse.html">
          Katalog ansehen (Anzahl Artikel: 2)
        </a>
      </section>
    </body></html>
    """


def _outdoor_item_html() -> str:
    return """
    <!doctype html>
    <html><body>
      <h1>Losnummer 1 - 1 Konvolut Outdoor Artikel Neuware der Marken Black Snake und noorsk aufgrund Pfandrecht des Lagerhalters</h1>
      <p>Versteigerung startet am: 27.05.2026 - 12:00:00</p>
      <p>Los ist verkauft</p>
      <h3>Verkaufspreis 80.000,00 EUR</h3>
      <p>68 Gebote / 4 Vorgebote</p>
      <div class="description">
        Das Konvolut umfasst 7.440 Packungen Black Snake Funktionsunterwäsche,
        Campingausrüstung und weitere Artikel in Sachgesamtheit.
      </div>
      <h3>Standort</h3>
      <p>Ca. Standort: Deutschland, 67227</p>
      <p>Dieser Eintrag wurde 299 mal aufgerufen.</p>
    </body></html>
    """


def test_dpv_url_contract_separates_index_catalog_and_item_identity():
    index = canonicalize_dpv_url(
        "http://versteigerungen-deutsche-pfandverwertung.de/index.html?x=1"
    )
    active = canonicalize_dpv_url(
        "https://www.versteigerungen-deutsche-pfandverwertung.de/"
        "schuhbestand--search-1-block-183-browse.html?sort=1"
    )
    closed = canonicalize_dpv_url(
        "https://www.versteigerungen-deutsche-pfandverwertung.de/"
        "outdoor--search-1-search_closed-y-block-177-browse.html"
    )
    item = canonicalize_dpv_url(
        "https://www.versteigerungen-deutsche-pfandverwertung.de/"
        "00-live-versteigerungen/outdoor-konvolut--id-2175-item.html?ref=1"
    )

    assert index is not None and index.kind == "AUCTION_INDEX"
    assert index.canonical_url == DEFAULT_DPV_INDEX_URL
    assert active is not None and active.catalog_block_id == "183"
    assert active.closed_catalog is False
    assert active.canonical_url.endswith("block-183-browse.html")
    assert closed is not None and closed.catalog_block_id == "177"
    assert closed.closed_catalog is True
    assert item is not None and item.kind == "ITEM_DETAIL"
    assert item.object_id == "2175"
    assert item.canonical_url.endswith("--id-2175-item.html")
    assert canonicalize_dpv_url("https://example.de/blocks_overview.php") is None
    assert canonicalize_dpv_url(
        "https://www.versteigerungen-deutsche-pfandverwertung.de/login.php"
    ) is None


def test_index_parser_selects_explicit_clothing_inventory_and_rejects_brand_rights():
    entries = parse_dpv_auction_index(DEFAULT_DPV_INDEX_URL, _index_html())

    assert [entry.catalog_block_id for entry in entries] == ["183", "184", "150"]
    clothing, vehicle, brand_rights = entries
    assert clothing.opportunity_identity == "dpv-auction:183"
    assert clothing.listing_status == ACTIVE
    assert clothing.item_count == 2
    assert clothing.clothing_evidence is True
    assert set(clothing.clothing_terms) >= {"schuhe", "schals", "taschen", "socken"}
    assert clothing.bulk_evidence is True
    assert set(clothing.bulk_terms) >= {"konvolut", "multi_unit"}
    assert vehicle.clothing_evidence is False
    assert brand_rights.title.startswith("Markenrechte Hallhuber")
    assert brand_rights.listing_status == ENDED
    assert brand_rights.clothing_evidence is False


def test_item_parser_preserves_historical_bulk_clothing_evidence_and_eur_semantics():
    metadata = parse_dpv_item_metadata(
        "https://www.versteigerungen-deutsche-pfandverwertung.de/"
        "00-live-versteigerungen/1-konvolut-outdoor-artikel-neuware-"
        "der-marken-black-snake-und-noorsk-aufgrund-pfandrecht-des-"
        "lagerhalters--id-2175-item.html",
        _outdoor_item_html(),
    )

    assert metadata.object_id == "2175"
    assert metadata.opportunity_identity == "dpv-object:2175"
    assert metadata.lot_number == "1"
    assert metadata.listing_status == ENDED
    assert metadata.displayed_amount_eur == 80000.0
    assert metadata.displayed_amount_kind == "FINAL_SALE_PRICE"
    assert metadata.bid_count == 68
    assert metadata.location == "Deutschland, 67227"
    assert "7.440 Packungen" in metadata.quantity_mentions
    assert metadata.clothing_evidence is True
    assert "unterwaesche" in metadata.clothing_terms
    assert metadata.bulk_evidence is True
    assert set(metadata.bulk_terms) >= {"konvolut", "sachgesamtheit", "multi_unit"}


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
    with pytest.raises(ValueError, match="public Deutsche Pfandverwertung"):
        fetch_dpv_auction_index(
            session=_FakeSession(
                _FakeResponse(
                    "https://www.versteigerungen-deutsche-pfandverwertung.de/login.php",
                    _index_html(),
                )
            )
        )

    with pytest.raises(RuntimeError, match="content type"):
        fetch_dpv_auction_index(
            session=_FakeSession(
                _FakeResponse(DEFAULT_DPV_INDEX_URL, _index_html(), "application/json")
            )
        )


def test_dpv_source_contract_remains_planned_until_live_clothing_validation():
    contract = json.loads(
        (
            ROOT
            / "config"
            / "sources"
            / "de_deutsche_pfandverwertung_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert contract["source_id"] == "DE_DEUTSCHE_PFANDVERWERTUNG_V1"
    assert contract["runtime_status"] == "PLANNED"
    assert contract["audit_decision"] == "GO_FOR_BOUNDED_INDEX_AND_ITEM_ADAPTER"
    assert contract["identity_contract"]["object_id_is_required_for_item_deduplication"] is True
    assert contract["filter_contract"]["brand_rights_are_clothing_inventory"] is False
    assert contract["known_public_evidence"]["historical_clothing_item_identity"] == "dpv-object:2175"
    assert contract["activation_requirements"]["live_active_clothing_catalog_required"] is True
    assert contract["activation_requirements"]["production_ready"] is False
    assert all(value is False for value in contract["safety_contract"].values())
