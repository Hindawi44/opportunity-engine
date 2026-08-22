from __future__ import annotations

from opportunity_engine.automatic_query_gap_miss_scout import (
    PublicPage,
    _extract_company,
    _verify_closure_liquidation_page,
)


def _page(html: str) -> PublicPage:
    url = "https://example.no/products/real-closure"
    return PublicPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
    )


def test_company_identity_parser_recognizes_operating_identity_before_drives_av() -> None:
    text = "Senna Mode drives av Senna Mode B.V., et selskap registrert i Nederland."

    assert _extract_company(text) == "Senna Mode"


def test_exact_page_verifier_accepts_real_stenge_butikken_language_only_with_stock_sale_and_identity() -> None:
    proof = _verify_closure_liquidation_page(
        _page(
            """
            <html><body>
              <h1>Avviklingssalg</h1>
              <h2>Senna Mode Oslo</h2>
              <p>På grunn av personlige omstendigheter må vi dessverre stenge butikken vår.</p>
              <p>Derfor holder vi vårt største salg noensinne for å selge ut vårt siste varelager.</p>
              <p>Senna Mode drives av Senna Mode B.V., et selskap registrert i Nederland.</p>
            </body></html>
            """
        )
    )

    assert proof is not None
    assert proof["company"] == "Senna Mode"
    assert "stenge butikken" in proof["closure_markers"]
    assert "avviklingssalg" in proof["query_gap_terms"]
    assert "varelager" in proof["liquidation_markers"]


def test_stenge_butikken_phrase_alone_does_not_weaken_strict_contract() -> None:
    page = _page(
        """
        <html><body>
          <h1>Senna Mode</h1>
          <p>Vi må stenge butikken vår.</p>
          <p>Senna Mode drives av Senna Mode B.V.</p>
        </body></html>
        """
    )

    assert _verify_closure_liquidation_page(page) is None


def test_temporary_stenge_butikken_language_is_rejected_even_with_sale_and_inventory_words() -> None:
    page = _page(
        """
        <html><body>
          <h1>Avviklingssalg</h1>
          <p>Vi må stenge butikken midlertidig for oppussing.</p>
          <p>Varelager er tilgjengelig under kampanjen.</p>
          <p>Senna Mode drives av Senna Mode B.V.</p>
        </body></html>
        """
    )

    assert _verify_closure_liquidation_page(page) is None
