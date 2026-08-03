#!/usr/bin/env python3
"""Apply persisted human reviews to a completed lifecycle checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.human_review_checkpoint import (
    reconcile_checkpoint_human_reviews,
)
from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    write_lifecycle_checkpoint_artifacts,
)


def _load(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reconciled = reconcile_checkpoint_human_reviews(
        _load(args.report),
        _load(args.manifest),
        root=args.root,
    )
    write_lifecycle_checkpoint_artifacts(
        reconciled,
        args.report,
        args.summary,
    )
    print(
        json.dumps(
            {
                "human_review_outcome_count": reconciled.get(
                    "human_review_outcome_count", 0
                ),
                "next_human_action": reconciled.get("next_human_action"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
