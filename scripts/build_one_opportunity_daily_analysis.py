#!/usr/bin/env python3
"""Build one daily analysis intake from the final multi-market checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.one_opportunity_daily_analysis import (
    build_daily_analysis,
    render_daily_analysis,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _identity_values(record: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("opportunity_id", "opportunity_identity", "source_url", "canonical_url", "url"):
        value = " ".join(str(record.get(key) or "").split())
        if value:
            values.append(value)
    return tuple(dict.fromkeys(values))


def load_detail_records(manifest: Mapping[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for source in manifest.get("sources") or []:
        if not isinstance(source, Mapping):
            continue
        artifact_dir = root / str(source.get("artifact_dir") or "")
        report_name = str(source.get("unified_report_file") or "unified-opportunity-report.json")
        path = artifact_dir / report_name
        if not path.exists():
            continue
        payload = _read_json(path)
        for raw in payload.get("records") or []:
            if not isinstance(raw, Mapping):
                continue
            item = dict(raw)
            for identity in _identity_values(item):
                records.setdefault(identity, item)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args()

    checkpoint = _read_json(args.checkpoint)
    manifest = _read_json(args.manifest)
    details = load_detail_records(manifest, args.root)
    report = build_daily_analysis(checkpoint, detail_records=details)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_summary.write_text(render_daily_analysis(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
