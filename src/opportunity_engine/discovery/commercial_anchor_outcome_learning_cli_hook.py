"""Wire commercial-anchor outcome learning into the established checkpoint lifecycle.

This hook does not create a search runtime. For the existing multi-market operator
CLI it registers one read-only atexit learner *before* Unified Search Runtime is
registered by discovery.__init__. Because atexit executes LIFO, the existing
six-market Exa runtime finishes first and this learner then consumes its persisted
Exact-Lot resolution evidence.

For the existing previous-state restore CLI, the hook only extends the explicit
learning-state allow-list with the bounded anchor-outcome memory filename. It does
not broaden arbitrary artifact restoration.
"""
from __future__ import annotations

import atexit
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from opportunity_engine.discovery.commercial_anchor_historical_bootstrap import (
    apply_commercial_anchor_historical_bootstrap,
)
from opportunity_engine.discovery.commercial_anchor_outcome_learning import (
    MEMORY_FILENAME,
    OUTPUT_FILENAME,
    write_commercial_anchor_outcome_learning,
)

RUN_MULTI_CLI = "run_multi_market_daily_operator_checkpoint.py"
RESTORE_CLI = "restore_previous_checkpoint_state.py"
_INSTALLED = False

_SAFETY = {
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


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _input_root() -> Path:
    return Path(_compact(os.environ.get("INPUT_ROOT")) or "artifacts/multi-market-inputs")


def _output_dir() -> Path:
    return Path(
        _compact(os.environ.get("OUTPUT_DIR"))
        or "artifacts/multi-market-daily-operator-checkpoint"
    )


def _run_id() -> str:
    return _compact(os.environ.get("GITHUB_RUN_ID")) or "LOCAL_CHECKPOINT"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_failure_report(output_dir: Path, exc: Exception) -> None:
    payload: dict[str, Any] = {
        "schema_version": "commercial-anchor-outcome-learning-1.0",
        "status": "FAILURE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error_type": type(exc).__name__,
        "error": _compact(exc)[:1000],
        "learning_evidence_only": True,
        "anchor_is_qualification_evidence": False,
        **_SAFETY,
    }
    _write_json(output_dir / OUTPUT_FILENAME, payload)


def _bootstrap_failure(exc: Exception) -> dict[str, Any]:
    return {
        "status": "FAILURE",
        "error_type": type(exc).__name__,
        "error": _compact(exc)[:1000],
        "search_requests": 0,
        "learning_evidence_only": True,
        "anchor_is_qualification_evidence": False,
        **_SAFETY,
    }


def _run_anchor_outcome_learning() -> None:
    """Consume current six-market Exact-Lot outcome evidence without searching."""
    input_root = _input_root()
    output_dir = _output_dir()

    # Historical bootstrap is evidence-only and must not suppress truthful current
    # learning if its static reviewed artifact ever becomes invalid.
    try:
        bootstrap = apply_commercial_anchor_historical_bootstrap(input_root=input_root)
    except Exception as exc:
        bootstrap = _bootstrap_failure(exc)

    try:
        report = write_commercial_anchor_outcome_learning(
            input_root=input_root,
            output_dir=output_dir,
            run_id=_run_id(),
        )
        report["historical_bootstrap"] = bootstrap
        _write_json(output_dir / OUTPUT_FILENAME, report)
    except Exception as exc:  # learning must never break the established checkpoint
        _write_failure_report(output_dir, exc)


def _allow_restore_memory_state() -> None:
    """Add exactly one bounded learning artifact to the existing restore allow-list."""
    from opportunity_engine.discovery import checkpoint_state_restore

    if MEMORY_FILENAME not in checkpoint_state_restore.LEARNING_STATE_FILENAMES:
        checkpoint_state_restore.LEARNING_STATE_FILENAMES = (
            *checkpoint_state_restore.LEARNING_STATE_FILENAMES,
            MEMORY_FILENAME,
        )


def install_commercial_anchor_outcome_learning_cli_hook() -> bool:
    """Install only on the two established checkpoint lifecycle CLIs."""
    global _INSTALLED
    if _INSTALLED:
        return False

    target = Path(sys.argv[0]).name
    if target == RUN_MULTI_CLI:
        atexit.register(_run_anchor_outcome_learning)
    elif target == RESTORE_CLI:
        _allow_restore_memory_state()
    else:
        return False

    _INSTALLED = True
    return True
