from __future__ import annotations

import json
from pathlib import Path

import pytest

import opportunity_engine.cost_guard as cost_guard
import opportunity_engine.discovery.brave_search as brave_search


def _manual_test_env(monkeypatch, tmp_path: Path, *, attempt: str = "1") -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_WORKFLOW", cost_guard.AUTOMATED_CHECKPOINT_WORKFLOW)
    monkeypatch.setenv("GITHUB_JOB", cost_guard.AUTOMATED_CHECKPOINT_JOB)
    monkeypatch.setenv("GITHUB_ACTOR", "Hindawi44")
    monkeypatch.setenv("GITHUB_REF_NAME", cost_guard.MANUAL_PAID_BRAVE_TEST_BRANCH)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", attempt)
    monkeypatch.setenv("GITHUB_RUN_ID", "123456")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv(cost_guard.MANUAL_PAID_BRAVE_OVERRIDE, raising=False)


def _success_transport_payload() -> bytes:
    return json.dumps(
        {
            "web": {
                "results": [
                    {
                        "title": "Bulk clothing liquidation lot",
                        "url": "https://example.com/lot-1",
                        "description": "Commercial stock lot",
                    }
                ]
            }
        }
    ).encode("utf-8")


def test_dedicated_first_attempt_branch_is_paid_but_bounded(monkeypatch, tmp_path: Path) -> None:
    _manual_test_env(monkeypatch, tmp_path)

    assert cost_guard.manual_paid_brave_block_reason() is None
    budget = cost_guard.manual_paid_brave_incremental_budget()
    assert budget is not None
    assert budget["max_requests"] == 2000
    assert budget["observed_unit_cost_usd"] == 0.005
    assert budget["max_incremental_cost_usd"] == 10.0


def test_dedicated_branch_rerun_attempt_is_not_authorized(monkeypatch, tmp_path: Path) -> None:
    _manual_test_env(monkeypatch, tmp_path, attempt="2")

    assert (
        cost_guard.manual_paid_brave_block_reason()
        == cost_guard.MANUAL_PAID_BRAVE_BLOCK_REASON
    )
    assert cost_guard.manual_paid_brave_incremental_budget() is None


def test_manual_budget_stops_transport_at_shared_request_ceiling(monkeypatch, tmp_path: Path) -> None:
    _manual_test_env(monkeypatch, tmp_path)
    monkeypatch.setattr(cost_guard, "MANUAL_PAID_BRAVE_TEST_MAX_REQUESTS", 2)
    calls = {"count": 0}

    def transport(request, timeout):
        calls["count"] += 1
        return _success_transport_payload()

    brave_search._reset_usage_limit_circuit_for_tests()
    monkeypatch.setattr(brave_search, "_default_transport", transport)
    try:
        first = brave_search.BraveSearchProvider("secret", max_retries=0)
        second = brave_search.BraveSearchProvider("secret", max_retries=0)
        third = brave_search.BraveSearchProvider("secret", max_retries=0)

        assert len(first.search("clothing liquidation")) == 1
        assert len(second.search("warehouse clothing stock")) == 1
        with pytest.raises(
            RuntimeError,
            match=brave_search._MANUAL_BUDGET_EXHAUSTED,
        ):
            third.search("auction clothing inventory")

        assert calls["count"] == 2
        state = json.loads(
            (tmp_path / brave_search._MANUAL_BUDGET_STATE_FILENAME).read_text(
                encoding="utf-8"
            )
        )
        assert state["reserved_requests"] == 2
        assert state["remaining_requests"] == 0
        assert state["estimated_reserved_cost_usd"] == 0.01
        assert state["fail_closed"] is True
    finally:
        brave_search._reset_usage_limit_circuit_for_tests()


def test_corrupt_budget_state_fails_closed_before_network(monkeypatch, tmp_path: Path) -> None:
    _manual_test_env(monkeypatch, tmp_path)
    state_path = tmp_path / brave_search._MANUAL_BUDGET_STATE_FILENAME
    state_path.write_text("not-json", encoding="utf-8")
    calls = {"count": 0}

    def transport(request, timeout):
        calls["count"] += 1
        return _success_transport_payload()

    brave_search._reset_usage_limit_circuit_for_tests()
    monkeypatch.setattr(brave_search, "_default_transport", transport)
    try:
        provider = brave_search.BraveSearchProvider("secret", max_retries=0)
        with pytest.raises(
            RuntimeError,
            match=brave_search._MANUAL_BUDGET_STATE_INVALID,
        ):
            provider.search("clothing liquidation")
        assert calls["count"] == 0
    finally:
        brave_search._reset_usage_limit_circuit_for_tests()


def test_explicit_manual_override_uses_same_fixed_budget(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv(cost_guard.MANUAL_PAID_BRAVE_OVERRIDE, "true")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    assert cost_guard.manual_paid_brave_block_reason() is None
    budget = cost_guard.manual_paid_brave_incremental_budget()
    assert budget is not None
    assert budget["max_incremental_cost_usd"] == 10.0
