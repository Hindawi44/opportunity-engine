#!/usr/bin/env python3
"""Add lifecycle stages and SQLite transitions to a completed checkpoint report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    enrich_checkpoint_with_lifecycle,
    write_lifecycle_checkpoint_artifacts,
)


def _load_object(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--restore-status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = _load_object(args.report)
    manifest = _load_object(args.manifest)
    restore_status = (
        _load_object(args.restore_status)
        if args.restore_status and Path(args.restore_status).exists()
        else None
    )
    enriched = enrich_checkpoint_with_lifecycle(
        report,
        manifest,
        root=args.root,
        restore_status=restore_status,
    )
    write_lifecycle_checkpoint_artifacts(enriched, args.report, args.summary)
    print(json.dumps(enriched.get("lifecycle") or {}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
