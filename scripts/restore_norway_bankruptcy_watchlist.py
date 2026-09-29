#!/usr/bin/env python3
"""Restore only the prior Norway bankruptcy watchlist artifact."""

from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from opportunity_engine.discovery import checkpoint_state_restore
from scripts.run_norway_bankruptcy_watchlist import validate_watchlist

ARTIFACT_NAME = "norway-bankruptcy-link-evidence"
WATCHLIST_FILENAME = "bankruptcy-watchlist.json"
WATCHLIST_MEMBERS = (
    WATCHLIST_FILENAME,
    f"norway-bankruptcy/{WATCHLIST_FILENAME}",
    f"artifacts/norway-bankruptcy/{WATCHLIST_FILENAME}",
)


@contextmanager
def configured_watchlist_restore():
    """Reuse the audited checkpoint restore with a single JSON allow-list."""
    names = (
        "ARTIFACT_NAME",
        "RESTORABLE_EVENTS",
        "DATABASE_RELATIVE_PATHS",
        "LEARNING_STATE_FILENAMES",
        "FOLLOW_UP_SEED_FILENAME",
        "FOLLOW_UP_SEED_MEMBERS",
    )
    previous = {name: getattr(checkpoint_state_restore, name) for name in names}
    checkpoint_state_restore.ARTIFACT_NAME = ARTIFACT_NAME
    checkpoint_state_restore.RESTORABLE_EVENTS = {
        "workflow_dispatch",
        "schedule",
        "push",
    }
    checkpoint_state_restore.DATABASE_RELATIVE_PATHS = ()
    checkpoint_state_restore.LEARNING_STATE_FILENAMES = ()
    checkpoint_state_restore.FOLLOW_UP_SEED_FILENAME = WATCHLIST_FILENAME
    checkpoint_state_restore.FOLLOW_UP_SEED_MEMBERS = WATCHLIST_MEMBERS
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(checkpoint_state_restore, name, value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def restore_previous_watchlist(
    *,
    repository: str,
    token: str,
    current_run_id: int,
    target: str | Path,
    status_path: str | Path,
    workflow_file: str = "multi-market-daily-operator-checkpoint.yaml",
    branch: str = "main",
) -> dict[str, Any]:
    destination = Path(target)
    output = Path(status_path)
    with TemporaryDirectory(prefix="norway-bankruptcy-watchlist-") as temporary:
        staging = Path(temporary)
        with configured_watchlist_restore():
            generic_status = (
                checkpoint_state_restore.restore_previous_checkpoint_databases(
                    repository=repository,
                    token=token,
                    current_run_id=current_run_id,
                    input_root=staging / "unused-inputs",
                    status_path=staging / "restore-status.json",
                    workflow_file=workflow_file,
                    branch=branch,
                )
            )
        restored = generic_status.get("restored_follow_up_seed")
        if generic_status.get("status") == "UNAVAILABLE":
            status = {
                "status": "UNAVAILABLE",
                "watchlist_restored": False,
                "error_type": generic_status.get("error_type"),
                "error": generic_status.get("error")
                or generic_status.get("reason")
                or "Previous state is unavailable",
            }
        elif isinstance(restored, Mapping):
            staged_path = Path(str(restored.get("relative_path") or ""))
            try:
                payload = json.loads(staged_path.read_text(encoding="utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("Restored watchlist must be a JSON object")
                validated = validate_watchlist(payload)
            except Exception as exc:
                status = {
                    "status": "UNAVAILABLE",
                    "watchlist_restored": False,
                    "error_type": type(exc).__name__,
                    "error": f"Restored watchlist failed validation: {exc}",
                }
            else:
                _write_json(destination, validated)
                status = {
                    "status": "RESTORED",
                    "watchlist_restored": True,
                    "restored_case_count": len(validated["cases"]),
                    "previous_run_id": generic_status.get("previous_run_id"),
                    "previous_run_event": generic_status.get("previous_run_event"),
                    "previous_artifact_id": generic_status.get("previous_artifact_id"),
                    "restored_member": restored.get("archive_member"),
                }
        else:
            status = {
                "status": "NO_PREVIOUS_STATE",
                "watchlist_restored": False,
                "reason": "No earlier artifact contained the watchlist",
            }
    _write_json(output, status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument(
        "--current-run-id",
        type=int,
        default=int(os.environ.get("GITHUB_RUN_ID", "0") or 0),
    )
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--status-path", type=Path, required=True)
    parser.add_argument(
        "--workflow-file",
        default="multi-market-daily-operator-checkpoint.yaml",
    )
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    status = restore_previous_watchlist(
        repository=args.repository,
        token=args.token,
        current_run_id=args.current_run_id,
        target=args.target,
        status_path=args.status_path,
        workflow_file=args.workflow_file,
        branch=args.branch,
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 2 if status["status"] == "UNAVAILABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
