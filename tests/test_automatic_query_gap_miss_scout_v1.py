from __future__ import annotations

from datetime import datetime, timezone
import json

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.missed_opportunity_learning import load_missed_opportunity_memory


RITA_URL = (
    "https://www.vartoslo.no/anbefalt-bydel-sentrum-hille-melbye-arkitekter/"
    "butikken-legger-ned-etter-90-ar-store-planer-for-sentrumsbygarden/1252479"
)

RITA_HTML = """
<html><head><title>Butikken legger ned etter 90 år</title></head>
<body>
<h1>Butikken legger ned etter 90 år</h1>
<p>Klesbutikken Rita Korsettsalong i Storgata 9 stenger etter 90 år.</p>
<p>I vinduet kan forbigående nå lese ordene «Sluttsalg» og «Alt skal ut».</p>
<p>Rita Korsettsalong legges ned. Alle varer skal ut av butikken.</p>
<p>Siste åpningsdag blir 1. oktober.</p>
</body></html>
"""


def _checkpoint(*urls: str) -> dict:
    return {
        "deduplicated_opportunities": [
            {"canonical_url": url, "source_urls": [url]}
            for url in urls
        ]
    }


def _hit(url: str = RITA_URL) -> SearchHit:
    return SearchHit(
        title="Butikken legger ned etter 90 år: Store planer for sentrumsbygården",
        url=url,
        description="Klesbutikken Rita Korsettsalong stenger etter 90 år.",
        provider="Brave Search",
    )


def test_scout_query_does_not_leak_candidate_learning_terms() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import SCOUT_QUERY_NO

    folded = SCOUT_QUERY_NO.casefold()
    assert "sluttsalg" not in folded
    assert "avslutningssalg" not in folded
    assert "opphørssalg" not in folded
    assert "avviklingssalg" not in folded
    assert "tømmesalg" not in folded


def test_verified_independent_page_becomes_query_gap_when_term_is_absent_from_core_queries() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        discover_query_gap_misses,
    )

    calls: list[str] = []

    def search(query: str):
        calls.append(query)
        return [_hit()]

    def fetch_page(url: str):
        assert url == RITA_URL
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            html=RITA_HTML,
        )

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[
            '("opphørssalg" OR "avviklingssalg" OR konkurs) klær',
            '("restlager" OR "varelager") salg',
        ],
        search=search,
        fetch_page=fetch_page,
        observed_at=datetime(2026, 8, 22, 16, 30, tzinfo=timezone.utc),
    )

    assert calls and calls[0]
    assert outcome["search_request_count"] == 1
    assert outcome["page_request_count"] == 1
    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 1
    [case] = outcome["cases"]
    assert case.root_cause == "QUERY_GAP"
    assert case.trace.query_generated is False
    assert case.stock_proven is True
    assert case.ground_truth_url == RITA_URL
    assert case.discovered_by == "AUTOMATIC_INDEPENDENT_QUERY_GAP_SCOUT"
    assert case.opportunity_type == "VERIFIED_STORE_CLOSURE_INVENTORY_LIQUIDATION"
    assert "sluttsalg" in case.learning_evidence_text.casefold()
    assert outcome["cases_metadata"][0]["query_gap_term"] == "sluttsalg"
    assert outcome["cases_metadata"][0]["source_page_verified"] is True
    assert outcome["cases_metadata"][0]["search_hit_alone_is_ground_truth"] is False


def test_search_hit_without_verified_page_is_never_ground_truth() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        discover_query_gap_misses,
    )

    def fetch_page(url: str):
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html="<html><body>Rita Korsettsalong legges ned.</body></html>",
        )

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=[],
        search=lambda query: [_hit()],
        fetch_page=fetch_page,
    )

    assert outcome["verified_page_count"] == 0
    assert outcome["detected_miss_count"] == 0
    assert outcome["cases"] == []


def test_page_already_present_in_core_is_not_a_miss() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        discover_query_gap_misses,
    )

    outcome = discover_query_gap_misses(
        _checkpoint(RITA_URL),
        active_queries=[],
        search=lambda query: [_hit()],
        fetch_page=lambda url: PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=RITA_HTML,
        ),
    )

    assert outcome["page_request_count"] == 0
    assert outcome["detected_miss_count"] == 0
    assert outcome["core_already_knew_count"] == 1


def test_term_already_present_in_active_queries_is_not_labeled_query_gap() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        discover_query_gap_misses,
    )

    outcome = discover_query_gap_misses(
        _checkpoint(),
        active_queries=['("sluttsalg" OR "opphørssalg") butikk'],
        search=lambda query: [_hit()],
        fetch_page=lambda url: PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=RITA_HTML,
        ),
    )

    assert outcome["verified_page_count"] == 1
    assert outcome["detected_miss_count"] == 0
    assert outcome["no_new_query_term_count"] == 1


def test_manual_scout_cost_guard_makes_zero_network_requests(tmp_path) -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        write_automatic_query_gap_miss_scout,
    )

    output = tmp_path / "checkpoint"
    output.mkdir()
    (output / "multi-market-daily-checkpoint.json").write_text(
        json.dumps(_checkpoint()),
        encoding="utf-8",
    )
    calls = {"search": 0, "page": 0}

    def search(query: str):
        calls["search"] += 1
        return [_hit()]

    def fetch_page(url: str):
        calls["page"] += 1
        raise AssertionError("manual cost guard must block before page fetch")

    report = write_automatic_query_gap_miss_scout(
        output,
        input_root=tmp_path / "multi-market-inputs",
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
        search_override=search,
        page_fetcher=fetch_page,
    )

    assert report["status"] == "SKIPPED_COST_GUARD"
    assert report["search_request_count"] == 0
    assert report["page_request_count"] == 0
    assert report["automatic_query_activation"] is False
    assert report["automatic_purchase"] is False
    assert calls == {"search": 0, "page": 0}


def test_verified_query_gap_is_merged_into_durable_miss_memory(tmp_path) -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import (
        PublicPage,
        write_automatic_query_gap_miss_scout,
    )

    output = tmp_path / "checkpoint"
    output.mkdir()
    (output / "multi-market-daily-checkpoint.json").write_text(
        json.dumps(_checkpoint()),
        encoding="utf-8",
    )
    active_query_config = tmp_path / "queries.json"
    active_query_config.write_text(
        json.dumps({"queries": ['("opphørssalg" OR "avviklingssalg") butikk']}),
        encoding="utf-8",
    )

    report = write_automatic_query_gap_miss_scout(
        output,
        input_root=tmp_path / "multi-market-inputs",
        active_query_config=active_query_config,
        environment={"GITHUB_EVENT_NAME": "schedule", "BRAVE_SEARCH_API_KEY": "test"},
        search_override=lambda query: [_hit()],
        page_fetcher=lambda url: PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html=RITA_HTML,
        ),
        observed_at=datetime(2026, 8, 22, 16, 30, tzinfo=timezone.utc),
    )

    memory_path = tmp_path / "multi-market-inputs" / "learning" / "missed-opportunities.json"
    memory = load_missed_opportunity_memory(memory_path)
    assert report["status"] == "SUCCESS"
    assert report["new_case_count"] == 1
    assert len(memory) == 1
    assert memory[0].root_cause == "QUERY_GAP"
    assert memory[0].learning_status == "DIAGNOSED"
    assert "sluttsalg" in memory[0].learning_evidence_text.casefold()
