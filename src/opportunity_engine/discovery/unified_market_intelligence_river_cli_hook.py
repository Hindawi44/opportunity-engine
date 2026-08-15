"""Install the unified river and bounded signal follow-up after the bulletin CLI."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys

from opportunity_engine.discovery.signal_follow_up_continuity import (
    write_signal_follow_up_engine_with_continuity,
)
from opportunity_engine.discovery.unified_market_intelligence_river import (
    write_unified_market_intelligence_river,
)

_INSTALLED = False


def install_unified_market_intelligence_river_cli_hook() -> None:
    """Register bounded post-bulletin projections for the existing CLI only.

    The hook activates only for ``build_domain_market_intelligence_feed.py`` and
    only when that command has produced its base domain brief. The unified river
    is written first; then the signal follow-up continuity layer searches durable
    entity scents before filling any remaining budget with current early-signal
    cases. Search hits remain unverified leads and cannot promote an opportunity
    or perform any commercial action.
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
        follow_up = write_signal_follow_up_engine_with_continuity(
            output_dir,
            environment=os.environ,
        )
        print(
            "signal_follow_up_engine:",
            json.dumps(
                {
                    "status": follow_up.get("status"),
                    "eligible_follow_up_case_count": follow_up.get("eligible_follow_up_case_count"),
                    "selected_case_count": follow_up.get("selected_case_count"),
                    "persistent_entity_case_count": follow_up.get("persistent_entity_case_count"),
                    "persistent_entity_selected_count": follow_up.get("persistent_entity_selected_count"),
                    "search_request_count": follow_up.get("search_request_count"),
                    "commercial_lead_count": follow_up.get("commercial_lead_count"),
                    "explicit_commercial_case_link_count": follow_up.get(
                        "explicit_commercial_case_link_count"
                    ),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_bulletin)
    _INSTALLED = True
