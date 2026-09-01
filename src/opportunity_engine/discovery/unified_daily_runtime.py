"""Build the daily six-market operator runtime through one explicit owner."""
from __future__ import annotations

from pathlib import Path

from opportunity_engine.discovery import unified_search_runtime_cli_hook as search_runtime
from opportunity_engine.discovery.unified_search_truth_reconciliation_cli_hook import (
    reconcile_runtime_artifacts,
)
from opportunity_engine.discovery.unified_operator_report import (
    write_unified_operator_report,
)
from opportunity_engine.discovery.unified_six_market_runtime_cli_hook import (
    build_unified_runtime_artifacts,
)


def build_unified_daily_runtime(output_dir: str | Path) -> dict[str, Path]:
    """Build, augment, and reconcile the operator runtime in a fixed order."""
    root = Path(output_dir)
    base = build_unified_runtime_artifacts(root)
    search_runtime._finalize_daily_search_runtime()

    runtime_path = root / "unified-search-runtime-v1.json"
    if not runtime_path.exists():
        raise RuntimeError("Unified search runtime was not emitted")

    reconciled = reconcile_runtime_artifacts(root)
    operator = write_unified_operator_report(root)
    return {
        "pipeline": reconciled["pipeline"],
        "runtime": reconciled["runtime"],
        "summary": reconciled["summary"],
        "reconciliation": reconciled["audit"],
        "operator_report_json": operator["json"],
        "operator_report_text": operator["text"],
        "base_pipeline": base["pipeline"],
    }
