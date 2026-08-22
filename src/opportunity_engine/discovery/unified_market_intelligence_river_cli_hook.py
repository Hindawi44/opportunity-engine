"""Install the unified river and bounded signal follow-up after the bulletin CLI."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys

from opportunity_engine.automatic_missed_opportunity_capture import (
    write_automatic_missed_opportunity_capture,
)
from opportunity_engine.discovery.signal_follow_up_continuity import (
    write_signal_follow_up_engine_with_continuity,
)
from opportunity_engine.discovery.signal_follow_up_source_verification import (
    write_signal_follow_up_source_verification,
)
from opportunity_engine.discovery.unified_market_intelligence_river import (
    write_unified_market_intelligence_river,
)
from opportunity_engine.root_cause_feedback_router import (
    write_root_cause_feedback_router,
)

_INSTALLED = False


def install_unified_market_intelligence_river_cli_hook() -> None:
    """Register bounded post-bulletin projections for the existing CLI only.

    The hook activates only for ``build_domain_market_intelligence_feed.py`` and
    only when that command has produced its base domain brief. The unified river
    is written first; then the signal follow-up continuity layer searches durable
    entity scents before filling any remaining budget with current early-signal
    cases. Supported exact public item URLs are routed into existing
    source-specific VENTA/Auksjonen verifiers. Source-verified bulk clothing lots
    absent from the canonical checkpoint are then captured into durable missed-
    opportunity memory. Finally the root-cause feedback router assigns each miss
    to its correct adaptation mechanism, so source/parser/verifier/reporting
    failures never accidentally become keyword-learning changes.
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
        source_verification = write_signal_follow_up_source_verification(
            output_dir,
            follow_up_report=follow_up,
        )
        print(
            "signal_follow_up_source_verification:",
            json.dumps(
                {
                    "status": source_verification.get("status"),
                    "candidate_lead_count": source_verification.get("candidate_lead_count"),
                    "supported_exact_item_lead_count": source_verification.get(
                        "supported_exact_item_lead_count"
                    ),
                    "verification_request_count": source_verification.get(
                        "verification_request_count"
                    ),
                    "source_page_verified_count": source_verification.get(
                        "source_page_verified_count"
                    ),
                    "source_page_failed_count": source_verification.get(
                        "source_page_failed_count"
                    ),
                    "verified_with_price_count": source_verification.get(
                        "verified_with_price_count"
                    ),
                    "verified_with_weight_count": source_verification.get(
                        "verified_with_weight_count"
                    ),
                    "verified_with_quantity_count": source_verification.get(
                        "verified_with_quantity_count"
                    ),
                    "verified_with_pallet_count": source_verification.get(
                        "verified_with_pallet_count"
                    ),
                },
                sort_keys=True,
            ),
        )

        input_root = Path(
            str(os.environ.get("INPUT_ROOT") or "").strip()
            or (output_dir.parent / "multi-market-inputs").as_posix()
        )
        miss_capture = write_automatic_missed_opportunity_capture(
            output_dir,
            input_root=input_root,
            root=".",
        )
        print(
            "automatic_missed_opportunity_capture:",
            json.dumps(
                {
                    "status": miss_capture.get("status"),
                    "verified_candidate_count": miss_capture.get(
                        "verified_candidate_count"
                    ),
                    "detected_miss_count": miss_capture.get("detected_miss_count"),
                    "new_case_count": miss_capture.get("new_case_count"),
                    "repeat_miss_count_this_run": miss_capture.get(
                        "repeat_miss_count_this_run"
                    ),
                    "root_cause_counts": miss_capture.get("root_cause_counts"),
                },
                sort_keys=True,
            ),
        )

        feedback = write_root_cause_feedback_router(
            output_dir,
            input_root=input_root,
        )
        print(
            "root_cause_feedback_router:",
            json.dumps(
                {
                    "status": feedback.get("status"),
                    "active_route_count": feedback.get("active_route_count"),
                    "critical_route_count": feedback.get("critical_route_count"),
                    "keyword_learning_route_count": feedback.get(
                        "keyword_learning_route_count"
                    ),
                    "mechanism_counts": feedback.get("mechanism_counts"),
                    "root_cause_counts": feedback.get("root_cause_counts"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_bulletin)
    _INSTALLED = True
