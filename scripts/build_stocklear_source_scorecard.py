#!/usr/bin/env python3
"""Build the evidence-only Stocklear source promotion scorecard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.source_promotion_scorecard import build_source_promotion_scorecard


def _load(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-candidates", default="docs/benchmarks/source-discovery-shadow-2026-08-22-result.json")
    parser.add_argument("--live-proof", default="docs/benchmarks/source-shadow-live-validation-2026-08-22-result.json")
    parser.add_argument("--access-proof", default="docs/benchmarks/stocklear-access-stability-2026-08-22-result.json")
    parser.add_argument("--independent-live-discovery-rounds", type=int, required=True)
    parser.add_argument("--live-source-candidate-count", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = build_source_promotion_scorecard(
        _load(args.source_candidates),
        _load(args.live_proof),
        _load(args.access_proof),
        source_domain="joblot.stocklear.eu",
        independent_live_discovery_rounds=args.independent_live_discovery_rounds,
        live_source_candidate_count=args.live_source_candidate_count,
    )
    report["evidence"] = {
        "source_candidates_path": args.source_candidates,
        "live_proof_path": args.live_proof,
        "access_proof_path": args.access_proof,
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "promotion_readiness_score": report["promotion_readiness_score"],
        "blocking_reasons": report["blocking_reasons"],
        "automatic_promotion": report["automatic_promotion"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
