from __future__ import annotations

from datetime import datetime, timezone
import json
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
from scripts.restore_previous_checkpoint_state import _prepare_previous_runtime_overlay


NOW = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
TERM = "avviklingssalg"
HOLDOUTS = (
    "HOLDOUT-NO-SENZE-OF-JOY",
    "HOLDOUT-NO-TOFF-OG-LITEN-STEINKJER",
    "HOLDOUT-NO-GAULA-NATURSENTER",
)


def _shadow_overlay():
    evaluation = KeywordEvaluationResult(
        term=TERM,
        market_code="NO",
        status="PROVEN",
        recovered_case_ids=HOLDOUTS,
        raw_hit_count=9,
        verified_relevant_count=3,
        precision=1 / 3,
        min_recovered_cases=1,
        min_precision=0.20,
        automatic_activation=False,
        support_case_ids=("AUTO-MISS-NO-BAUHAUS",),
        evaluation_scope="HOLDOUT_TRANSFER",
    )
    return build_learned_query_overlay([evaluation])


def test_restore_applies_current_promotion_to_restored_shadow_before_discovery(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    shadow_path = input_root / "learning" / "shadow-keyword-overlay.json"
    save_learned_query_overlay(shadow_path, _shadow_overlay())
    promotion_path = tmp_path / "query-promotions.json"
    promotion_path.write_text(
        json.dumps(
            {
                "schema_version": "query-promotion-gate-1.0",
                "decisions": [
                    {
                        "market_code": "NO",
                        "term": TERM,
                        "status": "PROMOTED",
                        "reason": "Repeated independent transfer proof passed.",
                        "approved_at": "2026-08-22T19:45:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runtime_overlay = tmp_path / "runtime" / "active-keyword-overlay.json"

    _prepare_previous_runtime_overlay(
        input_root,
        runtime_overlay,
        promotion_config_path=promotion_path,
    )

    payload = json.loads(runtime_overlay.read_text(encoding="utf-8"))
    row = payload["markets"]["NO"][0]
    assert row["term"] == TERM
    assert row["promotion_status"] == "PROMOTED"
    assert row["activation_source"] == "EXPLICIT_PROMOTION"
    assert row["independent_transfer_case_count"] == 3
    assert payload["automatic_query_activation"] is False


def test_scheduled_promoted_core_search_creates_verified_direct_candidate(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    active = select_promoted_query_overlay(
        _shadow_overlay(),
        {("NO", TERM): "PROMOTED"},
    )
    save_learned_query_overlay(overlay_path, active)
    queries: list[str] = []

    def search(query: str):
        queries.append(query)
        return [
            SearchHit(
                title="BAUHAUS Norge avvikler virksomheten",
                url="https://www.bauhaus.no/bauhaus-norge-informasjon",
                description="Avviklingssalg. Hele lagerbeholdningen skal ut.",
                provider="Fake Brave",
            )
        ]

    def fetch_page(url: str):
        return PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            html=(
                "<html><body><h1>BAUHAUS Norge avvikler virksomheten</h1>"
                "<p>Vi avvikler virksomheten og har avviklingssalg. "
                "Hele lagerbeholdningen skal ut.</p></body></html>"
            ),
        )

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "source",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=search,
        fetch_page=fetch_page,
        observed_at=NOW,
        results_per_query=10,
        max_pages=3,
    )

    assert queries == ['"avviklingssalg"']
    assert report["status"] == "SUCCESS"
    assert report["request_count"] == 1
    assert report["verified_opportunity_count"] == 1
    assert report["applied_terms"] == [TERM]
    assert report["promotion_gate_enforced"] is True
    assert report["automatic_query_activation"] is False

    candidates = json.loads(
        (tmp_path / "source" / "all-discovered-candidates.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(candidates) == 1
    record = candidates[0]
    assert record["market_code"] == "NO"
    assert record["company_name"] == "BAUHAUS Norge"
    assert record["scenario"] == "STOCK_LIQUIDATION"
    assert record["workflow_status"] == "REQUIRES_VERIFICATION"
    assert record["evaluation_status"] == "REQUIRES_VERIFICATION"
    assert record["verified"] is True
    assert record["analysis_eligible"] is False
    assert record["metadata"]["learned_term"] == TERM
    assert record["metadata"]["source_page_verified"] is True
    assert record["metadata"]["inventory_liquidation_verified"] is True

    unified = json.loads(
        (tmp_path / "source" / "unified-opportunity-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert unified["record_count"] == 1
    assert unified["records"][0]["opportunity_id"] == record["opportunity_id"]


def test_no_promoted_terms_makes_zero_search_requests(tmp_path: Path) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(
        overlay_path,
        {
            "schema_version": "learned-query-overlay-1.0",
            "markets": {},
            "max_terms_per_market": 5,
            "active_term_count": 0,
            "automatic_query_activation": False,
            "promotion_gate_enforced": True,
            "activation_source": "EXPLICIT_PROMOTION",
            "automatic_financial_action": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        },
    )
    calls: list[str] = []

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "source",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=lambda query: calls.append(query) or [],
        fetch_page=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        observed_at=NOW,
    )

    assert calls == []
    assert report["status"] == "VALID_ZERO"
    assert report["request_count"] == 0
    assert report["verified_opportunity_count"] == 0
