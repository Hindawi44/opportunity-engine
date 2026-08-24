#!/usr/bin/env python3
"""CLI for Search Experiment Execution Bridge V1."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.search_experiment_execution_bridge_v1 import (
    execute_search_experiment_spec,
    replay_or_ingest_pending_experiment,
    select_search_experiment_spec,
    write_json,
)


def _read(path: str | Path, *, optional: bool = False) -> dict[str, Any]:
    target = Path(path)
    if optional and not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {target}")
    return dict(payload)


def _from_mind_forge(args: argparse.Namespace) -> int:
    task = _read(args.teaching_task)
    creative = _read(args.creative_result)
    final_rank = _read(args.final_rank)
    spec = select_search_experiment_spec(
        teaching_task=task,
        creative_result=creative,
        final_rank=final_rank,
    )
    if spec.get("status") != "READY":
        write_json(
            args.output,
            {
                "schema_version": "search-experiment-execution-bridge-1.0",
                "status": spec.get("status"),
                "spec": spec,
                "shadow_only": True,
                "production_mutation": False,
            },
        )
        print(f"status={spec.get('status')}")
        return 0

    result = execute_search_experiment_spec(
        spec,
        exa_api_key=os.environ.get("EXA_API_KEY", ""),
        run_id=args.run_id,
    )
    write_json(args.output, result)
    if args.pending_output:
        write_json(args.pending_output, result)
    print(f"status={result['status']}")
    print(f"outcome={result['outcome']}")
    print(f"successful_route={str(result['successful_route']).lower()}")
    print(f"experiment_fingerprint={result['experiment_fingerprint']}")
    return 0


def _checkpoint(args: argparse.Namespace) -> int:
    pending = _read(args.pending)
    memory = _read(args.memory, optional=True)
    registry = _read(args.rule_registry, optional=True)
    result = replay_or_ingest_pending_experiment(
        pending_result=pending,
        existing_memory=memory,
        checkpoint_run_id=args.run_id,
        exa_api_key=os.environ.get("EXA_API_KEY", ""),
        rule_registry=registry,
    )
    updated_memory = result.get("memory")
    if not isinstance(updated_memory, Mapping):
        raise ValueError("bridge checkpoint result did not return Unified Memory V2")
    write_json(args.memory, updated_memory)
    audit = {key: value for key, value in result.items() if key != "memory"}
    write_json(args.output, audit)
    print(f"status={audit['status']}")
    print(f"network_search_executed={str(audit.get('network_search_executed', False)).lower()}")
    print(f"experiment_fingerprint={audit.get('experiment_fingerprint')}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    proposed = sub.add_parser("from-mind-forge")
    proposed.add_argument("--teaching-task", required=True)
    proposed.add_argument("--creative-result", required=True)
    proposed.add_argument("--final-rank", required=True)
    proposed.add_argument("--run-id", required=True)
    proposed.add_argument("--output", required=True)
    proposed.add_argument("--pending-output")
    proposed.set_defaults(func=_from_mind_forge)

    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--pending", required=True)
    checkpoint.add_argument("--memory", required=True)
    checkpoint.add_argument("--rule-registry", required=True)
    checkpoint.add_argument("--run-id", required=True)
    checkpoint.add_argument("--output", required=True)
    checkpoint.set_defaults(func=_checkpoint)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
