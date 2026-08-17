"""Write Mathematical Logic V1 after the unified river has finished."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys

from opportunity_engine.discovery.mathematical_logic_shadow import (
    write_mathematical_logic_shadow,
)

_INSTALLED = False


def install_mathematical_logic_shadow_cli_hook() -> None:
    """Register a read-only post-river shadow writer for the bulletin CLI.

    This hook must be registered before the unified-river hook. Python executes
    atexit handlers in reverse registration order, so the unified river writes
    its case artifact first and Math V1 observes it afterwards.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_after_unified_river() -> None:
        if not (output_dir / "unified-market-cases.json").exists():
            return
        report = write_mathematical_logic_shadow(
            output_dir,
            baseline_commit=os.environ.get("GITHUB_SHA") or None,
        )
        aggregate = ((report.get("aggregate") or {}).get("all_cases") or {})
        print(
            "mathematical_logic_shadow_v1:",
            json.dumps(
                {
                    "engine_version": report.get("engine_version"),
                    "case_count": (report.get("baseline") or {}).get("observed_case_count"),
                    "coverage_matches": (report.get("baseline") or {}).get(
                        "coverage_matches_declared_count"
                    ),
                    "mean_completeness": aggregate.get("mean_completeness"),
                    "mean_decision_distance": aggregate.get("mean_decision_distance"),
                    "decision_influence": (report.get("methodology") or {}).get(
                        "decision_influence"
                    ),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_unified_river)
    _INSTALLED = True
