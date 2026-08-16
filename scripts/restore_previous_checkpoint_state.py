#!/usr/bin/env python3
"""Restore lifecycle SQLite files from the previous successful checkpoint run."""
from __future__ import annotations

import argparse
import json
import os

from opportunity_engine.discovery import checkpoint_state_restore


ITALY_MEMORY_RELATIVE_PATH = "it-market/opportunity_engine.db"
NETHERLANDS_MEMORY_RELATIVE_PATH = "nl-market/opportunity_engine.db"
FRANCE_MEMORY_RELATIVE_PATH = "fr-market/opportunity_engine.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    extra_paths = (
        ITALY_MEMORY_RELATIVE_PATH,
        NETHERLANDS_MEMORY_RELATIVE_PATH,
        FRANCE_MEMORY_RELATIVE_PATH,
    )
    for relative_path in extra_paths:
        if relative_path not in checkpoint_state_restore.DATABASE_RELATIVE_PATHS:
            checkpoint_state_restore.DATABASE_RELATIVE_PATHS = (
                *checkpoint_state_restore.DATABASE_RELATIVE_PATHS,
                relative_path,
            )
    status = checkpoint_state_restore.restore_previous_checkpoint_databases(
        repository=args.repository,
        token=args.token,
        current_run_id=args.current_run_id,
        input_root=args.input_root,
        status_path=args.status_path,
        workflow_file=args.workflow_file,
        branch=args.branch,
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
