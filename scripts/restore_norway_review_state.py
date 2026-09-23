#!/usr/bin/env python3
"""Restore only durable Norwegian review state from the existing checkpoint artifact."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery import checkpoint_state_restore


def configure_norway_only_restore() -> None:
    """Reuse the existing restore mechanism while excluding every foreign state file."""
    checkpoint_state_restore.DATABASE_RELATIVE_PATHS = tuple(
        path
        for path in checkpoint_state_restore.DATABASE_RELATIVE_PATHS
        if path.startswith("no-")
    )
    # Review learning is rebuilt from Norwegian SQLite decisions. Do not import
    # the old cross-market search overlays or cross-source follow-up seed.
    checkpoint_state_restore.LEARNING_STATE_FILENAMES = ()
    checkpoint_state_restore.FOLLOW_UP_SEED_MEMBERS = ()
    # Main-branch push artifacts become the durable continuation point. The
    # legacy scheduled/manual artifact remains eligible for the first restore.
    checkpoint_state_restore.RESTORABLE_EVENTS = {
        "workflow_dispatch",
        "schedule",
        "push",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument(
        "--current-run-id",
        type=int,
        default=int(os.environ.get("GITHUB_RUN_ID", "0") or 0),
    )
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--status-path", required=True)
    parser.add_argument(
        "--workflow-file",
        default="multi-market-daily-operator-checkpoint.yaml",
    )
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()

    configure_norway_only_restore()
    status = checkpoint_state_restore.restore_previous_checkpoint_databases(
        repository=args.repository,
        token=args.token,
        current_run_id=args.current_run_id,
        input_root=args.input_root,
        status_path=args.status_path,
        workflow_file=args.workflow_file,
        branch=args.branch,
    )
    foreign = [
        item
        for item in status.get("restored_databases", [])
        if not str(item.get("relative_path") or "").split("/")[-2].startswith("no-")
    ]
    if foreign:
        raise RuntimeError(f"foreign database restored in Norway-only mode: {foreign}")
    status["norway_only"] = True
    status["foreign_databases_restored"] = 0
    Path(args.status_path).write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
