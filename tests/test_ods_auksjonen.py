from datetime import datetime, timedelta

import pytest

from opportunity_engine.ods.auksjonen import (
    AuksjonenClient,
    AuksjonenConnector,
    parse_auksjonen_listing_page,
)
from opportunity_engine.ods.models import ODSRequest


JSON_LD_PAGE = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "itemListElement": [
    {
      "@type": "Product",
      "name": "Butikkinnredning med hyller",
      "url": "/auksjon/123456/butikkinnredning",
      "description": "Komplett butikkinnredning",
      "offers": {
        "@type": "Offer",
        "price": "12500",
        "priceCurrency": "NOK",
        "validThrough": "2026-07-31T18:00:00+02:00"
      },
      "address": {"addressLocality": "Trondheim"}
    }
  ]
}
</script>
</head></html>
"""


FALLBACK_PAGE = """
<html><body>
<a href="/auksjon/987654/varelager-klaer">
  Varelager klær Avsluttes snart Gjenstår 2 dager Høyeste bud 8 500,- Bud
</a>
<a href="/auksjoner/">Alle auksjoner</a>
</body></html>
"""


def test_parse_json_ld_listing() -> None:
    documents = parse_auksjonen_listing_page(JSON_LD_PAGE)

    assert len(documents) == 1
    document = documents[0]
    assert document.document_id == "auksjonen-123456"
    assert document.title == "Butikkinnredning med hyller"
    assert document.url == "https://www.auksjonen.no/auksjon/123456/butikkinnredning"
    assert document.country == "Norway"
    assert document.metadata["current_price_nok"] == 12500.0
    assert document.metadata["price_type"] == "offer_price"
    assert document.metadata["price_status"] == "verified_from_json_ld"
    assert document.metadata["city"] == "Trondheim"
    assert document.metadata["ends_at"] == "2026-07-31T18:00:00+02:00"


def test_fallback_anchor_parser_extracts_listing() -> None:
    documents = parse_auksjonen_listing_page(FALLBACK_PAGE)

    assert len(documents) == 1
    assert documents[0].document_id == "auksjonen-987654"
    assert documents[0].title == "Varelager klær"
    assert documents[0].metadata["current_price_nok"] == 8500.0
    assert documents[0].metadata["price_type"] == "highest_bid"
    assert documents[0].metadata["price_status"] == "verified_from_listing_text"


@pytest.mark.parametrize(
    ("label", "expected_type"),
    [
        ("Nåværende bud: kr 12 750", "current_bid"),
        ("Gjeldende bud NOK 4.500", "current_bid"),
        ("Fastpris 18 000 kr", "fixed_price"),
        ("Kjøp nå for NOK 22 500", "buy_now"),
        ("Startpris: 3 000,-", "starting_price"),
    ],
)
def test_extracts_common_norwegian_price_formats(label: str, expected_type: str) -> None:
    html = f"""
    <html><body>
      <a href="/auksjon/765432/testobjekt">Testobjekt {label} Avsluttes 31.07.2026</a>
    </body></html>
    """

    document = parse_auksjonen_listing_page(html)[0]

    expected_price = {
        "current_bid": 12750.0 if "12 750" in label else 4500.0,
        "fixed_price": 18000.0,
        "buy_now": 22500.0,
        "starting_price": 3000.0,
    }[expected_type]
    assert document.metadata["current_price_nok"] == expected_price
    assert document.metadata["price_type"] == expected_type


def test_missing_price_is_explicit_and_not_invented() -> None:
    html = """
    <html><body>
      <a href="/auksjon/654321/ukjent-pris">Butikkinnredning Avsluttes snart</a>
    </body></html>
    """

    document = parse_auksjonen_listing_page(html)[0]

    assert document.metadata["current_price_nok"] is None
    assert document.metadata["price_type"] is None
    assert document.metadata["price_status"] == "missing_from_listing_text"


def test_json_ld_aggregate_offer_uses_low_price() -> None:
    html = JSON_LD_PAGE.replace(
        '"price": "12500",',
        '"lowPrice": "9 900",\n        "highPrice": "15 000",',
    )

    document = parse_auksjonen_listing_page(html)[0]

    assert document.metadata["current_price_nok"] == 9900.0
    assert document.metadata["price_type"] == "low_price"


def test_connector_uses_request_subject_as_query() -> None:
    calls: list[str] = []

    def transport(url: str, timeout: float, headers: dict[str, str]) -> str:
        calls.append(url)
        assert timeout == 7.0
        assert headers["Accept"].startswith("text/html")
        return JSON_LD_PAGE

    connector = AuksjonenConnector(AuksjonenClient(timeout=7.0, transport=transport))
    request = ODSRequest(subject="butikk inventar", country="Norway")

    documents = connector.fetch(request)

    assert len(documents) == 1
    assert calls == ["https://www.auksjonen.no/auksjoner/?q=butikk+inventar"]


def test_empty_page_returns_no_documents() -> None:
    assert parse_auksjonen_listing_page("   ") == ()


def test_client_rejects_insecure_base_url() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AuksjonenClient(base_url="http://example.test")


def test_invalid_end_time_is_not_invented() -> None:
    html = JSON_LD_PAGE.replace("2026-07-31T18:00:00+02:00", "unknown")
    document = parse_auksjonen_listing_page(html)[0]
    assert document.metadata["ends_at"] is None


def test_expected_end_time_representation_is_iso_8601() -> None:
    document = parse_auksjonen_listing_page(JSON_LD_PAGE)[0]
    parsed = datetime.fromisoformat(document.metadata["ends_at"])
    assert parsed.year == 2026
    assert parsed.month == 7
    assert parsed.day == 31
    assert parsed.hour == 18
    assert parsed.utcoffset() == timedelta(hours=2)
