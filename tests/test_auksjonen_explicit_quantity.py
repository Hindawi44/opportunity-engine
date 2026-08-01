from opportunity_engine.discovery.auksjonen_playwright_fallback import (
    AuksjonenPlaywrightFallbackVerifier,
)
from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ITEM_LISTING,
    UNRESOLVED_SOURCE,
    PageVerification,
)


AUKSJONEN_ITEM = (
    "https://auksjonen.no/auksjon/overskuddsvarer/"
    "8_stk_Blaklader_T-skjorter_i_storrelse_XL/557914"
)


def _unresolved(url=AUKSJONEN_ITEM):
    return PageVerification(
        url=url,
        page_role=UNRESOLVED_SOURCE,
        opportunity_identity="url-id:557914",
        identity_stable=True,
        verified=False,
        error="insufficient public listing content",
    )


def _run(monkeypatch, rendered):
    monkeypatch.setattr(
        "opportunity_engine.discovery.auksjonen_playwright_fallback.verify_public_html",
        lambda url, html: rendered,
    )
    verifier = AuksjonenPlaywrightFallbackVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=lambda url: (url, "<html/>"),
    )
    return verifier(AUKSJONEN_ITEM)


def _active_clothing(**overrides):
    values = {
        "url": AUKSJONEN_ITEM,
        "title": "Blåkläder T-skjorter",
        "text": "Produsent: Blåkläder. Materiale: bomull.",
        "listing_status": ACTIVE,
        "page_role": ITEM_LISTING,
        "opportunity_identity": "url-id:557914",
        "identity_stable": True,
        "verified": True,
    }
    values.update(overrides)
    return PageVerification(**values)


def test_extracts_quantity_from_explicit_antall_label(monkeypatch):
    result = _run(
        monkeypatch,
        _active_clothing(text="Antall: 8 stk T-skjorter. Produsent: Blåkläder."),
    )

    assert result.quantity == 8


def test_extracts_quantity_from_explicit_title_prefix(monkeypatch):
    result = _run(
        monkeypatch,
        _active_clothing(title="8 stk Blåkläder T-skjorter i størrelse XL"),
    )

    assert result.quantity == 8


def test_missing_quantity_remains_unknown(monkeypatch):
    result = _run(
        monkeypatch,
        _active_clothing(
            title="Blåkläder T-skjorter i størrelse XL modell 3325",
            text="Produsent: Blåkläder. Modell: 3325. Materiale: 100 % bomull.",
        ),
    )

    assert result.quantity is None


def test_model_and_article_numbers_are_not_guessed_as_quantity(monkeypatch):
    result = _run(
        monkeypatch,
        _active_clothing(
            title="Blåkläder modell 3325",
            text="Artikkelnummer: 883 07 2469. Størrelse: 46.",
        ),
    )

    assert result.quantity is None


def test_existing_quantity_is_preserved(monkeypatch):
    result = _run(
        monkeypatch,
        _active_clothing(
            quantity=12,
            text="Antall: 8 stk T-skjorter. Produsent: Blåkläder.",
        ),
    )

    assert result.quantity == 12
