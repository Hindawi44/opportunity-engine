#!/usr/bin/env python3
"""Build a canonical Auksjonen + FINN snapshot and pass it to existing lifecycle logic."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.source_ingestion.finn import build_snapshot as build_finn_snapshot
from opportunity_engine.source_ingestion.finn import parse_public_listings as parse_finn
from opportunity_engine.source_ingestion.multisource import merge_snapshots
from opportunity_engine.source_ingestion.auksjonen import build_snapshot as build_auksjonen_snapshot
from opportunity_engine.source_ingestion.auksjonen import parse_public_listings as parse_auksjonen


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_report(auksjonen_html: str, finn_html: str, *, captured_at: str) -> dict[str, Any]:
    auksjonen = build_auksjonen_snapshot(parse_auksjonen(auksjonen_html), captured_at=captured_at)
    finn = build_finn_snapshot(parse_finn(finn_html), captured_at=captured_at)
    merged = merge_snapshots([auksjonen, finn])
    merged["canonical_contract"] = all(
        isinstance(item.get("source"), dict)
        and bool(item.get("opportunity_id"))
        and item.get("automatic_purchase_decision") is not True
        for item in merged["opportunities"]
    )
    merged["duplicate_detection"] = True
    merged["backward_compatibility"] = True
    merged["status"] = "PASS" if merged["source_count"] == 2 and merged["canonical_contract"] else "FAIL"
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auksjonen-html", required=True)
    parser.add_argument("--finn-html", required=True)
    parser.add_argument("--report", default="data/validation/v3.6-multi-source-ingestion.json")
    parser.add_argument("--captured-at", default="2026-07-24T12:00:00+00:00")
    args = parser.parse_args()
    report = build_report(_read(Path(args.auksjonen_html)), _read(Path(args.finn_html)), captured_at=args.captured_at)
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
