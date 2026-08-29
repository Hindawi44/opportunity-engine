from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed_core.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cost_isolation_diagnostics_subject", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openai_missing_key_status_is_labeled_as_intentional_cost_isolation(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("HUNT_FOLLOWUP_MAX_CASES", "0")
    report = {"status": "SKIPPED_NO_API_KEY", "api_request_count": 0}

    result = module._annotate_intentional_cost_isolation(
        report,
        expected_status="SKIPPED_NO_API_KEY",
    )

    assert result["status"] == "SKIPPED_NO_API_KEY"
    assert result["diagnostic_status"] == "SKIPPED_INTENTIONAL_COST_ISOLATION"
    assert result["skip_reason"] == "CORE_DAILY_COST_ISOLATION"
    assert result["credential_error"] is False


def test_brave_missing_key_status_is_labeled_as_intentional_cost_isolation(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("HUNT_FOLLOWUP_MAX_CASES", "0")
    report = {"status": "SKIPPED_NO_BRAVE_KEY", "search_request_count": 0}

    result = module._annotate_intentional_cost_isolation(
        report,
        expected_status="SKIPPED_NO_BRAVE_KEY",
    )

    assert result["status"] == "SKIPPED_NO_BRAVE_KEY"
    assert result["diagnostic_status"] == "SKIPPED_INTENTIONAL_COST_ISOLATION"
    assert result["skip_reason"] == "CORE_DAILY_COST_ISOLATION"
    assert result["credential_error"] is False


def test_real_missing_key_status_is_not_rewritten_without_cost_isolation(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("HUNT_FOLLOWUP_MAX_CASES", raising=False)
    report = {"status": "SKIPPED_NO_API_KEY", "api_request_count": 0}

    result = module._annotate_intentional_cost_isolation(
        report,
        expected_status="SKIPPED_NO_API_KEY",
    )

    assert "diagnostic_status" not in result
    assert "skip_reason" not in result
    assert "credential_error" not in result
