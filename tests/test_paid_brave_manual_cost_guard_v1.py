from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from opportunity_engine.cost_guard import (
    MANUAL_PAID_BRAVE_BLOCK_REASON,
    ensure_paid_brave_allowed,
    manual_paid_brave_block_reason,
)
from opportunity_engine.discovery.brave_market_signal_continuity import (
    collect_manifest_brave_market_signals,
)


ROOT = Path(__file__).resolve().parents[1]


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


def test_market_runner_is_guarded_before_paid_source_selection() -> None:
    script = (ROOT / "scripts/run_market_clothing_inventory_discovery.py").read_text(
        encoding="utf-8"
    )

    guard_index = script.index("ensure_paid_brave_allowed()")
    runner_index = script.index("runner = select_market_runner")
    assert guard_index < runner_index
