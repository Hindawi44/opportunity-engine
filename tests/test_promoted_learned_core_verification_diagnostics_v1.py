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
NOW = datetime(2026, 8, 22, 20, 45, tzinfo=timezone.utc)


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
        support_case_ids=("AUTO-MISS-NO-BAUHAUS",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )
    return select_promoted_query_overlay(
        build_learned_query_overlay([evaluation]),
        {("NO", TERM): "PROMOTED"},
    )


def test_promoted_core_reports_exact_reason_for_rejected_public_page(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(overlay_path, _active_overlay())
    url = "https://example.no/avviklingssalg"

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "out",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=lambda query: [
            SearchHit(
                title="Nordlys Handel avvikler virksomheten",
                url=url,
                description="Avviklingssalg på alle varer.",
                provider="Fake Brave",
            )
        ],
        fetch_page=lambda requested_url: PublicPage(
            requested_url=requested_url,
            final_url=requested_url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            html=(
                "<html><body><h1>Nordlys Handel avvikler virksomheten</h1>"
                "<p>Vi har avviklingssalg på alle varer denne uken.</p>"
                "</body></html>"
            ),
        ),
        observed_at=NOW,
        results_per_query=10,
        max_pages=10,
    )

    assert report["verified_opportunity_count"] == 0
    assert report["verification_attempt_count"] == 1
    assert report["verification_attempts"] == [
        {
            "term": TERM,
            "rank": 1,
            "title": "Nordlys Handel avvikler virksomheten",
            "requested_url": url,
            "final_url": url,
            "status_code": 200,
            "content_type": "text/html; charset=utf-8",
            "result": "REJECTED",
            "rejection_reasons": ["INVENTORY_LIQUIDATION_MISSING"],
            "closure_markers": ["avvikler"],
            "sale_terms": [TERM],
            "liquidation_markers": [],
            "company": "Nordlys Handel",
        }
    ]
