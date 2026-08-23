"""Run Unified Learning Spine after river + daily learning artifacts exist."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any

from opportunity_engine.unified_learning_spine import (
    OUTPUT_FILENAME,
    SCHEMA_VERSION,
    write_unified_learning_spine,
)

_INSTALLED = False


def _write_failed(output_dir: Path, exc: Exception) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "evidence_record_count": 0,
        "market_counts": {},
        "domain_counts": {},
        "evidence_kind_counts": {},
        "out_of_domain_excluded_count": 0,
        "out_of_domain_excluded_ids": [],
        "project_domain_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / OUTPUT_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def run_unified_learning_spine_fail_closed(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    try:
        return write_unified_learning_spine(output_dir, input_root=input_root)
    except Exception as exc:
        return _write_failed(Path(output_dir), exc)


def install_unified_learning_spine_cli_hook() -> None:
    """Register the daily spine between daily learning and Learning Layer.

    Python atexit is LIFO.  Discovery __init__ registers handlers in this order:

        Learning Layer -> Unified Learning Spine -> daily learner -> river

    Runtime therefore becomes:

        river -> daily learner -> Unified Learning Spine -> Learning Layer

    so the spine sees the same-run unified river plus the same-run durable
    learning state while remaining independent of the operator-facing Learning
    Layer review plane.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    input_root = Path(
        str(os.environ.get("INPUT_ROOT") or "").strip()
        or (output_dir.parent / "multi-market-inputs").as_posix()
    )

    def _run_after_learning() -> None:
        report = run_unified_learning_spine_fail_closed(
            output_dir,
            input_root=input_root,
        )
        print(
            "unified_learning_spine:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "evidence_record_count": report.get("evidence_record_count", 0),
                    "market_counts": report.get("market_counts", {}),
                    "domain_counts": report.get("domain_counts", {}),
                    "out_of_domain_excluded_count": report.get(
                        "out_of_domain_excluded_count", 0
                    ),
                    "production_mutation": report.get("production_mutation", False),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_learning)
    _INSTALLED = True
