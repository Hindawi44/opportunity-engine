#!/usr/bin/env python3
"""Build an operational health snapshot for discovery and pipeline stages."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_object(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def status_label(status: str) -> str:
    normalized = status.upper()
    if normalized == "SUCCESS":
        return "HEALTHY"
    if normalized in {"RUNNING", "DRY_RUN"}:
        return "DEGRADED"
    return "FAILED"


def _source_rows(source_funnel: dict) -> list[dict]:
    raw_sources = source_funnel.get("sources", [])
    if not isinstance(raw_sources, list):
        return []

    rows: list[dict] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        active = bool(item.get("active"))
        configured = bool(item.get("configured"))
        error = item.get("error")
        fetched = int(item.get("fetched") or 0)
        status = str(item.get("status") or "unknown")

        # A configured, active source must not be reported healthy when it errors
        # or when its status explicitly indicates failure.
        failed = active and configured and (
            bool(error) or status.lower() in {"failed", "error", "unavailable"}
        )
        if failed:
            health = "FAILED"
        elif active and configured:
            health = "HEALTHY"
        else:
            health = "BLOCKED" if "awaiting" in status.lower() else "INACTIVE"

        rows.append({
            "source": item.get("source"),
            "status": status,
            "health": health,
            "active": active,
            "configured": configured,
            "item_count": fetched,
            "error": error,
            "required_configuration": item.get("required_configuration", []),
            "access_mode": item.get("access_mode"),
        })
    return rows


def build_health(pipeline: dict, source_funnel: dict, registry: dict, generated_at: str) -> dict:
    stages = []
    raw_stages = pipeline.get("stages", [])
    if isinstance(raw_stages, list):
        for item in raw_stages:
            if not isinstance(item, dict):
                continue
            stages.append({
                "name": item.get("name"),
                "status": item.get("status"),
                "health": status_label(str(item.get("status") or "UNKNOWN")),
                "exit_code": item.get("exit_code"),
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
            })

    source_rows = _source_rows(source_funnel)
    pipeline_status = str(pipeline.get("status") or "UNKNOWN")
    failed_sources = sum(1 for item in source_rows if item["health"] == "FAILED")
    overall = status_label(pipeline_status)
    if failed_sources:
        overall = "DEGRADED" if overall == "HEALTHY" else overall

    return {
        "schema_version": 2,
        "generated_at": generated_at,
        "overall_health": overall,
        "pipeline_status": pipeline_status,
        "failed_stage": pipeline.get("failed_stage"),
        "stage_count": len(stages),
        "source_count": len(source_rows),
        "failed_source_count": failed_sources,
        "registry_record_count": registry.get("record_count", 0),
        "registry_status_counts": registry.get("status_counts", {}),
        "stages": stages,
        "sources": source_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-status", default="data/pipeline_run_status.json")
    parser.add_argument("--source-funnel", default="data/source_funnel.json")
    parser.add_argument("--registry", default="data/opportunity_registry.json")
    parser.add_argument("--output", default="data/discovery_health.json")
    args = parser.parse_args()
    payload = build_health(
        load_object(Path(args.pipeline_status)),
        load_object(Path(args.source_funnel)),
        load_object(Path(args.registry)),
        datetime.now(timezone.utc).isoformat(),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "overall_health": payload["overall_health"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
