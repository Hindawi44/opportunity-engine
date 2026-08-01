from opportunity_engine.discovery.germany_riegermann_live_compat import (
    extract_riegermann_item_urls_compat,
    parse_riegermann_catalog_html_compat,
)

CATALOG_URL = (
    "https://riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh"
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
