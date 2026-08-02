from __future__ import annotations

from dataclasses import dataclass

from opportunity_engine.discovery.germany_riegermann_live_compat import (
    extract_riegermann_catalog_page_urls_compat,
    extract_riegermann_item_urls_compat,
    install_riegermann_live_catalog_compatibility,
    parse_riegermann_catalog_html_compat,
    run_riegermann_live_discovery_compat,
)

CATALOG_URL = (
    "https://riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh"
)
CATALOG_PAGE_2_URL = (
    "https://riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh?Lstatus=1&currentpos=24&oldpagesize=24"
)
CATALOG_PAGE_3_URL = (
    "https://riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh?Lstatus=1&currentpos=48&oldpagesize=24"
)
INFORMATION_URL = (
    "https://riegermann.de/de/2019_versteigerung_cabrini_gmbh/a/908"
)


def test_compat_extracts_absolute_and_relative_item_links_once():
    source = """
    <html><body>
      <a href="https://www.riegermann.de/de/l/73457/damen_lederjacke_groesse_36?x=1">A</a>
      <a href="/de/l/73457/damen_lederjacke_groesse_36">duplicate</a>
      <a href="https://riegermann.de/de/l/73490/posten_lederjacken_24_stueck">B</a>
      <a href="https://example.de/de/l/99999/not-riegermann">noise</a>
    </body></html>
    """

    assert extract_riegermann_item_urls_compat(CATALOG_URL, source) == (
        "https://riegermann.de/de/l/73457/damen_lederjacke_groesse_36",
        "https://riegermann.de/de/l/73490/posten_lederjacken_24_stueck",
    )


def test_compat_extracts_same_auction_pagination_once_per_offset():
    source = f"""
    <html><body>
      <a href="?Lstatus=1&currentpos=24&oldpagesize=24">2</a>
      <a href="{CATALOG_PAGE_2_URL}&ord=title">duplicate offset</a>
      <a href="{CATALOG_PAGE_3_URL}">3</a>
      <a href="/de/objekte/au-909/other?currentpos=24">other auction</a>
      <a href="/de/l/73457/damen_lederjacke_groesse_36">item</a>
    </body></html>
    """

    assert extract_riegermann_catalog_page_urls_compat(CATALOG_URL, source) == (
        CATALOG_PAGE_2_URL,
        CATALOG_PAGE_3_URL,
    )


def test_compat_retains_generic_absolute_link_as_conservative_child_evidence():
    source = """
    <!doctype html>
    <html>
      <head><title>Versteigerung Cabrini GmbH</title></head>
      <body>
        <h1>Versteigerung Cabrini GmbH</h1>
        <p>Aktuell</p>
        <a href="https://www.riegermann.de/de/l/73457/damen_lederjacke_groesse_36?x=1">
          Damen Lederjacke Größe 36
        </a>
      </body>
    </html>
    """

    event = parse_riegermann_catalog_html_compat(CATALOG_URL, source)

    assert event.auction_id == "908"
    assert len(event.child_lots) == 1
    lot = event.child_lots[0]
    assert lot.object_id == "73457"
    assert lot.ordinary_single_garment is True
    assert lot.promotion_eligible is False
    assert lot.top5_eligible is False
    assert lot.quantity is None
    assert lot.source_start_or_minimum_price_eur is None
    assert lot.source_displayed_bid_eur is None
    assert lot.final_sale_price_eur is None
    assert lot.price_nok is None
    assert lot.bid_price_nok is None


def test_compat_promotes_only_explicit_bulk_slug_without_inventing_price():
    source = """
    <!doctype html>
    <html>
      <head><title>Versteigerung Cabrini GmbH</title></head>
      <body>
        <p>Aktuell</p>
        <a href="https://www.riegermann.de/de/l/73490/posten_lederjacken_24_stueck">
          Posten Lederjacken 24 Stück
        </a>
      </body>
    </html>
    """

    event = parse_riegermann_catalog_html_compat(CATALOG_URL, source)
    lot = event.child_lots[0]

    assert lot.object_id == "73490"
    assert lot.bulk_evidence is True
    assert lot.promotion_eligible is True
    assert lot.quantity == 24
    assert lot.source_price_kind is None
    assert lot.source_start_or_minimum_price_eur is None
    assert lot.source_displayed_bid_eur is None
    assert lot.final_sale_price_trusted is False


def test_compat_does_not_extract_lots_from_information_page():
    source = """
    <!doctype html>
    <html>
      <head><title>Versteigerung Cabrini GmbH</title></head>
      <body>
        <h1>Versteigerung Cabrini GmbH</h1>
        <p>Aktuell</p>
        <p>Ort: DE-55450 Langenlonsheim</p>
      </body>
    </html>
    """

    event = parse_riegermann_catalog_html_compat(INFORMATION_URL, source)

    assert event.auction_id == "908"
    assert event.child_lots == ()
    assert event.location == "DE-55450 Langenlonsheim"


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200
    content_type: str = "text/html; charset=utf-8"

    def __post_init__(self) -> None:
        self.content = self.text.encode("utf-8")
        self.encoding = "utf-8"
        self.headers = {"content-type": self.content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        try:
            return self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"unexpected URL: {url}") from exc


def _catalog_page(*, item_url: str, next_url: str | None = None) -> str:
    next_link = f'<a href="{next_url}">next</a>' if next_url else ""
    return f"""
    <!doctype html>
    <html>
      <head><title>Versteigerung Cabrini GmbH</title></head>
      <body>
        <h1>Versteigerung Cabrini GmbH</h1>
        <p>Vorschau</p>
        <a href="{item_url}">item</a>
        {next_link}
      </body>
    </html>
    """


def _information_page() -> str:
    return """
    <!doctype html>
    <html>
      <head><title>Versteigerung Cabrini GmbH</title></head>
      <body>
        <h1>Versteigerung Cabrini GmbH</h1>
        <p>Aktuell</p>
        <p>DE-55450 Langenlonsheim, An den Nahewiesen 12 + 13</p>
        <p>Zuschläge am Montag</p>
        <p>Aufgeld: 20% - USt.: 19%</p>
      </body>
    </html>
    """


def test_live_compat_collects_all_catalog_pages_and_propagates_active_status():
    install_riegermann_live_catalog_compatibility()
    ordinary_url = "https://riegermann.de/de/l/73249/damen_lederjacke_groesse_42"
    bulk_url = "https://riegermann.de/de/l/73490/posten_lederjacken_24_stueck"
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(
                CATALOG_URL,
                _catalog_page(item_url=ordinary_url, next_url=CATALOG_PAGE_2_URL),
            ),
            CATALOG_PAGE_2_URL: FakeResponse(
                CATALOG_PAGE_2_URL,
                _catalog_page(item_url=bulk_url),
            ),
            INFORMATION_URL: FakeResponse(INFORMATION_URL, _information_page()),
        }
    )

    live = run_riegermann_live_discovery_compat(
        CATALOG_URL,
        information_url=INFORMATION_URL,
        session=session,
        item_verification_limit=0,
    )
    result = live.discovery_result
    report = result["search_run_report"]["riegermann_live"]
    parent = next(
        candidate
        for candidate in result["all_discovered_candidates"]
        if candidate["page_role"] == "AUCTION_EVENT"
    )

    assert report["catalog_page_count"] == 2
    assert report["catalog_coverage_complete"] is True
    assert report["catalog_item_url_count"] == 2
    assert report["parsed_child_lot_count"] == 2
    assert report["promoted_bulk_lot_count"] == 1
    assert parent["catalog_pages_fetched"] == 2
    assert parent["catalog_coverage_complete"] is True
    assert parent["child_lot_count"] == 2
    assert parent["promoted_bulk_lot_count"] == 1
    assert parent["location"] == "DE-55450 Langenlonsheim, An den Nahewiesen 12 + 13"
    assert {lot["listing_status"] for lot in parent["child_lots"]} == {"ACTIVE"}
    assert session.calls == [CATALOG_URL, CATALOG_PAGE_2_URL, INFORMATION_URL]


def test_live_compat_marks_catalog_incomplete_when_page_limit_is_reached():
    install_riegermann_live_catalog_compatibility()
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(
                CATALOG_URL,
                _catalog_page(
                    item_url="https://riegermann.de/de/l/73249/damen_lederjacke_groesse_42",
                    next_url=CATALOG_PAGE_2_URL,
                ),
            ),
            CATALOG_PAGE_2_URL: FakeResponse(
                CATALOG_PAGE_2_URL,
                _catalog_page(
                    item_url="https://riegermann.de/de/l/73250/damen_lederjacke_groesse_44",
                    next_url=CATALOG_PAGE_3_URL,
                ),
            ),
        }
    )

    live = run_riegermann_live_discovery_compat(
        CATALOG_URL,
        session=session,
        item_verification_limit=0,
        catalog_page_limit=2,
    )
    result = live.discovery_result
    report = result["search_run_report"]["riegermann_live"]
    parent = result["all_discovered_candidates"][0]

    assert report["catalog_page_count"] == 2
    assert report["catalog_page_limit_reached"] is True
    assert report["catalog_coverage_complete"] is False
    assert parent["catalog_coverage_complete"] is False
    assert "complete public catalog coverage" in parent["missing_information"]
    assert parent["post_verification_top5_block_reason"] == (
        "catalog_pagination_incomplete"
    )
