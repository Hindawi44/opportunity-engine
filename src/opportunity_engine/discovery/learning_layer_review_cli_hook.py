"""Run the unified Learning Layer after same-run learning artifacts exist."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any

from opportunity_engine.learning_layer import write_learning_layer_review

_INSTALLED = False
REPORT_FILENAME = "learning-layer-review.json"


def _write_failed(output_dir: Path, exc: Exception) -> dict[str, Any]:
    report = {
        "schema_version": "learning-layer-review-1.0",
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "review_item_count": 0,
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
    (output_dir / REPORT_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def run_learning_layer_review_fail_closed(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    try:
        return write_learning_layer_review(output_dir, input_root=input_root)
    except Exception as exc:
        return _write_failed(Path(output_dir), exc)


def install_learning_layer_review_cli_hook() -> None:
    """Register only for the daily domain-intelligence build CLI.

    This hook must be registered before the daily miss learner and unified river.
    Because atexit runs LIFO, capture/routing runs first, daily keyword learning
    runs second, and this Learning Layer aggregation runs last.
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
        report = run_learning_layer_review_fail_closed(
            output_dir,
            input_root=input_root,
        )
        print(
            "learning_layer_review:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "what_worked_count": report.get("what_worked_count", 0),
                    "what_failed_count": report.get("what_failed_count", 0),
                    "review_item_count": report.get("review_item_count", 0),
                    "replicated_search_route_count": report.get(
                        "replicated_search_route_count", 0
                    ),
                    "active_root_cause_route_count": report.get(
                        "active_root_cause_route_count", 0
                    ),
                    "automatic_query_activation": report.get(
                        "automatic_query_activation", False
                    ),
                    "automatic_provider_activation": report.get(
                        "automatic_provider_activation", False
                    ),
                    "production_mutation": report.get("production_mutation", False),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_learning)
    _INSTALLED = True
