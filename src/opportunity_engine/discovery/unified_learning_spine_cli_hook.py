"""Run Unified Learning Spine, Memory V2 and Market Route Portfolio V1."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any

import opportunity_engine.discovery.checkpoint_state_restore as checkpoint_state_restore
from opportunity_engine.auksjonen_route_learning import (
    write_unified_learning_spine_with_native_routes as write_unified_learning_spine,
)
from opportunity_engine.market_route_portfolio_v1 import (
    OUTPUT_FILENAME as PORTFOLIO_OUTPUT_FILENAME,
    SCHEMA_VERSION as PORTFOLIO_SCHEMA_VERSION,
    TEXT_FILENAME as PORTFOLIO_TEXT_FILENAME,
    write_market_route_portfolio_v1,
)
from opportunity_engine.unified_learning_spine import (
    OUTPUT_FILENAME,
    SCHEMA_VERSION,
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


def _write_portfolio_failed(output_dir: Path, exc: Exception) -> dict[str, Any]:
    report = {
        "schema_version": PORTFOLIO_SCHEMA_VERSION,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "market_count": 0,
        "market_route_complete_count": 0,
        "market_must_continue_discovery_count": 0,
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
    (output_dir / PORTFOLIO_OUTPUT_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / PORTFOLIO_TEXT_FILENAME).write_text(
        f"MARKET ROUTE PORTFOLIO V1\nFAILED: {type(exc).__name__}: {str(exc)[:300]}\n",
        encoding="utf-8",
    )
    return report


def _append_portfolio_to_phone_summary(output_dir: Path) -> None:
    phone = output_dir / "multi-market-phone-summary.txt"
    portfolio_text = output_dir / PORTFOLIO_TEXT_FILENAME
    if not phone.exists() or not portfolio_text.exists():
        return
    existing = phone.read_text(encoding="utf-8")
    addition = portfolio_text.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    phone.write_text(existing + separator + addition, encoding="utf-8")


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
        return _write_memory_failed(Path(output_dir), exc)


def run_market_route_portfolio_v1_fail_closed(
    output_dir: str | Path,
    *,
    unified_memory: dict[str, Any],
) -> dict[str, Any]:
    try:
        report = write_market_route_portfolio_v1(
            output_dir,
            unified_memory=unified_memory,
        )
    except Exception as exc:
        report = _write_portfolio_failed(Path(output_dir), exc)
    _append_portfolio_to_phone_summary(Path(output_dir))
    return report


def install_unified_learning_spine_cli_hook() -> None:
    """Register Spine -> Memory V2 -> Route Portfolio before Learning Layer.

    Python atexit is LIFO. The established registration order yields runtime:

        river -> daily learner -> Unified Learning Spine -> Unified Memory V2
        -> Market Route Portfolio V1 -> Learning Layer

    The portfolio is derived from already-domain-gated memory and is review-only.
    It cannot activate a query/provider/source or perform a commercial action.
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

        if memory_report.get("status") in {"SUCCESS", "VALID_ZERO"}:
            portfolio_report = run_market_route_portfolio_v1_fail_closed(
                output_dir,
                unified_memory=memory_report,
            )
        else:
            portfolio_report = _write_portfolio_failed(
                output_dir,
                RuntimeError("Unified Memory V2 did not produce valid portfolio input"),
            )
            _append_portfolio_to_phone_summary(output_dir)

        print(
            "market_route_portfolio_v1:",
            json.dumps(
                {
                    "status": portfolio_report.get("status"),
                    "market_count": portfolio_report.get("market_count", 0),
                    "market_route_complete_count": portfolio_report.get(
                        "market_route_complete_count", 0
                    ),
                    "market_must_continue_discovery_count": portfolio_report.get(
                        "market_must_continue_discovery_count", 0
                    ),
                    "production_mutation": portfolio_report.get(
                        "production_mutation", False
                    ),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_learning)
    _INSTALLED = True
