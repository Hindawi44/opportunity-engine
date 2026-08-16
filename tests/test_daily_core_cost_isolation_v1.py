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
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-alias-test")
    monkeypatch.setenv("HUNT_FOLLOWUP_MAX_CASES", "2")

    assert module._apply_cost_isolation() is False
    assert "OPENAI_API_KEY" not in os.environ
    assert os.environ["BRAVE_SEARCH_API_KEY"] == "brave-test"
    assert os.environ["BRAVE_API_KEY"] == "brave-alias-test"
    assert os.environ["HUNT_FOLLOWUP_MAX_CASES"] == "0"


def test_targeted_stage_must_explicitly_opt_in(monkeypatch) -> None:
    module = _load_module()
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
    assert '"targeted_brave_followup_deferred": not targeted_enabled' in text
    assert '"daily_brave_discovery_preserved": True' in text
    assert '"commercial_analysis_stage": "SEPARATE_MANUAL_WORKFLOW"' in text
