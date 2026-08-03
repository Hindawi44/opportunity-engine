#!/usr/bin/env python3
"""Download the latest successful daily-analysis artifact for commercial review."""
from __future__ import annotations

import argparse
import json
import os

from opportunity_engine.discovery.latest_checkpoint_analysis import (
    download_latest_checkpoint_analysis,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--status-path", required=True)
    parser.add_argument(
        "--workflow-file",
        default="multi-market-daily-operator-checkpoint.yaml",
    )
    parser.add_argument("--branch", default="main")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status = download_latest_checkpoint_analysis(
        repository=args.repository,
        token=args.token,
        output_dir=args.output_dir,
        status_path=args.status_path,
        workflow_file=args.workflow_file,
        branch=args.branch,
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0 if status.get("status") == "RESTORED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
