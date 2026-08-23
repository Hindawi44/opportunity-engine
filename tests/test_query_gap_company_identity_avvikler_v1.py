from __future__ import annotations


def test_extract_company_accepts_active_avvikler_form() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import _extract_company

    text = "BAUHAUS avvikler virksomheten i Norge."

    assert _extract_company(text) == "BAUHAUS"


def test_official_bauhaus_style_page_is_out_of_domain_even_with_company_identity() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        _verify_closure_liquidation_page,
    )

    page = PublicPage(
        requested_url="https://www.bauhaus.no/bauhaus-norge-informasjon",
        final_url="https://www.bauhaus.no/bauhaus-norge-informasjon",
        status_code=200,
        content_type="text/html; charset=UTF-8",
        html="""
        <html><body>
        <h1>BAUHAUS avvikler virksomheten i Norge.</h1>
        <p>Opphørssalget starter lørdag 22. august.</p>
        <p>I forbindelse med avviklingen vil vi selge ut byggematerialer, verktøy og fliser.</p>
        <p>Kundeservice har ikke ytterligere informasjon om lagerbeholdningen.</p>
        </body></html>
        """,
    )

    assert _verify_closure_liquidation_page(page) is None
