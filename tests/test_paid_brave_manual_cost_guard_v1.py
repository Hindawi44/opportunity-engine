from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from opportunity_engine.cost_guard import (
    AUTOMATED_CHECKPOINT_BOUNDED_SOURCE_BUDGETS,
    MANUAL_PAID_BRAVE_BLOCK_REASON,
    ensure_paid_brave_allowed,
    manual_paid_brave_block_reason,
)
from opportunity_engine.discovery.brave_market_signal_continuity import (
    collect_manifest_brave_market_signals,
)


ROOT = Path(__file__).resolve().parents[1]
AUTOMATED_CHECKPOINT_ENV = {
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_WORKFLOW": "Multi-Market Daily Operator Checkpoint",
    "GITHUB_JOB": "operator-read-only-checkpoint",
    "GITHUB_ACTOR": "github-actions[bot]",
    "BRAVE_SEARCH_API_KEY": "would-be-paid-key",
}


def test_manual_workflow_blocks_paid_brave_by_default() -> None:
    env = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "BRAVE_SEARCH_API_KEY": "would-be-paid-key",
    }

    assert manual_paid_brave_block_reason(env) == MANUAL_PAID_BRAVE_BLOCK_REASON
    with pytest.raises(RuntimeError, match=MANUAL_PAID_BRAVE_BLOCK_REASON):
        ensure_paid_brave_allowed(env)


def test_schedule_and_explicit_override_remain_available() -> None:
    assert manual_paid_brave_block_reason({"GITHUB_EVENT_NAME": "schedule"}) is None
    assert (
        manual_paid_brave_block_reason(
            {
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL": "true",
            }
        )
        is None
    )


def test_auto_checkpoint_allows_only_existing_bounded_direct_source_budgets() -> None:
    assert AUTOMATED_CHECKPOINT_BOUNDED_SOURCE_BUDGETS == {
        ("SE", "blinto"): 8,
        ("SE", "klaravik"): 8,
        ("SE", "psauction"): 8,
        ("DE", "sen-sen"): 6,
    }

    for (market, source), max_budget in AUTOMATED_CHECKPOINT_BOUNDED_SOURCE_BUDGETS.items():
        assert (
            manual_paid_brave_block_reason(
                AUTOMATED_CHECKPOINT_ENV,
                market=market,
                source=source,
                query_budget=max_budget,
            )
            is None
        )
        assert (
            manual_paid_brave_block_reason(
                AUTOMATED_CHECKPOINT_ENV,
                market=market,
                source=source,
                query_budget=max_budget + 1,
            )
            == MANUAL_PAID_BRAVE_BLOCK_REASON
        )


def test_auto_checkpoint_identity_is_not_a_global_brave_bypass() -> None:
    assert (
        manual_paid_brave_block_reason(AUTOMATED_CHECKPOINT_ENV)
        == MANUAL_PAID_BRAVE_BLOCK_REASON
    )
    assert (
        manual_paid_brave_block_reason(
            AUTOMATED_CHECKPOINT_ENV,
            market="SE",
            source="unknown-source",
            query_budget=1,
        )
        == MANUAL_PAID_BRAVE_BLOCK_REASON
    )


def test_manual_actor_stays_blocked_even_for_an_allowed_source_and_budget() -> None:
    env = {**AUTOMATED_CHECKPOINT_ENV, "GITHUB_ACTOR": "Hindawi44"}
    assert (
        manual_paid_brave_block_reason(
            env,
            market="SE",
            source="blinto",
            query_budget=8,
        )
        == MANUAL_PAID_BRAVE_BLOCK_REASON
    )


def test_wrong_workflow_or_job_stays_blocked_for_bot_actor() -> None:
    for env in (
        {**AUTOMATED_CHECKPOINT_ENV, "GITHUB_WORKFLOW": "Other Workflow"},
        {**AUTOMATED_CHECKPOINT_ENV, "GITHUB_JOB": "other-job"},
    ):
        assert (
            manual_paid_brave_block_reason(
                env,
                market="SE",
                source="blinto",
                query_budget=8,
            )
            == MANUAL_PAID_BRAVE_BLOCK_REASON
        )


def test_manual_radar_guard_makes_zero_provider_requests(tmp_path: Path) -> None:
    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "artifact_dir": "artifacts/no",
            },
            {
                "market_code": "SE",
                "artifact_dir": "artifacts/se",
            },
            {
                "market_code": "DE",
                "artifact_dir": "artifacts/de",
            },
        ]
    }
    provider_calls: list[tuple] = []

    def provider_factory(*args):
        provider_calls.append(args)
        raise AssertionError("provider must not be created under the manual cost guard")

    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        observed_at=datetime(2026, 8, 17, 7, 0, tzinfo=timezone.utc),
        environment={
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "BRAVE_SEARCH_API_KEY": "would-be-paid-key",
        },
        provider_factory=provider_factory,
    )

    assert provider_calls == []
    assert report["requests_made"] == 0
    assert report["signal_count"] == 0
    assert report["status_counts"] == {"SKIPPED_COST_GUARD": 3}
    assert report["cost_guard"]["paid_brave_requests_blocked"] is True
    assert all(
        source["block_reason"] == MANUAL_PAID_BRAVE_BLOCK_REASON
        for source in report["sources"]
    )


def test_auto_checkpoint_does_not_unlock_brave_radar_without_source_scope(
    tmp_path: Path,
) -> None:
    manifest = {
        "sources": [
            {"market_code": "NO", "artifact_dir": "artifacts/no"},
            {"market_code": "SE", "artifact_dir": "artifacts/se"},
            {"market_code": "DE", "artifact_dir": "artifacts/de"},
        ]
    }
    provider_calls: list[tuple] = []

    def provider_factory(*args):
        provider_calls.append(args)
        raise AssertionError("radar must remain blocked in automated checkpoint")

    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        observed_at=datetime(2026, 8, 25, 11, 0, tzinfo=timezone.utc),
        environment=AUTOMATED_CHECKPOINT_ENV,
        provider_factory=provider_factory,
    )

    assert provider_calls == []
    assert report["requests_made"] == 0
    assert report["status_counts"] == {"SKIPPED_COST_GUARD": 3}


def test_market_runner_passes_bounded_scope_before_paid_source_selection() -> None:
    script = (ROOT / "scripts/run_market_clothing_inventory_discovery.py").read_text(
        encoding="utf-8"
    )

    guard_index = script.index("ensure_paid_brave_allowed(")
    runner_index = script.index("runner = select_market_runner")
    assert guard_index < runner_index
    assert "source=paid_scope.source" in script
    assert "query_budget=paid_scope.query_budget" in script
