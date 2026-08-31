from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    parse_auksjonen_item_page,
)


def test_blaklader_condition_section_marks_new_lot_as_new_or_unused() -> None:
    html = """
    <!doctype html>
    <html>
      <body>
        <h1>22 stk Blåkläder arbeidsjakker i størrelse S - modell 3463 og 4830</h1>
        <h2>Beskrivelse</h2>
        <p>Parti med 22 stk Blåkläder arbeidsjakker i størrelse Small.</p>
        <h2>Tilstand og egenerklæring</h2>
        <p>Nytt.</p>
      </body>
    </html>
    """

    parsed = parse_auksjonen_item_page(html)

    assert parsed["quantity"] == 22
    assert parsed["condition"] == "NEW_OR_UNUSED"


def test_standalone_new_word_without_condition_heading_is_not_trusted() -> None:
    html = """
    <!doctype html>
    <html>
      <body>
        <h1>22 stk arbeidsjakker</h1>
        <p>Nytt parti tilgjengelig på lager.</p>
      </body>
    </html>
    """

    parsed = parse_auksjonen_item_page(html)

    assert parsed["quantity"] == 22
    assert parsed["condition"] is None
