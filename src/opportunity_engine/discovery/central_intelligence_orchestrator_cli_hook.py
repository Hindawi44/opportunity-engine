"""Run the central intelligence synthesis after existing daily projections."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys

from opportunity_engine.discovery.central_intelligence_orchestrator import (
    write_central_intelligence_orchestrator,
)

_INSTALLED = False


def install_central_intelligence_orchestrator_cli_hook() -> None:
    """Register the final read-only daily synthesis.

    This hook must be registered before the market-comparables and river hooks.
    Python executes atexit callbacks in reverse order, so the established order is:

    fabric watch -> fabric AI -> unified river -> market comparables -> central brief
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_last() -> None:
        if not (output_dir / "domain-market-intelligence-brief.json").exists():
            return
        brief = write_central_intelligence_orchestrator(output_dir)
        action = brief.get("primary_human_action") or {}
        print(
            "central_intelligence_orchestrator:",
            json.dumps(
                {
                    "status": brief.get("status"),
                    "market_visibility": brief.get("market_visibility"),
                    "primary_action": action.get("action_type"),
                    "target": action.get("target"),
                    "output_files": brief.get("output_files"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_last)
    _INSTALLED = True
