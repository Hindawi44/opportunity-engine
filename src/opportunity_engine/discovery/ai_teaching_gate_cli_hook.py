"""Emit AI Teaching Gate V1 after Memory V2 and Route Portfolio V1."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any

from opportunity_engine.ai_teaching_gate_v1 import (
    OUTPUT_FILENAME,
    SCHEMA_VERSION,
    TEXT_FILENAME,
    write_ai_teaching_gate_v1,
)
from opportunity_engine.market_route_portfolio_v1 import (
    OUTPUT_FILENAME as PORTFOLIO_OUTPUT_FILENAME,
)
from opportunity_engine.unified_memory_v2 import (
    MEMORY_FILENAME as UNIFIED_MEMORY_FILENAME,
)


_INSTALLED = False


def _write_failed(output_dir: Path, exc: Exception) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "safely_learned_pattern_count": 0,
        "deterministic_proof_task_count": 0,
        "ai_teaching_task_count": 0,
        "next_manual_ai_task_id": None,
        "mind_forge_contract": {
            "existing_runtime_reused": True,
            "manual_paid_run_required": True,
            "automatic_ai_invocation": False,
        },
        "project_domain_gate_enforced": True,
        "automatic_ai_invocation": False,
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
    (output_dir / TEXT_FILENAME).write_text(
        f"AI TEACHING GATE V1\nFAILED: {type(exc).__name__}: {str(exc)[:300]}\n",
        encoding="utf-8",
    )
    return report


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path.as_posix()}")
    return payload


def _memory_path(output: Path, input_root: str | Path | None) -> Path:
    if input_root is not None:
        root = Path(input_root)
    else:
        configured = str(os.environ.get("INPUT_ROOT") or "").strip()
        root = Path(configured) if configured else output.parent / "multi-market-inputs"

    durable = root / "learning" / UNIFIED_MEMORY_FILENAME
    if durable.exists():
        return durable

    # Backward-compatible fallback for isolated/local tests that still stage the
    # full memory beside other review artifacts. Production checkpoint memory is
    # authoritative under INPUT_ROOT/learning.
    return output / UNIFIED_MEMORY_FILENAME


def run_ai_teaching_gate_v1_fail_closed(
    output_dir: str | Path,
    *,
    input_root: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    try:
        memory = _read_json(_memory_path(output, input_root))
        portfolio = _read_json(output / PORTFOLIO_OUTPUT_FILENAME)
        return write_ai_teaching_gate_v1(
            output,
            unified_memory=memory,
            market_route_portfolio=portfolio,
        )
    except Exception as exc:
        return _write_failed(output, exc)


def install_ai_teaching_gate_cli_hook() -> None:
    """Register a non-spending teaching queue after Spine/Memory/Portfolio.

    Registration order is controlled in discovery.__init__. Because atexit runs
    LIFO, this hook is registered before Unified Learning Spine so runtime is:

        river -> daily learner -> Spine -> Memory V2 -> Route Portfolio
        -> AI Teaching Gate -> Learning Layer

    The gate never imports Agents SDK and never calls OpenAI. It only decides
    whether known work belongs to a fixed rule, deterministic proof loop, or a
    future manual MIND FORGE teaching run.
    """
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return

    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    configured_input_root = str(os.environ.get("INPUT_ROOT") or "").strip()
    input_root = (
        Path(configured_input_root)
        if configured_input_root
        else output_dir.parent / "multi-market-inputs"
    )

    def _run_after_memory_and_portfolio() -> None:
        report = run_ai_teaching_gate_v1_fail_closed(
            output_dir,
            input_root=input_root,
        )
        print(
            "ai_teaching_gate_v1:",
            json.dumps(
                {
                    "status": report.get("status"),
                    "safely_learned_pattern_count": report.get(
                        "safely_learned_pattern_count", 0
                    ),
                    "deterministic_proof_task_count": report.get(
                        "deterministic_proof_task_count", 0
                    ),
                    "ai_teaching_task_count": report.get("ai_teaching_task_count", 0),
                    "next_manual_ai_task_id": report.get("next_manual_ai_task_id"),
                    "automatic_ai_invocation": report.get(
                        "automatic_ai_invocation", False
                    ),
                    "production_mutation": report.get("production_mutation", False),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_memory_and_portfolio)
    _INSTALLED = True
