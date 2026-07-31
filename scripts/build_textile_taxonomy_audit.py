#!/usr/bin/env python3
"""Build a detached Textile & Sewing Opportunity Taxonomy V1 audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.textile_taxonomy import build_textile_taxonomy_audit


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = next(
            (
                payload[key]
                for key in ("candidates", "results", "opportunities")
                if isinstance(payload.get(key), list)
            ),
            [payload],
        )
    else:
        raise ValueError("input JSON must be an object or a list")

    if not all(isinstance(candidate, dict) for candidate in candidates):
        raise ValueError("every candidate must be a JSON object")
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify public candidates using the textile/sewing taxonomy."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    audit = build_textile_taxonomy_audit(_load_candidates(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "candidate_count": audit["candidate_count"],
                "included_count": audit["included_count"],
                "rejected_count": audit["rejected_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
