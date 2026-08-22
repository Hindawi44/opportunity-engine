from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.automatic_query_gap_miss_scout import PublicPage
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    save_learned_query_overlay,
)
from opportunity_engine.learning_promotion_gate import select_promoted_query_overlay
from opportunity_engine.promoted_learned_core_discovery import (
    collect_promoted_learned_core_opportunities,
)


TERM = "avviklingssalg"
NOW = datetime(2026, 8, 22, 20, 30, tzinfo=timezone.utc)


def _active_overlay():
    evaluation = KeywordEvaluationResult(
        term=TERM,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=(
            "HOLDOUT-NO-SENZE-OF-JOY",
            "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER",
            "HOLDOUT-NO-GAULA-NATURSENTER",
        ),
        raw_hit_count=9,
        verified_relevant_count=3,
        precision=1 / 3,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
        support_case_ids=("auto-query-gap:no:a1d0426721ee47e868026b31",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )
    shadow = build_learned_query_overlay([evaluation])
    return select_promoted_query_overlay(
        shadow,
        {("NO", TERM): "PROMOTED"},
    )


def test_promoted_core_can_verify_late_ranked_result_within_ten_hit_window(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(overlay_path, _active_overlay())

    hits = [
        SearchHit(
            title=f"Noise {rank}",
            url=f"https://example.no/noise-{rank}",
            description="Avviklingssalg nevnt uten dokumentert nedleggelse.",
            provider="Fake Brave",
        )
        for rank in range(1, 6)
    ]
    hits.append(
        SearchHit(
            title="Gaula Natursenter avvikler virksomheten",
            url="https://gaula.example.no/avviklingssalg",
            description="Avviklingssalg. Hele lagerbeholdningen skal ut.",
            provider="Fake Brave",
        )
    )

    def fetch_page(url: str) -> PublicPage:
        if url.endswith("/avviklingssalg"):
            html = (
                "<html><body><h1>Gaula Natursenter avvikler virksomheten</h1>"
                "<p>Gaula Natursenter avvikler virksomheten. Avviklingssalg. "
                "Hele lagerbeholdningen skal ut.</p></body></html>"
            )
        else:
            html = "<html><body><p>Vanlig kampanje.</p></body></html>"
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            html=html,
        )

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "out",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=lambda query: hits,
        fetch_page=fetch_page,
        observed_at=NOW,
        results_per_query=10,
        max_pages=10,
    )

    assert report["request_count"] == 1
    assert report["raw_hit_count"] == 6
    assert report["page_request_count"] == 6
    assert report["verified_opportunity_count"] == 1
