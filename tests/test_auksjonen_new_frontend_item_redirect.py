from opportunity_engine.discovery.auksjonen_playwright_fallback import (
    AuksjonenPlaywrightFallbackVerifier,
    canonicalize_auksjonen_item_url,
    is_specific_auksjonen_item_url,
)
from opportunity_engine.discovery.clothing_inventory_search import PageVerification


OLD_ITEM_URL = (
    "https://auksjonen.no/auksjon/overskuddsvarer/"
    "Parti_med_24_klesartikler/558602"
)
NEW_ITEM_URL = (
    "https://ny.auksjonen.no/auksjon/overskuddsvarer/"
    "Parti_med_24_klesartikler/558602"
)


def _unresolved(url: str) -> PageVerification:
    return PageVerification(
        url=url,
        verified=False,
        error="insufficient public listing content",
    )


def test_new_frontend_item_url_is_approved_and_canonicalized() -> None:
    assert is_specific_auksjonen_item_url(NEW_ITEM_URL) is True
    assert canonicalize_auksjonen_item_url(NEW_ITEM_URL) == OLD_ITEM_URL
    assert canonicalize_auksjonen_item_url(
        "https://ny.auksjonen.no/auksjoner/overskudd_klaer"
    ) is None
    assert canonicalize_auksjonen_item_url(
        "https://example.no/auksjon/overskuddsvarer/Test/558602"
    ) is None


def test_playwright_accepts_same_item_redirect_to_new_frontend_host() -> None:
    html = """
    <html><head><title>Parti med 24 klesartikler</title></head>
    <body>
      <h1>Parti med 24 klesartikler</h1>
      <p>Auksjon pågår. 24 klær selges samlet.</p>
    </body></html>
    """
    verifier = AuksjonenPlaywrightFallbackVerifier(
        _unresolved,
        rendered_page_loader=lambda url: (NEW_ITEM_URL, html),
    )

    result = verifier(OLD_ITEM_URL)

    assert "redirected outside" not in str(result.error or "")
    assert verifier.diagnostics()["attempted"] == 1


def test_playwright_still_rejects_unrelated_new_frontend_redirect() -> None:
    verifier = AuksjonenPlaywrightFallbackVerifier(
        _unresolved,
        rendered_page_loader=lambda url: (
            "https://ny.auksjonen.no/auksjoner/overskudd_klaer",
            "<html><body>Kategori</body></html>",
        ),
    )

    result = verifier(OLD_ITEM_URL)

    assert "redirected outside one specific Auksjonen item" in str(result.error)
    assert verifier.diagnostics()["failed"] == 1
