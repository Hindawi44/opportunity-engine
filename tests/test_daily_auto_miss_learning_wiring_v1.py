from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    load_missed_opportunity_memory,
    save_missed_opportunity_memory,
)


INIT = Path("src/opportunity_engine/discovery/__init__.py")
HOOK = Path("src/opportunity_engine/discovery/daily_auto_miss_learning_cli_hook.py")
RESTORE_SCRIPT = Path("scripts/restore_previous_checkpoint_state.py")


def test_restore_phase_preserves_shadow_but_defers_new_learning_until_post_capture() -> None:
    script = RESTORE_SCRIPT.read_text(encoding="utf-8")

    shadow_extend = script.index("SHADOW_KEYWORD_OVERLAY_FILENAME")
    restore_call = script.index("restore_previous_checkpoint_databases(")
    assert shadow_extend < restore_call
    assert "shadow-keyword-overlay.json" in script
    assert "run_daily_learning_runtime(" not in script
    assert "DEFERRED_UNTIL_POST_CAPTURE" in script


def test_auto_learning_hook_runs_after_unified_capture_by_atexit_order() -> None:
    init = INIT.read_text(encoding="utf-8")

    auto_install = init.index("install_daily_auto_miss_learning_cli_hook()")
    river_install = init.index("install_unified_market_intelligence_river_cli_hook()")

    # atexit is LIFO: registering auto-learning before the river makes the river
    # capture/routing handler run first, then the learning consumer runs second.
    assert auto_install < river_install

    hook = HOOK.read_text(encoding="utf-8")
    assert "automatic-missed-opportunity-capture.json" in hook
    assert "run_daily_learning_runtime(" in hook
    assert 'learning_dir=root / "learning"' in hook
    assert 'report_path=output / REPORT_FILENAME' in hook
    assert "run_daily_auto_miss_learning_fail_closed(" in hook


def test_auto_learning_consumes_durable_miss_memory_without_manual_brave_cost(
    tmp_path: Path,
) -> None:
    from opportunity_engine.discovery.daily_auto_miss_learning_cli_hook import (
        run_daily_auto_miss_learning,
    )

    input_root = tmp_path / "multi-market-inputs"
    output_dir = tmp_path / "checkpoint"
    output_dir.mkdir(parents=True)
    (output_dir / "automatic-missed-opportunity-capture.json").write_text(
        json.dumps({"status": "SUCCESS", "new_case_count": 1}),
        encoding="utf-8",
    )
    (output_dir / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"schema_version": "test"}),
        encoding="utf-8",
    )

    case = MissedOpportunityCase(
        case_id="AUTO-QUERY-GAP-1",
        market_code="NO",
        discovered_by="AUTOMATIC_VERIFIED_GAP_TEST",
        observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company="Example AS",
        ground_truth_url="https://example.no/stock",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text="Sluttlager selges ved nedleggelse.",
        root_cause="QUERY_GAP",
        learning_status="DIAGNOSED",
    )
    memory_path = input_root / "learning" / "missed-opportunities.json"
    save_missed_opportunity_memory(memory_path, [case])

    report = run_daily_auto_miss_learning(
        output_dir,
        input_root=input_root,
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
    )

    # The repository may also contain curated real inbox cases (for example the
    # first Lene Interiør proof). The post-capture cycle must merge rather than
    # erase either source of memory.
    assert report["known_missed_opportunity_count"] >= 1
    persisted_ids = {item.case_id for item in load_missed_opportunity_memory(memory_path)}
    assert "AUTO-QUERY-GAP-1" in persisted_ids
    assert report["candidate_count"] >= 1
    assert report["learning_search_requests"] == 0
    assert report["search_status"] == "SKIPPED_COST_GUARD"
    assert report["automatic_query_activation"] is False
    assert report["promotion_gate_enforced"] is True
    assert (output_dir / "daily-learning-cycle.json").exists()
    assert (input_root / "learning" / "shadow-keyword-overlay.json").exists()
    assert (input_root / "learning" / "active-keyword-overlay.json").exists()
    assert (input_root / "learning" / "safe-learning-proof.json").exists()

    brief = json.loads(
        (output_dir / "domain-market-intelligence-brief.json").read_text(
            encoding="utf-8"
        )
    )
    summary = brief["daily_auto_miss_learning"]
    assert summary["known_missed_opportunity_count"] == report[
        "known_missed_opportunity_count"
    ]
    assert summary["automatic_query_activation"] is False
    assert summary["promotion_gate_enforced"] is True


def test_auto_learning_failure_is_structured_and_fail_closed(tmp_path: Path) -> None:
    from opportunity_engine.discovery.daily_auto_miss_learning_cli_hook import (
        run_daily_auto_miss_learning_fail_closed,
    )

    input_root = tmp_path / "multi-market-inputs"
    output_dir = tmp_path / "checkpoint"
    output_dir.mkdir(parents=True)
    (output_dir / "automatic-missed-opportunity-capture.json").write_text(
        json.dumps({"status": "SUCCESS", "new_case_count": 1}),
        encoding="utf-8",
    )
    (output_dir / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"schema_version": "test", "current_direct_opportunities": ["kept"]}),
        encoding="utf-8",
    )
    learning_dir = input_root / "learning"
    learning_dir.mkdir(parents=True)
    (learning_dir / "shadow-keyword-overlay.json").write_text(
        json.dumps({"schema_version": "unsupported", "markets": {}}),
        encoding="utf-8",
    )

    report = run_daily_auto_miss_learning_fail_closed(
        output_dir,
        input_root=input_root,
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
    )

    assert report["status"] == "FAILED"
    assert report["error_type"] == "ValueError"
    assert report["learning_search_requests"] == 0
    assert report["active_learned_term_count"] == 0
    assert report["automatic_query_activation"] is False
    assert report["promotion_gate_enforced"] is True
    assert report["automatic_purchase"] is False
    assert (output_dir / "daily-learning-cycle.json").exists()

    brief = json.loads(
        (output_dir / "domain-market-intelligence-brief.json").read_text(
            encoding="utf-8"
        )
    )
    assert brief["current_direct_opportunities"] == ["kept"]
    assert brief["daily_auto_miss_learning"]["status"] == "FAILED"
    assert brief["daily_auto_miss_learning"]["automatic_query_activation"] is False


def test_auto_learning_hook_skips_when_capture_stage_did_not_finish(tmp_path: Path) -> None:
    from opportunity_engine.discovery.daily_auto_miss_learning_cli_hook import (
        run_daily_auto_miss_learning,
    )

    output_dir = tmp_path / "checkpoint"
    output_dir.mkdir(parents=True)
    report = run_daily_auto_miss_learning(
        output_dir,
        input_root=tmp_path / "multi-market-inputs",
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
    )

    assert report["status"] == "SKIPPED_NO_CAPTURE_ARTIFACT"
    assert report["automatic_query_activation"] is False
    assert report["automatic_purchase"] is False
    assert not (output_dir / "daily-learning-cycle.json").exists()
