from __future__ import annotations

from datetime import datetime, timezone
import json

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.automatic_query_gap_miss_scout import PublicPage
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    save_learned_query_overlay,
)
from opportunity_engine.learning_promotion_gate import select_promoted_query_overlay
from opportunity_engine.promoted_learned_core_discovery import (
    _clean_verified_company_name,
    collect_promoted_learned_core_opportunities,
)


TERM = "avviklingssalg"
NOW = datetime(2026, 8, 22, 21, 30, tzinfo=timezone.utc)


def _overlay(tmp_path):
    evaluation = KeywordEvaluationResult(
        term=TERM,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=(
            "HOLDOUT-NO-SENZE-OF-JOY",
            "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER",
            "HOLDOUT-NO-CLOTHING-THREE",
        ),
        raw_hit_count=9,
        verified_relevant_count=3,
        precision=1 / 3,
        min_recovered_cases=1,
        min_precision=0.20,
        automatic_activation=False,
        support_case_ids=("AUTO-MISS-NO-CLOTHING-LIQUIDATION",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )
    shadow = build_learned_query_overlay([evaluation])
    active = select_promoted_query_overlay(shadow, {("NO", TERM): "PROMOTED"})
    path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(path, active)
    return path


def _page(url: str) -> PublicPage:
    html = """
    <html><body>
      <div>Stengt BEDRIFTSDETALJER BEDRIFTSDETALJER Senna Mode drives av Senna Mode B.V.</div>
      <div>Klesbutikken selger klær, jakker og bukser.</div>
      <div>Avviklingssalg</div>
      <div>Vi må dessverre stenge butikken vår og selge ut vårt siste varelager.</div>
    </body></html>
    """
    return PublicPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        html=html,
    )


def test_promoted_output_cleans_repeated_template_noise_from_verified_company():
    assert (
        _clean_verified_company_name(
            "Stengt BEDRIFTSDETALJER BEDRIFTSDETALJER Senna Mode"
        )
        == "Senna Mode"
    )


def test_promoted_core_collapses_same_company_same_liquidation_across_product_pages(tmp_path):
    overlay = _overlay(tmp_path)
    urls = [
        "https://www.sennamode.com/products/alpha",
        "https://www.sennamode.com/products/beta",
        "https://www.sennamode.com/products/gamma",
    ]

    def search(_query: str):
        return [
            SearchHit(
                title=f"Product {index} – Senna Mode",
                url=url,
                description="Klesbutikk avviklingssalg – stenge butikken",
                provider="Brave Search",
            )
            for index, url in enumerate(urls, start=1)
        ]

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "out",
        environment={
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay),
            "BRAVE_SEARCH_API_KEY": "test-key",
        },
        search_override=search,
        fetch_page=_page,
        observed_at=NOW,
        results_per_query=10,
        max_pages=10,
        max_terms=1,
    )

    rows = json.loads((tmp_path / "out" / "all-discovered-candidates.json").read_text(encoding="utf-8"))
    assert report["raw_hit_count"] == 3
    assert report["page_request_count"] == 3
    assert report["verified_page_count"] == 3
    assert report["verified_opportunity_count"] == 1
    assert report["duplicate_verified_page_count"] == 2
    assert len(rows) == 1
    assert rows[0]["company_name"] == "Senna Mode"
    assert rows[0]["title"] == "Senna Mode inventory liquidation"
    assert rows[0]["metadata"]["verified_source_page_count"] == 3
    assert sorted(rows[0]["metadata"]["additional_verified_source_urls"]) == sorted(urls[1:])
    verified_urls = {
        item["source_url"]
        for item in rows[0]["evidence"]
        if item["verified"] is True
    }
    assert verified_urls == set(urls)


def test_promoted_core_keeps_independent_companies_separate(tmp_path):
    overlay = _overlay(tmp_path)
    hits = [
        SearchHit(
            title="Senna Mode clothing sale",
            url="https://www.sennamode.com/products/alpha",
            description="Klesbutikk avviklingssalg – stenge butikken",
            provider="Brave Search",
        ),
        SearchHit(
            title="Nord Stil clothing sale",
            url="https://www.nordstil.no/products/alpha",
            description="Klesbutikk avviklingssalg – stenge butikken",
            provider="Brave Search",
        ),
    ]

    def fetch(url: str) -> PublicPage:
        company = "Senna Mode" if "sennamode" in url else "Nord Stil"
        html = f"""
        <html><body>
          <div>BEDRIFTSDETALJER {company} drives av {company} AS.</div>
          <div>Klesbutikken selger klær, jakker og bukser.</div>
          <div>Avviklingssalg</div>
          <div>Vi må dessverre stenge butikken vår og selge ut vårt siste varelager.</div>
        </body></html>
        """
        return PublicPage(url, url, 200, "text/html", html)

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "out-independent",
        environment={
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay),
            "BRAVE_SEARCH_API_KEY": "test-key",
        },
        search_override=lambda _q: hits,
        fetch_page=fetch,
        observed_at=NOW,
        results_per_query=10,
        max_pages=10,
        max_terms=1,
    )

    rows = json.loads((tmp_path / "out-independent" / "all-discovered-candidates.json").read_text(encoding="utf-8"))
    assert report["verified_page_count"] == 2
    assert report["verified_opportunity_count"] == 2
    assert report["duplicate_verified_page_count"] == 0
    assert {row["company_name"] for row in rows} == {"Senna Mode", "Nord Stil"}
