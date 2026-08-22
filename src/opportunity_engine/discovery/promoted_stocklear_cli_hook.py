"""Run explicitly promoted Stocklear before the unified daily river."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys

from opportunity_engine.promoted_source_production import write_promoted_stocklear_feed
from opportunity_engine.discovery import unified_market_intelligence_river as river_module

_INSTALLED = False
_FEED_FILENAME = "stocklear-promoted-source-feed.json"


def install_promoted_stocklear_cli_hook() -> None:
    """Register promoted Stocklear for the existing daily intelligence CLI only."""
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_before_unified_river() -> None:
        if not (output_dir / "domain-market-intelligence-brief.json").exists():
            return
        # The river is a read-only projection over named artifacts. The source
        # hook registers this promoted feed as an input only in this process.
        if _FEED_FILENAME not in river_module.INPUT_ARTIFACTS:
            river_module.INPUT_ARTIFACTS = (*river_module.INPUT_ARTIFACTS, _FEED_FILENAME)
        try:
            report = write_promoted_stocklear_feed(output_dir)
        except Exception as exc:
            report = {
                "status": "SOURCE_FETCH_FAILED",
                "production_source_active": True,
                "candidate_count": 0,
                "network_request_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
                "automatic_promotion": False,
            }
            (output_dir / _FEED_FILENAME).write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        print(
            "promoted_stocklear_production:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "production_source_active": report.get("production_source_active"),
                    "candidate_count": report.get("candidate_count"),
                    "network_request_count": report.get("network_request_count"),
                    "automatic_promotion": report.get("automatic_promotion"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_before_unified_river)
    _INSTALLED = True
