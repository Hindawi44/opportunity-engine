from opportunity_engine.landing_page_price import extract_nok_price_from_html


def test_extracts_json_ld_nok_price():
    html = '''
    <html><head><script type="application/ld+json">
    {"@type":"Product","offers":{"priceCurrency":"NOK","price":"4990"}}
    </script></head></html>
    '''
    price, source = extract_nok_price_from_html(html)
    assert price == 4990.0
    assert source == "json_ld"


def test_extracts_visible_kr_price():
    price, source = extract_nok_price_from_html("<html><body>Pris: 12 500 kr</body></html>")
    assert price == 12500.0
    assert source == "visible_text"


def test_rejects_bare_numbers():
    price, source = extract_nok_price_from_html("<html><body>2025 modell, 1530 stk, 300W</body></html>")
    assert price is None
    assert source is None


def test_structured_meta_requires_nok_context():
    price, source = extract_nok_price_from_html('<meta property="product:price:amount" content="999">')
    assert price is None
    assert source is None


def test_structured_meta_with_nok_context_is_accepted():
    html = '<meta property="product:price:amount" content="999"><meta property="product:price:currency" content="NOK">'
    price, source = extract_nok_price_from_html(html)
    assert price == 999.0
    assert source == "structured_meta"
