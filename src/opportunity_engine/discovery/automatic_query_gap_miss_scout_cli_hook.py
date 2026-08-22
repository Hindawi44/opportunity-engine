"""CLI hook for the bounded independent QUERY_GAP miss scout.

Registration order matters. This hook is registered after the Unified River and
before Stocklear. Python ``atexit`` runs handlers LIFO, so execution becomes:
Stocklear -> QUERY_GAP Scout -> Unified River/capture -> Daily Learner.

The hook is fail-closed. A scout failure writes structured evidence and never
activates queries, contacts a seller, bids, purchases or pays.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any


_INSTALLED = False
OUTPUT_FILENAME = "automatic-query-gap-miss-scout.json"


def _failure_report(exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": "automatic-query-gap-miss-scout-1.0",
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": " ".join(str(exc).split())[:500],
        "search_request_count": 0,
        "page_request_count": 0,
        "verified_page_count": 0,
        "detected_miss_count": 0,
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _write_failure(output_dir: Path, report: dict[str, Any]) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / OUTPUT_FILENAME
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except Exception:
        # The parent daily report must survive even if failure evidence cannot be written.
        pass


def install_automatic_query_gap_miss_scout_cli_hook() -> None:
    """Register the scout only for the daily domain-intelligence CLI."""
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

    def _run_before_river() -> None:
        try:
            # Lazy import avoids package-initialization cycles. The waterfall
            # reuses the original exact-page verifier and memory semantics.
            from opportunity_engine.query_gap_scout_waterfall import (
                write_automatic_query_gap_miss_scout,
            )

            report = write_automatic_query_gap_miss_scout(
                output_dir,
                input_root=input_root,
                environment=os.environ,
            )
        except Exception as exc:
            report = _failure_report(exc)
            _write_failure(output_dir, report)

        print(
            "automatic_query_gap_miss_scout:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "waterfall_enabled": report.get("waterfall_enabled", False),
                    "search_request_count": report.get("search_request_count", 0),
                    "page_request_count": report.get("page_request_count", 0),
                    "verified_page_count": report.get("verified_page_count", 0),
                    "detected_miss_count": report.get("detected_miss_count", 0),
                    "new_case_count": report.get("new_case_count", 0),
                    "automatic_query_activation": report.get(
                        "automatic_query_activation", False
                    ),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_before_river)
    _INSTALLED = True
