"""Run Unified Learning Spine and persistent Memory V2 after daily learning."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any

import opportunity_engine.discovery.checkpoint_state_restore as checkpoint_state_restore
from opportunity_engine.unified_learning_spine import (
    OUTPUT_FILENAME,
    SCHEMA_VERSION,
    write_unified_learning_spine,
)
from opportunity_engine.unified_memory_v2 import (
    MEMORY_FILENAME as UNIFIED_MEMORY_FILENAME,
    SCHEMA_VERSION as MEMORY_SCHEMA_VERSION,
    SUMMARY_FILENAME as MEMORY_SUMMARY_FILENAME,
    write_unified_memory_v2,
)

_INSTALLED = False


def _install_unified_memory_restore_allowlist() -> None:
    """Allow only the explicit Memory V2 JSON to survive checkpoint restore."""
    if UNIFIED_MEMORY_FILENAME not in checkpoint_state_restore.LEARNING_STATE_FILENAMES:
        checkpoint_state_restore.LEARNING_STATE_FILENAMES = (
            *checkpoint_state_restore.LEARNING_STATE_FILENAMES,
            UNIFIED_MEMORY_FILENAME,
        )


_install_unified_memory_restore_allowlist()


def _write_failed(output_dir: Path, exc: Exception) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "evidence_record_count": 0,
        "market_counts": {},
        "domain_counts": {},
        "evidence_kind_counts": {},
        "out_of_domain_excluded_count": 0,
        "out_of_domain_excluded_ids": [],
        "project_domain_gate_enforced": True,
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
    (output_dir / OUTPUT_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _write_memory_failed(output_dir: Path, exc: Exception) -> dict[str, Any]:
    report = {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "memory_run_count": 0,
        "evidence_memory_count": 0,
        "new_evidence_count": 0,
        "reobserved_evidence_count": 0,
        "query_memory_count": 0,
        "pattern_count": 0,
        "proven_pattern_count": 0,
        "repeated_success_route_count": 0,
        "failure_pattern_count": 0,
        "rule_review_candidate_count": 0,
        "fixed_rule_pattern_count": 0,
        "ai_still_needed_pattern_count": 0,
        "project_domain_gate_enforced": True,
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
    (output_dir / MEMORY_SUMMARY_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def run_unified_learning_spine_fail_closed(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    try:
        return write_unified_learning_spine(output_dir, input_root=input_root)
    except Exception as exc:
        return _write_failed(Path(output_dir), exc)


def run_unified_memory_v2_fail_closed(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    try:
        return write_unified_memory_v2(
            output_dir,
            input_root=input_root,
            run_id=run_id,
        )
    except Exception as exc:
        # Durable memory is written only inside write_unified_memory_v2 after a
        # complete successful build. A failure therefore leaves prior memory intact.
        return _write_memory_failed(Path(output_dir), exc)


def install_unified_learning_spine_cli_hook() -> None:
    """Register Spine + Memory V2 between daily learning and Learning Layer.

    Python atexit is LIFO. Discovery __init__ registers handlers in this order:

        Learning Layer -> Spine/Memory -> daily learner -> river

    Runtime therefore becomes:

        river -> daily learner -> Unified Learning Spine
        -> Unified Memory V2 -> Learning Layer

    Memory V2 consumes only the successful same-run Spine contract. It persists
    to the checkpoint learning directory for the next daily restore but remains
    review-only and cannot mutate production.
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
        report = run_unified_learning_spine_fail_closed(
            output_dir,
            input_root=input_root,
        )
        print(
            "unified_learning_spine:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "evidence_record_count": report.get("evidence_record_count", 0),
                    "market_counts": report.get("market_counts", {}),
                    "domain_counts": report.get("domain_counts", {}),
                    "out_of_domain_excluded_count": report.get(
                        "out_of_domain_excluded_count", 0
                    ),
                    "production_mutation": report.get("production_mutation", False),
                },
                sort_keys=True,
            ),
        )

        if report.get("status") in {"SUCCESS", "VALID_ZERO"}:
            memory_run_id = str(os.environ.get("GITHUB_RUN_ID") or "").strip()
            if not memory_run_id:
                memory_run_id = str(report.get("generated_at") or "").strip()
            if not memory_run_id:
                memory_run_id = "LOCAL_CHECKPOINT"
            memory_report = run_unified_memory_v2_fail_closed(
                output_dir,
                input_root=input_root,
                run_id=memory_run_id,
            )
        else:
            memory_report = _write_memory_failed(
                output_dir,
                RuntimeError("Unified Learning Spine did not produce a valid memory input"),
            )

        print(
            "unified_memory_v2:",
            json.dumps(
                {
                    "status": memory_report.get("status"),
                    "memory_source": memory_report.get("memory_source"),
                    "memory_run_count": memory_report.get("memory_run_count", 0),
                    "evidence_memory_count": memory_report.get("evidence_memory_count", 0),
                    "new_evidence_count": memory_report.get("new_evidence_count", 0),
                    "proven_pattern_count": memory_report.get("proven_pattern_count", 0),
                    "repeated_success_route_count": memory_report.get(
                        "repeated_success_route_count", 0
                    ),
                    "rule_review_candidate_count": memory_report.get(
                        "rule_review_candidate_count", 0
                    ),
                    "fixed_rule_pattern_count": memory_report.get(
                        "fixed_rule_pattern_count", 0
                    ),
                    "ai_still_needed_pattern_count": memory_report.get(
                        "ai_still_needed_pattern_count", 0
                    ),
                    "production_mutation": memory_report.get(
                        "production_mutation", False
                    ),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_learning)
    _INSTALLED = True
