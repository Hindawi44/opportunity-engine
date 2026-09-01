from __future__ import annotations

from pathlib import Path
import sys

from opportunity_engine.discovery import unified_daily_runtime as runtime
from opportunity_engine.discovery import unified_search_runtime_cli_hook as search_hook
from opportunity_engine.discovery import unified_search_truth_reconciliation_cli_hook as reconciliation_hook
from opportunity_engine.discovery import unified_six_market_runtime_cli_hook as six_market_hook


ROOT = Path(__file__).resolve().parents[1]


def test_explicit_runtime_has_one_ordered_owner(monkeypatch, tmp_path: Path) -> None:
    calls = []

    monkeypatch.setattr(
        runtime,
        "build_unified_runtime_artifacts",
        lambda root: calls.append(("base", root))
        or {"pipeline": root / "unified-six-market-pipeline-v1.json"},
    )

    def finalize() -> None:
        calls.append(("search", tmp_path))
        (tmp_path / "unified-search-runtime-v1.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(runtime.search_runtime, "_finalize_daily_search_runtime", finalize)
    monkeypatch.setattr(
        runtime,
        "reconcile_runtime_artifacts",
        lambda root: calls.append(("reconcile", root))
        or {
            "pipeline": root / "unified-six-market-pipeline-v1.json",
            "runtime": root / "unified-search-runtime-v1.json",
            "summary": root / "unified-six-market-phone-summary-v1.txt",
            "audit": root / "unified-search-truth-reconciliation-v1.json",
        },
    )
    monkeypatch.setattr(
        runtime,
        "write_unified_operator_report",
        lambda root: calls.append(("operator", root))
        or {
            "json": root / "unified-operator-report-v1.json",
            "text": root / "unified-operator-report-v1.txt",
        },
    )

    paths = runtime.build_unified_daily_runtime(tmp_path)

    assert [name for name, _ in calls] == ["base", "search", "reconcile", "operator"]
    assert paths["pipeline"] == tmp_path / "unified-six-market-pipeline-v1.json"
    assert paths["runtime"] == tmp_path / "unified-search-runtime-v1.json"
    assert paths["operator_report_text"] == tmp_path / "unified-operator-report-v1.txt"


def test_explicit_runtime_mode_disables_all_three_legacy_writers(monkeypatch) -> None:
    registered = []
    monkeypatch.setenv("OPPORTUNITY_ENGINE_EXPLICIT_UNIFIED_DAILY_RUNTIME", "1")
    monkeypatch.setattr(sys, "argv", ["build_domain_market_intelligence_feed.py"])

    for module in (search_hook, reconciliation_hook, six_market_hook):
        monkeypatch.setattr(module, "_INSTALLED", False)
        monkeypatch.setattr(module.atexit, "register", registered.append)

    assert search_hook.install_unified_search_runtime_cli_hook() is False
    assert reconciliation_hook.install_unified_search_truth_reconciliation_cli_hook() is False
    assert six_market_hook.install_unified_six_market_runtime_cli_hook() is False
    assert registered == []


def test_workflow_uses_the_explicit_runtime_owner() -> None:
    workflow = (
        ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
    ).read_text(encoding="utf-8")

    assert 'OPPORTUNITY_ENGINE_EXPLICIT_UNIFIED_DAILY_RUNTIME: "1"' in workflow
    assert "python scripts/run_unified_daily_runtime.py" in workflow
    assert workflow.index("Build domain market intelligence bulletin") < workflow.index(
        "Build one explicit unified six-market runtime"
    )
