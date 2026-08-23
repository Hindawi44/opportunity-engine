#!/usr/bin/env python3
"""Update positive-learning memory from one strict provider route run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.provider_route_success_learning import (
    build_provider_route_success_observation,
)
from opportunity_engine.search_success_learning import update_search_success_memory


def _load(path: str | Path) -> dict:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{target} must contain a JSON object")
    return payload


def _write(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("exa",), default="exa")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--provider-verification", required=True)
    parser.add_argument("--child-resolution")
    parser.add_argument("--multihop-resolution")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--observed-at")
    parser.add_argument("--existing-memory")
    parser.add_argument("--observation-output", required=True)
    parser.add_argument("--memory-output", required=True)
    parser.add_argument("--min-independent-runs", type=int, default=2)
    args = parser.parse_args()

    if not args.child_resolution and not args.multihop_resolution:
        parser.error("one of --child-resolution or --multihop-resolution is required")

    observation = build_provider_route_success_observation(
        run_id=args.run_id,
        provider=args.provider,
        benchmark=_load(args.benchmark),
        provider_verification=_load(args.provider_verification),
        child_resolution=_load(args.child_resolution) if args.child_resolution else None,
        multihop_resolution=(
            _load(args.multihop_resolution) if args.multihop_resolution else None
        ),
        observed_at=args.observed_at,
    )
    existing = _load(args.existing_memory) if args.existing_memory else {}
    memory = update_search_success_memory(
        existing,
        observation,
        min_independent_runs=args.min_independent_runs,
    )
    _write(args.observation_output, observation)
    _write(args.memory_output, memory)

    evaluated = observation["providers"][args.provider]
    print(f"status={observation['status']}")
    print(f"scope={observation['observation_scope']}")
    print(f"evaluated_provider={observation['evaluated_provider']}")
    print(f"provider_comparison={observation['provider_preference_status']}")
    print(f"direct_exact_lots={evaluated['direct_exact_lot_count']}")
    print(f"child_exact_lots={evaluated['child_exact_lot_count']}")
    print(f"multihop_exact_lots={evaluated['multihop_exact_lot_count']}")
    print(f"successful_routes={len(observation['successful_routes'])}")
    print(f"memory_run_count={memory['run_count']}")
    print(f"replicated_routes={memory['replicated_route_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
