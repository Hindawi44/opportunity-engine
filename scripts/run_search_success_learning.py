#!/usr/bin/env python3
"""Build review-only positive search learning from strict Exact-Lot evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.search_success_learning import (
    build_search_success_observation,
    update_search_success_memory,
)


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
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--tool-learning", required=True)
    parser.add_argument("--child-resolution", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--observed-at")
    parser.add_argument("--observation-output", required=True)
    parser.add_argument("--memory-output", required=True)
    parser.add_argument("--existing-memory")
    parser.add_argument("--min-independent-runs", type=int, default=2)
    args = parser.parse_args()

    observation = build_search_success_observation(
        run_id=args.run_id,
        benchmark=_load(args.benchmark),
        tool_learning_proof=_load(args.tool_learning),
        child_resolution=_load(args.child_resolution),
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

    print(f"status={observation['status']}")
    print(f"run_id={observation['run_id']}")
    print(f"observed_provider_leader={observation['observed_provider_leader']}")
    print(f"provider_preference_status={observation['provider_preference_status']}")
    print(f"successful_routes={len(observation['successful_routes'])}")
    print(f"memory_run_count={memory['run_count']}")
    print(f"replicated_routes={memory['replicated_route_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
