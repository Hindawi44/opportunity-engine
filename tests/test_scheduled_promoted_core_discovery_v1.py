from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.automatic_query_gap_miss_scout import PublicPage
from opportunity_engine.discovery.brave_market_signal_continuity import (
    collect_manifest_brave_market_signals,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learned_query_overlay import (
    build_learned_query_overlay,
    save_learned_query_overlay,
)
from opportunity_engine.learning_promotion_gate import select_promoted_query_overlay
import opportunity_engine.promoted_learned_checkpoint_bridge as bridge_module
from opportunity_engine.promoted_learned_checkpoint_bridge import (
    merge_promoted_learning_into_norway_cross_source,
)
from opportunity_engine.promoted_learned_core_discovery import (
    collect_promoted_learned_core_opportunities,
)
from scripts.restore_previous_checkpoint_state import (
    DEFAULT_SHADOW_BOOTSTRAP_PATH,
    _prepare_previous_runtime_overlay,
)


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


def _active_overlay():
    return select_promoted_query_overlay(
        _shadow_overlay(),
        {("NO", TERM): "PROMOTED"},
    )


def _promotion_config(path: Path) -> Path:
    path.write_text(
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
    return path


def _fake_page(url: str) -> PublicPage:
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


def test_restore_applies_current_promotion_to_restored_shadow_before_discovery(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    shadow_path = input_root / "learning" / "shadow-keyword-overlay.json"
    save_learned_query_overlay(shadow_path, _shadow_overlay())
    promotion_path = _promotion_config(tmp_path / "query-promotions.json")
    runtime_overlay = tmp_path / "runtime" / "active-keyword-overlay.json"

    _prepare_previous_runtime_overlay(
        input_root,
        runtime_overlay,
        promotion_config_path=promotion_path,
        bootstrap_shadow_path=tmp_path / "missing-bootstrap.json",
    )

    payload = json.loads(runtime_overlay.read_text(encoding="utf-8"))
    row = payload["markets"]["NO"][0]
    assert row["term"] == TERM
    assert row["promotion_status"] == "PROMOTED"
    assert row["activation_source"] == "EXPLICIT_PROMOTION"
    assert row["independent_transfer_case_count"] == 3
    assert payload["automatic_query_activation"] is False


def test_repository_v15c_bootstrap_activates_without_previous_shadow(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    runtime_overlay = tmp_path / "runtime" / "active-keyword-overlay.json"
    promotion_path = _promotion_config(tmp_path / "query-promotions.json")

    _prepare_previous_runtime_overlay(
        input_root,
        runtime_overlay,
        promotion_config_path=promotion_path,
        bootstrap_shadow_path=DEFAULT_SHADOW_BOOTSTRAP_PATH,
    )

    active = json.loads(runtime_overlay.read_text(encoding="utf-8"))
    row = active["markets"]["NO"][0]
    assert row["term"] == TERM
    assert row["transfer_validation_case_ids"] == sorted(HOLDOUTS)
    assert row["independent_transfer_case_count"] == 3
    assert row["promotion_status"] == "PROMOTED"
    assert row["proof_provenance"]["live_proof"] == "V15C"
    assert row["proof_provenance"]["workflow_run_id"] == 32593694641

    durable_shadow = json.loads(
        (input_root / "learning" / "shadow-keyword-overlay.json").read_text(
            encoding="utf-8"
        )
    )
    assert durable_shadow["markets"]["NO"][0]["term"] == TERM
    assert durable_shadow["automatic_query_activation"] is False


def test_scheduled_promoted_core_search_creates_verified_direct_candidate(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(overlay_path, _active_overlay())
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

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "source",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=search,
        fetch_page=_fake_page,
        observed_at=NOW,
        results_per_query=10,
        max_pages=3,
    )

    assert queries == [f'"{TERM}" "stenge butikken"']
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
    assert record["top5_eligible"] is False
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


def test_search_hit_without_exact_page_proof_never_becomes_opportunity(
    tmp_path: Path,
) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(overlay_path, _active_overlay())

    report = collect_promoted_learned_core_opportunities(
        tmp_path / "source",
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=lambda query: [
            SearchHit(
                title="Stor avviklingssalg",
                url="https://example.no/no-proof",
                description="Mange varer til salgs",
                provider="Fake Brave",
            )
        ],
        fetch_page=lambda url: PublicPage(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html="<html><body><h1>Vanlig kampanje</h1><p>Tilbud denne uken.</p></body></html>",
        ),
        observed_at=NOW,
    )

    assert report["request_count"] == 1
    assert report["verified_opportunity_count"] == 0
    assert json.loads(
        (tmp_path / "source" / "all-discovered-candidates.json").read_text(
            encoding="utf-8"
        )
    ) == []


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


def test_verified_learned_record_merges_into_existing_norway_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    overlay_path = tmp_path / "active-keyword-overlay.json"
    save_learned_query_overlay(overlay_path, _active_overlay())
    learned_dir = tmp_path / "no-learned-core"
    collect_promoted_learned_core_opportunities(
        learned_dir,
        environment={
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        search_override=lambda query: [
            SearchHit(
                title="BAUHAUS Norge avvikler virksomheten",
                url="https://www.bauhaus.no/bauhaus-norge-informasjon",
                description="Avviklingssalg. Hele lagerbeholdningen skal ut.",
                provider="Fake Brave",
            )
        ],
        fetch_page=_fake_page,
        observed_at=NOW,
    )

    cross = tmp_path / "no-cross-source"
    cross.mkdir()
    (cross / "all-discovered-candidates.json").write_text("[]", encoding="utf-8")
    (cross / "unified-opportunity-report.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "generated_at": NOW.isoformat().replace("+00:00", "Z"),
                "market_code": "NO",
                "currency": "NOK",
                "record_count": 0,
                "records": [],
                "conversion_error_count": 0,
                "conversion_errors": [],
            }
        ),
        encoding="utf-8",
    )
    (cross / "search-run-report.json").write_text(
        json.dumps(
            {
                "schema_version": "checkpoint-cross-source-no-1.0",
                "status": "PASS",
                "discovered_at": NOW.isoformat(),
                "market_code": "NO",
                "currency": "NOK",
                "record_count": 0,
                "currency_conversion_performed": False,
            }
        ),
        encoding="utf-8",
    )

    persisted: list[Path] = []

    def fake_persist(report_path, output_dir, **kwargs):
        persisted.append(Path(report_path))
        return ({"status": "SUCCESS"}, Path(output_dir) / "unified-persistence-summary.json")

    monkeypatch.setattr(
        bridge_module,
        "persist_unified_report_with_artifacts",
        fake_persist,
    )

    result = merge_promoted_learning_into_norway_cross_source(learned_dir, cross)

    assert result["status"] == "SUCCESS"
    assert result["merged_record_count"] == 1
    assert persisted == [cross / "unified-opportunity-report.json"]
    candidates = json.loads(
        (cross / "all-discovered-candidates.json").read_text(encoding="utf-8")
    )
    assert len(candidates) == 1
    assert candidates[0]["learned_term"] == TERM
    assert candidates[0]["source_page_verified"] is True
    assert candidates[0]["source_urls"] == [
        "https://www.bauhaus.no/bauhaus-norge-informasjon"
    ]
    unified = json.loads(
        (cross / "unified-opportunity-report.json").read_text(encoding="utf-8")
    )
    assert unified["record_count"] == 1
    assert unified["records"][0]["metadata"]["learned_term"] == TERM
    source_report = json.loads(
        (cross / "search-run-report.json").read_text(encoding="utf-8")
    )
    assert source_report["promoted_learned_core_merged_count"] == 1


def test_precheckpoint_request_displaces_one_no_radar_request(tmp_path: Path) -> None:
    overlay_path = tmp_path / "learning" / "active-keyword-overlay.json"
    save_learned_query_overlay(overlay_path, _active_overlay())
    pre_report = (
        tmp_path
        / "artifacts"
        / "multi-market-inputs"
        / "no-learned-core"
        / "search-run-report.json"
    )
    pre_report.parent.mkdir(parents=True, exist_ok=True)
    pre_report.write_text(
        json.dumps({"request_count": 1, "applied_terms": [TERM]}),
        encoding="utf-8",
    )
    manifest = {
        "sources": [
            {"market_code": "NO", "artifact_dir": "no"},
            {"market_code": "SE", "artifact_dir": "se"},
            {"market_code": "DE", "artifact_dir": "de"},
        ]
    }
    calls: list[tuple[str, str]] = []

    class Provider:
        name = "Fake Brave"

        def __init__(self, market: str):
            self.market = market

        def search(self, query: str, *, count: int = 10):
            calls.append((self.market, query))
            return []

    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        observed_at=NOW,
        environment={
            "GITHUB_EVENT_NAME": "schedule",
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        provider_factory=lambda market, api_key, freshness: Provider(market),
        queries_per_market=2,
        results_per_query=10,
    )

    assert len(calls) == 5
    assert sum(1 for market, _ in calls if market == "NO") == 1
    learned = report["learned_query_overlay"]
    assert learned["precheckpoint_learned_request_count"] == 1
    assert learned["radar_requests_displaced"] == 1
    assert learned["radar_request_count_after_displacement"] == 5
    assert learned["combined_learned_plus_radar_request_count"] == 6
    assert learned["baseline_radar_request_budget"] == 6
    assert learned["combined_request_budget_unchanged"] is True
    assert learned["extra_search_requests"] == 0


def test_discovery_package_installs_synchronous_scheduled_core_hook() -> None:
    text = Path("src/opportunity_engine/discovery/__init__.py").read_text(encoding="utf-8")
    hook = Path(
        "src/opportunity_engine/discovery/scheduled_promoted_core_cli_hook.py"
    ).read_text(encoding="utf-8")

    assert "install_scheduled_promoted_core_cli_hook()" in text
    assert 'Path(sys.argv[0]).name != "run_multi_market_daily_operator_checkpoint.py"' in hook
    assert "collect_promoted_learned_core_opportunities(" in hook
    assert "merge_promoted_learning_into_norway_cross_source(" in hook
