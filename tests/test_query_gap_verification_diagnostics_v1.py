from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit


RITA_URL = (
    "https://www.vartoslo.no/anbefalt-bydel-sentrum-hille-melbye-arkitekter/"
    "butikken-legger-ned-etter-90-ar-store-planer-for-sentrumsbygarden/1252479"
)
RITA_HTML = """
<html><body>
<h1>Butikken legger ned etter 90 år</h1>
<p>Klesbutikken Rita Korsettsalong i Storgata 9 stenger etter 90 år.</p>
<p>I vinduet står det «Sluttsalg» og «Alt skal ut».</p>
<p>Rita Korsettsalong legges ned. Alle varer skal ut av butikken.</p>
<p>Siste åpningsdag blir 1. oktober.</p>
</body></html>
"""


def _page(url: str, html: str, *, status: int = 200, content_type: str = "text/html"):
    from opportunity_engine.automatic_query_gap_miss_scout import PublicPage

    return PublicPage(
        requested_url=url,
        final_url=url,
        status_code=status,
        content_type=content_type,
        html=html,
    )


def _hit(url: str, title: str = "Butikken legger ned") -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description="Butikken stenger for godt.",
        provider="Brave Search",
    )


def test_diagnostic_explains_missing_verification_dimensions() -> None:
    from opportunity_engine.query_gap_scout_waterfall import diagnose_public_page

    url = "https://example.no/closure"
    diagnostic = diagnose_public_page(
        _page(url, "<html><body>Butikken stenger for godt.</body></html>")
    )

    assert diagnostic["verifier_status"] == "REJECTED"
    assert diagnostic["evidence_flags"]["html_ok"] is True
    assert diagnostic["evidence_flags"]["https_ok"] is True
    assert diagnostic["evidence_flags"]["closure_marker"] is True
    assert diagnostic["evidence_flags"]["sale_term"] is False
    assert diagnostic["evidence_flags"]["liquidation_marker"] is False
    assert diagnostic["evidence_flags"]["company_identity"] is False
    assert set(diagnostic["rejection_reasons"]) >= {
        "SALE_TERM_MISSING",
        "INVENTORY_LIQUIDATION_MISSING",
        "COMPANY_IDENTITY_MISSING",
    }


def test_verified_rita_page_has_no_rejection_reasons() -> None:
    from opportunity_engine.query_gap_scout_waterfall import diagnose_public_page

    diagnostic = diagnose_public_page(_page(RITA_URL, RITA_HTML))

    assert diagnostic["verifier_status"] == "VERIFIED"
    assert diagnostic["rejection_reasons"] == []
    assert diagnostic["evidence_flags"]["closure_marker"] is True
    assert diagnostic["evidence_flags"]["sale_term"] is True
    assert diagnostic["evidence_flags"]["liquidation_marker"] is True
    assert diagnostic["evidence_flags"]["company_identity"] is True
    assert diagnostic["company"] == "Rita Korsettsalong"


def test_non_html_and_temporary_closure_are_explained_fail_closed() -> None:
    from opportunity_engine.query_gap_scout_waterfall import diagnose_public_page

    non_html = diagnose_public_page(
        _page("https://example.no/file", "binary", content_type="application/pdf")
    )
    assert non_html["verifier_status"] == "REJECTED"
    assert "HTML_REQUIRED" in non_html["rejection_reasons"]

    temporary = diagnose_public_page(
        _page(
            "https://example.no/temporary",
            "<html><body>Butikken er midlertidig stengt for oppussing. Sluttsalg. Alt skal ut.</body></html>",
        )
    )
    assert temporary["verifier_status"] == "REJECTED"
    assert "TEMPORARY_CLOSURE_SIGNAL" in temporary["rejection_reasons"]


def test_waterfall_records_bounded_attempt_diagnostics_without_promoting_hits() -> None:
    from opportunity_engine.query_gap_scout_waterfall import (
        SCOUT_QUERIES_NO,
        discover_query_gap_misses,
    )

    urls = [
        "https://example.no/one",
        "https://example.no/two",
        "https://example.no/three",
        "https://example.no/four",
    ]

    def search(query: str):
        if query == SCOUT_QUERIES_NO[0]:
            return [_hit(urls[0])]
        return [_hit(urls[1]), _hit(urls[2]), _hit(urls[3])]

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=[],
        search=search,
        fetch_page=lambda url: _page(
            url,
            "<html><body>Butikken stenger for godt, men ingen dokumentert lagertømming.</body></html>",
        ),
        max_pages=3,
    )

    attempts = outcome["verification_attempts"]
    assert len(attempts) == 3
    assert outcome["page_request_count"] == 3
    assert all(item["verifier_status"] == "REJECTED" for item in attempts)
    assert all(item["search_hit_alone_is_ground_truth"] is False for item in attempts)
    assert all(item["automatic_query_activation"] is False for item in attempts)
    assert {item["stage"] for item in attempts} == {1, 2}


def test_fetch_failure_is_diagnostic_and_does_not_create_ground_truth() -> None:
    from opportunity_engine.query_gap_scout_waterfall import discover_query_gap_misses

    url = "https://example.no/fetch-fails"

    def fetch_page(_url: str):
        raise TimeoutError("network timeout")

    outcome = discover_query_gap_misses(
        {"deduplicated_opportunities": []},
        active_queries=[],
        search=lambda query: [_hit(url)] if "varelager" in query else [],
        fetch_page=fetch_page,
        max_pages=1,
    )

    [attempt] = outcome["verification_attempts"]
    assert attempt["verifier_status"] == "FETCH_FAILED"
    assert attempt["rejection_reasons"] == ["PAGE_FETCH_FAILED"]
    assert attempt["error_type"] == "TimeoutError"
    assert outcome["detected_miss_count"] == 0
