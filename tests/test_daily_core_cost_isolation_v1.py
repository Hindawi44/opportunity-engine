from __future__ import annotations

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("daily_cost_isolation_subject", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_daily_builder_defers_model_driven_enrichment_but_keeps_discovery(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("OPPORTUNITY_ENGINE_TARGETED_ENRICHMENT", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-alias-test")
    monkeypatch.setenv("HUNT_FOLLOWUP_MAX_CASES", "2")

    assert module._apply_cost_isolation() is False
    assert "OPENAI_API_KEY" not in os.environ
    assert os.environ["BRAVE_SEARCH_API_KEY"] == "brave-test"
    assert os.environ["BRAVE_API_KEY"] == "brave-alias-test"
    assert os.environ["HUNT_FOLLOWUP_MAX_CASES"] == "0"


def test_manual_builder_strips_brave_credentials_without_explicit_override(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("OPPORTUNITY_ENGINE_TARGETED_ENRICHMENT", raising=False)
    monkeypatch.delenv("OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL", raising=False)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_ACTOR", "Hindawi44")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-alias-test")
    monkeypatch.setenv("HUNT_FOLLOWUP_MAX_CASES", "2")

    assert module._apply_cost_isolation() is False
    assert "OPENAI_API_KEY" not in os.environ
    assert "BRAVE_SEARCH_API_KEY" not in os.environ
    assert "BRAVE_API_KEY" not in os.environ
    assert os.environ["HUNT_FOLLOWUP_MAX_CASES"] == "0"
    assert module._manual_brave_cost_guard_active() is True


def test_manual_builder_preserves_brave_only_with_explicit_paid_override(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("OPPORTUNITY_ENGINE_TARGETED_ENRICHMENT", raising=False)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_ACTOR", "Hindawi44")
    monkeypatch.setenv("OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL", "true")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-alias-test")

    assert module._apply_cost_isolation() is False
    assert os.environ["BRAVE_SEARCH_API_KEY"] == "brave-test"
    assert os.environ["BRAVE_API_KEY"] == "brave-alias-test"
    assert module._manual_brave_cost_guard_active() is False


def test_targeted_stage_must_explicitly_opt_in(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL", raising=False)
    monkeypatch.setenv("OPPORTUNITY_ENGINE_TARGETED_ENRICHMENT", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test")
    monkeypatch.setenv("HUNT_FOLLOWUP_MAX_CASES", "2")

    assert module._apply_cost_isolation() is True
    assert os.environ["OPENAI_API_KEY"] == "openai-test"
    assert os.environ["BRAVE_SEARCH_API_KEY"] == "brave-test"
    assert os.environ["HUNT_FOLLOWUP_MAX_CASES"] == "2"


def test_builder_records_core_daily_vs_targeted_stage_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"stage": "TARGETED_ENRICHMENT" if targeted_enabled else "CORE_DAILY"' in text
    assert '"openai_hunt_deferred": not targeted_enabled' in text
    assert '"manual_brave_cost_guard_applied": manual_brave_guard' in text
    assert '"manual_brave_requests_allowed": not manual_brave_guard' in text
    assert '"daily_brave_discovery_preserved": not manual_brave_guard' in text
    assert '"commercial_analysis_stage": "SEPARATE_MANUAL_WORKFLOW"' in text
