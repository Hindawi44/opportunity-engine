#!/usr/bin/env python3
"""Build review-only commercial-anchor outcome learning from current Exact-Lot artifacts."""
from __future__ import annotations

import argparse

from opportunity_engine.discovery.commercial_anchor_outcome_learning import (
    write_commercial_anchor_outcome_learning,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    report = write_commercial_anchor_outcome_learning(
        input_root=args.input_root,
        output_dir=args.output_dir,
        run_id=args.run_id,
    )
    print(f"Status: {report['status']}")
    print(f"Current observations: {report['current_run_observation_count']}")
    print(f"Candidate success patterns: {report['candidate_success_pattern_count']}")
    print(f"Proven success patterns: {report['proven_success_pattern_count']}")
    print(f"Repeated zero patterns: {report['repeated_zero_pattern_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
