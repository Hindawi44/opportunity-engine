"""Run the bounded market benchmark after the unified river is written."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys

from opportunity_engine.discovery.market_comparables_benchmark import (
    write_market_comparables_benchmark,
)

_INSTALLED = False


def install_market_comparables_benchmark_cli_hook() -> None:
    """Register only for the established daily bulletin command.

    This hook must be registered before the river hook. Python executes atexit
    callbacks in reverse order, so the river artifacts are available before the
    benchmark starts.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_after_river() -> None:
        try:
            report = write_market_comparables_benchmark(output_dir)
        except Exception as exc:  # keep the established bulletin truthful and available
            report = {
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "error": " ".join(str(exc).split())[:500],
                "decision_owner": "HUMAN_OPERATOR",
                "automatic_purchase": False,
            }
        print(
            "market_comparables_benchmark:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "target_count": report.get("target_count"),
                    "requests_made": report.get("requests_made"),
                    "accepted_comparable_count": report.get("accepted_comparable_count"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_river)
    _INSTALLED = True
