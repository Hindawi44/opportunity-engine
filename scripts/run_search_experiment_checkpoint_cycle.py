#!/usr/bin/env python3
"""Run at most one Search Experiment Bridge execution inside a daily checkpoint."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.search_experiment_execution_bridge_v1 import (
    MAX_EXECUTIONS_PER_FINGERPRINT,
    execute_search_experiment_spec,
    merge_experiment_result_into_memory,
    write_json,
)
from opportunity_engine.search_experiment_route_attribution_v1 import (
    apply_route_attribution_gate,
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _read(path: str | Path, *, optional: bool = False) -> dict[str, Any]:
    target = Path(path)
    if optional and not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {target}")
    return dict(payload)


def _route_source_identity(slot_id: str) -> str:
    return f"search-experiment:{slot_id.casefold()}"


def _pattern_key(spec: Mapping[str, Any]) -> str:
    return "|".join(
        (
            "ROUTE_SUCCESS",
            _upper(spec.get("market_code")),
            _upper(spec.get("project_domain")),
            _text(spec.get("provider")).casefold(),
            _upper(spec.get("route")),
            _text(spec.get("route_source_identity")).casefold(),
        )
    )


def _route_status(memory: Mapping[str, Any], spec: Mapping[str, Any]) -> str:
    key = _pattern_key(spec)
    for pattern in _rows(memory.get("patterns")):
        if _text(pattern.get("pattern_key")) != key:
            continue
        if pattern.get("converted_to_rule") is True:
            return "FIXED_RULE_ACTIVE"
        return _upper(pattern.get("pattern_status"))
    return ""


def _origins(memory: Mapping[str, Any], fingerprint: str) -> set[str]:
    return {
        _text(_mapping(row.get("latest_metadata")).get("origin_experiment_run_id"))
        for row in _rows(memory.get("evidence_memory"))
        if _text(_mapping(row.get("latest_metadata")).get("experiment_fingerprint")) == fingerprint
        and _text(_mapping(row.get("latest_metadata")).get("origin_experiment_run_id"))
    }


def _executed_today(memory: Mapping[str, Any], fingerprint: str) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    for row in _rows(memory.get("evidence_memory")):
        metadata = _mapping(row.get("latest_metadata"))
        if _text(metadata.get("experiment_fingerprint")) != fingerprint:
            continue
        for observation in _rows(row.get("run_observations")):
            observed = _text(observation.get("observed_at"))
            if observed.startswith(today):
                return True
    return False


def _specs_from_memory(memory: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_fingerprint: dict[str, dict[str, Any]] = {}
    for row in _rows(memory.get("evidence_memory")):
        if _upper(row.get("evidence_kind")) != "MARKET_OBSERVATION":
            continue
        if _upper(row.get("result_type")) != "SEARCH_EXPERIMENT":
            continue
        metadata = _mapping(row.get("latest_metadata"))
        fingerprint = _text(metadata.get("experiment_fingerprint"))
        slot_id = _upper(metadata.get("slot_id"))
        if not fingerprint or not slot_id:
            continue
        by_fingerprint[fingerprint] = {
            "schema_version": "search-experiment-spec-1.0",
            "status": "READY",
            "experiment_fingerprint": fingerprint,
            "teaching_task_id": None,
            "teaching_task_kind": "DETERMINISTIC_REPROOF",
            "selected_idea_id": None,
            "selected_idea_rank": None,
            "selected_idea_title": None,
            "market_code": _upper(row.get("market_code")),
            "project_domain": _upper(row.get("project_domain")),
            "slot_id": slot_id,
            "provider": _text(row.get("provider")).casefold(),
            "query": _text(row.get("query")),
            "route": _upper(row.get("route")),
            "route_source_identity": _route_source_identity(slot_id),
            "max_search_requests": 1,
            "max_results": 5,
            "max_independent_executions": MAX_EXECUTIONS_PER_FINGERPRINT,
            "shadow_only": True,
            "project_domain_gate_enforced": True,
            "automatic_query_activation": False,
            "automatic_provider_activation": False,
            "automatic_source_promotion": False,
            "automatic_code_change": False,
            "production_query_mutation": False,
            "production_mutation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    return [by_fingerprint[key] for key in sorted(by_fingerprint)]


def _eligible_existing(memory: Mapping[str, Any]) -> dict[str, Any] | None:
    for spec in _specs_from_memory(memory):
        fingerprint = _text(spec.get("experiment_fingerprint"))
        status = _route_status(memory, spec)
        if status in {"PROVEN", "FIXED_RULE_ACTIVE"}:
            continue
        if len(_origins(memory, fingerprint)) >= MAX_EXECUTIONS_PER_FINGERPRINT:
            continue
        if _executed_today(memory, fingerprint):
            continue
        return spec
    return None


def _pending_spec(fast_memory: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = fast_memory.get("pending_search_experiment_spec")
    if not isinstance(raw, Mapping):
        return None
    spec = dict(raw)
    if _upper(spec.get("status")) != "READY":
        return None
    return spec


def run_checkpoint_cycle(
    *,
    fast_memory: Mapping[str, Any],
    existing_memory: Mapping[str, Any],
    run_id: str,
    exa_api_key: str,
    rule_registry: Mapping[str, Any],
) -> dict[str, Any]:
    memory = dict(existing_memory)
    pending = _pending_spec(fast_memory)
    selected: dict[str, Any] | None = None
    selection_reason = ""

    if pending is not None:
        fingerprint = _text(pending.get("experiment_fingerprint"))
        status = _route_status(memory, pending)
        if (
            status not in {"PROVEN", "FIXED_RULE_ACTIVE"}
            and len(_origins(memory, fingerprint)) < MAX_EXECUTIONS_PER_FINGERPRINT
            and not _executed_today(memory, fingerprint)
        ):
            selected = pending
            selection_reason = "NEW_MIND_FORGE_SPEC" if not _origins(memory, fingerprint) else "MIND_FORGE_SPEC_REPROOF"

    if selected is None:
        selected = _eligible_existing(memory)
        if selected is not None:
            selection_reason = "UNIFIED_MEMORY_DETERMINISTIC_REPROOF"

    if selected is None:
        return {
            "schema_version": "search-experiment-checkpoint-cycle-1.0",
            "status": "VALID_ZERO_NO_ELIGIBLE_EXPERIMENT",
            "network_search_executed": False,
            "memory": memory,
            "automatic_query_activation": False,
            "automatic_provider_activation": False,
            "production_mutation": False,
            "automatic_contact": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    raw_result = execute_search_experiment_spec(
        selected,
        exa_api_key=exa_api_key,
        run_id=run_id,
    )
    result = apply_route_attribution_gate(raw_result)
    updated = merge_experiment_result_into_memory(
        existing_memory=memory,
        result=result,
        checkpoint_run_id=run_id,
        rule_registry=rule_registry,
    )
    fingerprint = _text(selected.get("experiment_fingerprint"))
    return {
        "schema_version": "search-experiment-checkpoint-cycle-1.0",
        "status": "EXECUTED_AND_LEARNED",
        "selection_reason": selection_reason,
        "network_search_executed": True,
        "experiment_fingerprint": fingerprint,
        "execution_count_after": len(_origins(updated, fingerprint)),
        "execution_cap": MAX_EXECUTIONS_PER_FINGERPRINT,
        "experiment_outcome": result.get("outcome"),
        "successful_route": result.get("successful_route"),
        "verified_result_count": result.get("successful_result_count", 0),
        "verified_result_domains": result.get("verified_result_domains", []),
        "route_attribution_gate_enforced": result.get("route_attribution_gate_enforced", False),
        "route_attribution_gate_status": result.get("route_attribution_gate_status"),
        "route_attribution_slot_id": result.get("route_attribution_slot_id"),
        "route_attribution_rejected_count": result.get("route_attribution_rejected_count", 0),
        "memory": updated,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast-memory", required=True)
    parser.add_argument("--unified-memory", required=True)
    parser.add_argument("--rule-registry", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    fast_memory = _read(args.fast_memory, optional=True)
    memory = _read(args.unified_memory, optional=True)
    registry = _read(args.rule_registry, optional=True)
    report = run_checkpoint_cycle(
        fast_memory=fast_memory,
        existing_memory=memory,
        run_id=args.run_id,
        exa_api_key=os.environ.get("EXA_API_KEY", ""),
        rule_registry=registry,
    )
    updated = report.pop("memory")
    write_json(args.unified_memory, updated)
    write_json(args.output, report)
    print(f"status={report['status']}")
    print("network_search_executed=" + str(report.get("network_search_executed", False)).lower())
    if report.get("experiment_fingerprint"):
        print(f"experiment_fingerprint={report['experiment_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
