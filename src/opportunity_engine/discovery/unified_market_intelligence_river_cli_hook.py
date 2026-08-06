"""Install the unified river after the established bulletin CLI completes."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import sys

from opportunity_engine.discovery.unified_market_intelligence_river import (
    write_unified_market_intelligence_river,
)

_INSTALLED = False


def install_unified_market_intelligence_river_cli_hook() -> None:
    """Register a bounded post-bulletin projection for the existing CLI only.

    The hook activates only for ``build_domain_market_intelligence_feed.py`` and
    only when that command has produced its base domain brief. No collector or
    network path is changed.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_after_bulletin() -> None:
        if not (output_dir / "domain-market-intelligence-brief.json").exists():
            return
        brief = write_unified_market_intelligence_river(output_dir)
        print(
            "unified_market_intelligence_river:",
            json.dumps(
                {
                    "status": brief.get("status"),
                    "counts": brief.get("counts"),
                    "output_files": brief.get("output_files"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_bulletin)
    _INSTALLED = True
