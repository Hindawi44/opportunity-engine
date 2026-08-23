from __future__ import annotations


def test_company_identity_parser_recognizes_name_before_avvikles() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import _extract_company

    assert _extract_company("BAUHAUS Norge avvikles i Norge.") == "BAUHAUS Norge"
    assert _extract_company("BAUHAUS avvikles i Norge.") == "BAUHAUS"


def test_company_identity_parser_recognizes_name_before_opphorer() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import _extract_company

    assert _extract_company("Eksempel Handel opphører etter 20 år.") == "Eksempel Handel"


def test_company_identity_parser_still_rejects_generic_label_before_avvikles() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import _extract_company

    assert _extract_company("Butikken avvikles i Norge.") is None


def test_exact_page_verifier_rejects_out_of_domain_avvikling_even_with_concrete_identity() -> None:
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
        <h1>BAUHAUS Norge avvikles</h1>
        <p>Fra 22. august starter opphørssalg.</p>
        <p>Lagerbeholdningen med byggematerialer, verktøy og fliser skal selges ut.</p>
        </body></html>
        """,
    )

    assert _verify_closure_liquidation_page(page) is None


def test_exact_page_verifier_accepts_same_avvikling_shape_when_clothing_is_proven() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        _verify_closure_liquidation_page,
    )

    url = "https://example.no/nordic-fashion-avvikling"
    page = PublicPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=UTF-8",
        html="""
        <html><body>
        <h1>Nordic Fashion avvikles</h1>
        <p>Klesbutikken starter opphørssalg.</p>
        <p>Hele lagerbeholdningen av klær, jakker og bukser skal selges ut.</p>
        </body></html>
        """,
    )

    proof = _verify_closure_liquidation_page(page)
    assert proof is not None
    assert proof["company"] == "Nordic Fashion"
    assert proof["project_domain"] == "CLOTHING_INVENTORY"
