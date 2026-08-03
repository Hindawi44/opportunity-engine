#!/usr/bin/env python3
"""Persist bounded source signals and write the daily domain bulletin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.domain_market_intelligence_feed import (
    build_domain_market_intelligence_brief,
    persist_manifest_market_signals,
)
from opportunity_engine.discovery.signal_role_freshness_correction import (
    write_corrected_market_bulletin_artifacts,
)
from opportunity_engine.discovery.sweden_valuable_datasets_status_feed import (
    collect_manifest_official_signals_with_sweden_status,
)


def _load_object(path: Path, name: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--config-path", default="alembic.ini")
    args = parser.parse_args()

    checkpoint = _load_object(Path(args.checkpoint), "checkpoint")
    manifest = _load_object(Path(args.manifest), "manifest")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    official_coverage = collect_manifest_official_signals_with_sweden_status(
        manifest,
        root=args.root,
    )
    (output_dir / "official-early-signal-source-coverage.json").write_text(
        json.dumps(official_coverage, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "official_early_signal_status_counts:",
        json.dumps(official_coverage.get("status_counts") or {}, sort_keys=True),
    )

    persistence = persist_manifest_market_signals(
        manifest,
        root=args.root,
        config_path=args.config_path,
    )
    (output_dir / "domain-market-signal-persistence.json").write_text(
        json.dumps(persistence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    brief = build_domain_market_intelligence_brief(checkpoint, persistence)
    write_corrected_market_bulletin_artifacts(
        brief,
        persistence,
        json_path=output_dir / "domain-market-intelligence-brief.json",
        text_path=output_dir / "domain-market-intelligence-brief.txt",
    )
    print((output_dir / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
