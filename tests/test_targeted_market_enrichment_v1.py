from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_targeted_market_enrichment.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("targeted_market_enrichment_subject", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _brief(*, with_signal: bool) -> dict:
    signals = []
    if with_signal:
        signals.append(
            {
                "signal_id": "signal:de:example-fashion",
                "signal_type": "INSOLVENCY_OR_LIQUIDATION",
                "source_country": "DE",
                "source": "Official insolvency source",
                "source_url": "https://example.test/case",
                "title": "Example Fashion GmbH Insolvenz",
                "company_name": "Example Fashion GmbH",
                "location": "Hamburg",
                "confidence": 0.9,
                "status": "WATCH",
                "metadata": {"signal_only": True},
            }
        )
    return {
        "generated_at": "2026-08-16T20:00:00Z",
        "new_signals_today": signals,
        "changed_signals_since_previous_checkpoint": [],
        "early_signals_to_watch": signals,
        "selected_human_action": {"action": "NO_IMMEDIATE_ACTION"},
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_gate_skips_without_eligible_hunt_signals_and_uses_no_paid_api() -> None:
    module = _load_module()
    gate = module.build_targeted_enrichment_gate(_brief(with_signal=False))

    assert gate["status"] == "SKIPPED_NO_ELIGIBLE_HUNT_SIGNALS"
    assert gate["should_run_targeted_enrichment"] is False
    assert gate["eligible_signal_count"] == 0
    assert gate["gate_uses_paid_api"] is False
    assert gate["automatic_purchase"] is False


def test_gate_runs_only_when_openai_hunt_selector_finds_real_eligible_signal() -> None:
    module = _load_module()
    gate = module.build_targeted_enrichment_gate(_brief(with_signal=True))

    assert gate["status"] == "RUN_TARGETED_ENRICHMENT"
    assert gate["should_run_targeted_enrichment"] is True
    assert gate["eligible_signal_count"] == 1
    assert gate["eligible_signal_ids"] == ["signal:de:example-fashion"]
    assert gate["gate_selector"] == "OPENAI_HUNT_SELECT_HUNT_SIGNALS"


def test_zero_signal_run_writes_only_gate_artifacts(tmp_path: Path) -> None:
    module = _load_module()
    result = module.run_targeted_enrichment(
        _brief(with_signal=False),
        output_dir=tmp_path,
        environment={"OPENAI_API_KEY": "must-not-be-used", "BRAVE_SEARCH_API_KEY": "must-not-be-used"},
    )

    assert result["status"] == "SKIPPED_NO_ELIGIBLE_HUNT_SIGNALS"
    assert (tmp_path / "targeted-enrichment-gate.json").exists()
    assert (tmp_path / "targeted-enrichment-gate.txt").exists()
    assert not (tmp_path / "openai-hunt-case-enrichment.json").exists()
    assert not (tmp_path / "hunt-case-targeted-followup.json").exists()


def test_runner_reuses_upstream_brief_instead_of_rerunning_daily_discovery() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "select_hunt_signals" in text
    assert "run_openai_hunt_case_enrichment" in text
    assert "run_hunt_case_targeted_followup" in text
    assert "build_domain_market_intelligence_feed" not in text
    assert '"daily_source_discovery_rerun": False' in text
    assert '"upstream_core_reused": True' in text
