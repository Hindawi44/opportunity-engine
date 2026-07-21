from scripts.enrich_auksjonen_listing_metadata import parse_listing_metadata


def test_parses_direct_json_ld_metadata_without_estimating() -> None:
    html = '''
    <script type="application/ld+json">
    {"@type":"Product","name":"Lagerreol","offers":{"@type":"Offer","price":"4500","validThrough":"2026-08-01T12:00:00+02:00"},"address":{"addressLocality":"Namsos"}}
    </script>
    '''
    result = parse_listing_metadata(html)
    assert result == {
        "asking_price_nok": 4500.0,
        "city": "Namsos",
        "ends_at": "2026-08-01T12:00:00+02:00",
    }


def test_missing_values_remain_null() -> None:
    result = parse_listing_metadata('<html><body>Ingen observerbare økonomiske data</body></html>')
    assert result == {"asking_price_nok": None, "city": None, "ends_at": None}


def test_parses_visible_current_bid_as_fallback() -> None:
    result = parse_listing_metadata('<div>Høyeste bud 12 500,-</div>')
    assert result["asking_price_nok"] == 12500.0
