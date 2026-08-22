from __future__ import annotations

from datetime import datetime, timezone
import json

from opportunity_engine.automatic_query_gap_miss_scout import PublicPage, _extract_company
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.promoted_learned_core_discovery import collect_promoted_learned_core_opportunities


def _overlay(tmp_path):
    path = tmp_path / "active-keyword-overlay.json"
    path.write_text(
        json.dumps(
            {
                "promotion_gate_enforced": True,
                "automatic_query_activation": False,
                "markets": {
                    "NO": [
                        {
                            "term": "avviklingssalg",
                            "source_verdict": "PROVEN",
                            "promotion_status": "PROMOTED",
                            "activation_source": "EXPLICIT_PROMOTION",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _page(url: str) -> PublicPage:
    html = """
    <html><body>
      <div>Stengt BEDRIFTSDETALJER BEDRIFTSDETALJER Senna Mode drives av Senna Mode B.V.</div>
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


def test_extract_company_ignores_repeated_template_noise_before_drives_av():
    text = (
        "Stengt BEDRIFTSDETALJER BEDRIFTSDETALJER "
        "Senna Mode drives av Senna Mode B.V."
    )
    assert _extract_company(text) == "Senna Mode"


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
                description="Avviklingssalg – stenge butikken",
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
        observed_at=datetime(2026, 8, 22, 21, 30, tzinfo=timezone.utc),
        results_per_query=10,
        max_pages=10,
        max_terms=1,
    )

    rows = json.loads((tmp_path / "out" / "all-discovered-candidates.json").read_text(encoding="utf-8"))
    assert report["raw_hit_count"] == 3
    assert report["page_request_count"] == 3
    assert report["verified_opportunity_count"] == 1
    assert len(rows) == 1
    assert rows[0]["company_name"] == "Senna Mode"
    assert rows[0]["metadata"]["verified_source_page_count"] == 3
    assert sorted(rows[0]["metadata"]["additional_verified_source_urls"]) == sorted(urls[1:])


def test_promoted_core_keeps_independent_companies_separate(tmp_path):
    overlay = _overlay(tmp_path)
    hits = [
        SearchHit(
            title="Senna Mode sale",
            url="https://www.sennamode.com/products/alpha",
            description="Avviklingssalg – stenge butikken",
            provider="Brave Search",
        ),
        SearchHit(
            title="Nord Stil sale",
            url="https://www.nordstil.no/products/alpha",
            description="Avviklingssalg – stenge butikken",
            provider="Brave Search",
        ),
    ]

    def fetch(url: str) -> PublicPage:
        company = "Senna Mode" if "sennamode" in url else "Nord Stil"
        html = f"""
        <html><body>
          <div>BEDRIFTSDETALJER {company} drives av {company} AS.</div>
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
        observed_at=datetime(2026, 8, 22, 21, 30, tzinfo=timezone.utc),
        results_per_query=10,
        max_pages=10,
        max_terms=1,
    )

    rows = json.loads((tmp_path / "out-independent" / "all-discovered-candidates.json").read_text(encoding="utf-8"))
    assert report["verified_opportunity_count"] == 2
    assert {row["company_name"] for row in rows} == {"Senna Mode", "Nord Stil"}
