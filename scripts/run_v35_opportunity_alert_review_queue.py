#!/usr/bin/env python3
"""Build one V3.5 review queue report from evaluated opportunities."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.opportunity_review_queue import update_review_queue


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/validation/v3.0-multi-opportunity-ranking.json")
    parser.add_argument("--state", default="data/monitoring/v3.5-review-queue-state.json")
    parser.add_argument("--report", default="data/validation/v3.5-opportunity-alert-review-queue.json")
    parser.add_argument("--run-at", default="2026-07-24T12:00:00Z")
    args = parser.parse_args()

    payload = _read(Path(args.input), {})
    candidates = payload.get("rankings") if isinstance(payload, dict) else []
    candidates = candidates if isinstance(candidates, list) else []
    state_path = Path(args.state)
    report, next_state = update_review_queue(candidates, _read(state_path, {}), run_at=args.run_at)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state_path.write_text(json.dumps(next_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
