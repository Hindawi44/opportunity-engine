from opportunity_engine.discovery.keyword_shadow_verification import _parse_html


def test_invalid_mysql_collation_charset_falls_back_to_latin1():
    body = (
        b"<html><head><title>Liquidazione abbigliamento</title></head>"
        b"<body>Azienda Srl - prezzo 10 EUR - disponibilit\xe0 immediata</body></html>"
    )

    title, text = _parse_html(body, "latin1_general_ci")

    assert title == "Liquidazione abbigliamento"
    assert "disponibilità immediata" in text


def test_unknown_charset_falls_back_to_utf8():
    body = "<html><body>Stock abbigliamento – Milano</body></html>".encode("utf-8")

    _, text = _parse_html(body, "not-a-real-charset")

    assert "Stock abbigliamento – Milano" in text
