"""Run bounded missed-opportunity learning after the daily capture stage.

The existing unified-river hook verifies and persists missed opportunities near
process exit. This hook is intentionally registered *before* that hook because
``atexit`` handlers run LIFO: capture/routing executes first, then this consumer
reads the newly durable miss memory in the same daily run.

Learning remains shadow-first and promotion-gated. Manual GitHub runs inherit
the existing paid-Brave cost guard; scheduled runs may evaluate at most two
candidate patterns with five results each. Learning failure is fail-closed and
must never invalidate the already-produced discovery checkpoint.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from opportunity_engine.daily_learning_operator import DailyLearningPolicy
from opportunity_engine.daily_learning_runtime import run_daily_learning_runtime


_INSTALLED = False
CAPTURE_FILENAME = "automatic-missed-opportunity-capture.json"
REPORT_FILENAME = "daily-learning-cycle.json"


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def _write_object(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _attach_to_brief(output_dir: Path, report: Mapping[str, Any]) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_object(brief_path)
    if brief is None:
        return
    brief["daily_auto_miss_learning"] = {
        key: report.get(key)
        for key in (
            "status",
            "generated_at",
            "search_status",
            "known_missed_opportunity_count",
            "candidate_count",
            "evaluated_candidate_count",
            "learning_search_requests",
            "proven_term_count_this_run",
            "shadow_proven_term_count",
            "active_learned_term_count",
            "recovered_case_count",
            "transfer_proven_case_count",
            "safe_learning_proof_status",
            "safe_learning_shadow_recovered_case_count",
            "safe_learning_shadow_transfer_proven_case_count",
            "safe_learning_promotion_eligible_count",
            "promotion_gate_enforced",
            "automatic_query_activation",
            "learning_timing",
            "error_type",
            "error",
        )
    }
    _write_object(brief_path, brief)


def run_daily_auto_miss_learning(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Consume durable miss memory only after today's capture artifact exists."""
    output = Path(output_dir)
    root = Path(input_root)
    capture = _read_object(output / CAPTURE_FILENAME)
    if capture is None:
        return {
            "status": "SKIPPED_NO_CAPTURE_ARTIFACT",
            "reason": "daily miss capture did not finish, so learning was not run",
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    report = run_daily_learning_runtime(
        learning_dir=root / "learning",
        inbox_path="config/learning/missed_opportunity_inbox.json",
        validation_cases_path="config/learning/query_gap_validation_cases.json",
        active_query_config="config/brave_search_queries.json",
        promotion_config_path="config/learning/query_promotions.json",
        report_path=output / REPORT_FILENAME,
        environment=environment,
        policy=DailyLearningPolicy(
            max_candidates_per_run=2,
            min_recovered_cases=1,
            min_precision=0.20,
            max_terms_per_market=5,
        ),
        results_per_candidate=5,
    )
    report["capture_status"] = capture.get("status")
    report["captured_new_case_count"] = int(capture.get("new_case_count") or 0)
    report["captured_repeat_miss_count"] = int(
        capture.get("repeat_miss_count_this_run") or 0
    )
    report["learning_timing"] = "POST_CAPTURE_SAME_RUN"
    report["automatic_query_activation"] = False
    report["automatic_contact"] = False
    report["automatic_bid"] = False
    report["automatic_purchase"] = False
    report["automatic_payment"] = False
    _write_object(output / REPORT_FILENAME, report)
    _attach_to_brief(output, report)
    return report


def run_daily_auto_miss_learning_fail_closed(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run post-capture learning without allowing it to break discovery output."""
    output = Path(output_dir)
    try:
        return run_daily_auto_miss_learning(
            output,
            input_root=input_root,
            environment=environment,
        )
    except Exception as exc:
        report = {
            "status": "FAILED",
            "search_status": "FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "learning_timing": "POST_CAPTURE_SAME_RUN",
            "learning_search_requests": 0,
            "proven_term_count_this_run": 0,
            "active_learned_term_count": 0,
            "promotion_gate_enforced": True,
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_object(output / REPORT_FILENAME, report)
        _attach_to_brief(output, report)
        return report


def install_daily_auto_miss_learning_cli_hook() -> None:
    """Register the post-capture learner only for the daily bulletin CLI."""
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

    def _run_after_capture() -> None:
        report = run_daily_auto_miss_learning_fail_closed(
            output_dir,
            input_root=input_root,
            environment=os.environ,
        )
        print(
            "daily_auto_miss_learning:",
            json.dumps(
                {
                    "status": report.get("status") or report.get("search_status"),
                    "capture_status": report.get("capture_status"),
                    "captured_new_case_count": report.get("captured_new_case_count", 0),
                    "known_missed_opportunity_count": report.get(
                        "known_missed_opportunity_count", 0
                    ),
                    "candidate_count": report.get("candidate_count", 0),
                    "learning_search_requests": report.get("learning_search_requests", 0),
                    "proven_term_count_this_run": report.get(
                        "proven_term_count_this_run", 0
                    ),
                    "shadow_proven_term_count": report.get(
                        "shadow_proven_term_count", 0
                    ),
                    "active_learned_term_count": report.get(
                        "active_learned_term_count", 0
                    ),
                    "promotion_gate_enforced": report.get(
                        "promotion_gate_enforced", False
                    ),
                    "automatic_query_activation": report.get(
                        "automatic_query_activation", False
                    ),
                    "learning_timing": report.get("learning_timing"),
                    "error_type": report.get("error_type"),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_capture)
    _INSTALLED = True
