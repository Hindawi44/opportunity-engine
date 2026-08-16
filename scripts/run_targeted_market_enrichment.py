#!/usr/bin/env python3
"""Run paid/model-driven market enrichment only after a zero-cost eligibility gate."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.hunt_case_targeted_followup import (
    attach_targeted_followup_intelligence,
    run_hunt_case_targeted_followup,
    write_hunt_case_targeted_followup_artifacts,
)
from opportunity_engine.discovery.openai_hunt_case_enrichment import (
    attach_hunt_case_intelligence,
    run_openai_hunt_case_enrichment,
    select_hunt_signals,
    write_openai_hunt_case_artifacts,
)


SCHEMA_VERSION = "targeted-market-enrichment-1.0"
SAFETY_KEYS = (
    "automatic_contact",
    "automatic_bid",
    "automatic_purchase",
    "automatic_payment",
)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_read_only(payload: Mapping[str, Any], label: str) -> None:
    for key in SAFETY_KEYS:
        if payload.get(key) is not False:
            raise ValueError(f"{label} changed read-only safety: {key}")


def build_targeted_enrichment_gate(brief: Mapping[str, Any]) -> dict[str, Any]:
    """Use the same deterministic selector as OpenAI Hunt before exposing secrets."""
    selected = select_hunt_signals(brief, max_signals=10)
    signal_ids = [str(item.get("signal_id") or "") for item in selected]
    should_run = bool(selected)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": brief.get("generated_at"),
        "status": "RUN_TARGETED_ENRICHMENT" if should_run else "SKIPPED_NO_ELIGIBLE_HUNT_SIGNALS",
        "should_run_targeted_enrichment": should_run,
        "eligible_signal_count": len(selected),
        "eligible_signal_ids": signal_ids,
        "gate_uses_paid_api": False,
        "gate_selector": "OPENAI_HUNT_SELECT_HUNT_SIGNALS",
        "market_coverage": ["NO", "SE", "DE"],
        "commercial_analysis_stage": "SEPARATE_MANUAL_WORKFLOW",
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _render_gate(gate: Mapping[str, Any]) -> str:
    return (
        "TARGETED MARKET ENRICHMENT GATE\n"
        f"status: {gate.get('status')}\n"
        f"eligible_signal_count: {gate.get('eligible_signal_count', 0)}\n"
        f"should_run_targeted_enrichment: {str(bool(gate.get('should_run_targeted_enrichment'))).lower()}\n"
        "gate_uses_paid_api: false\n"
        "commercial_analysis_stage: SEPARATE_MANUAL_WORKFLOW\n"
        "automatic_purchase: false\n"
    )


def run_targeted_enrichment(
    brief: Mapping[str, Any],
    *,
    output_dir: Path,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    gate = build_targeted_enrichment_gate(brief)
    _write_json(output_dir / "targeted-enrichment-gate.json", gate)
    (output_dir / "targeted-enrichment-gate.txt").write_text(
        _render_gate(gate), encoding="utf-8"
    )
    if not gate["should_run_targeted_enrichment"]:
        return gate

    env = dict(os.environ if environment is None else environment)
    hunt = run_openai_hunt_case_enrichment(brief, environment=env)
    write_openai_hunt_case_artifacts(
        hunt,
        json_path=output_dir / "openai-hunt-case-enrichment.json",
        text_path=output_dir / "openai-hunt-case-enrichment.txt",
    )
    _assert_read_only(hunt, "OpenAI hunt")

    followup = run_hunt_case_targeted_followup(hunt, brief, environment=env)
    write_hunt_case_targeted_followup_artifacts(
        followup,
        json_path=output_dir / "hunt-case-targeted-followup.json",
        text_path=output_dir / "hunt-case-targeted-followup.txt",
    )
    _assert_read_only(followup, "targeted follow-up")

    enriched = attach_hunt_case_intelligence(brief, hunt)
    enriched = attach_targeted_followup_intelligence(enriched, followup)
    enriched["cost_isolation"] = {
        "schema_version": "daily-cost-isolation-1.0",
        "stage": "TARGETED_ENRICHMENT",
        "targeted_enrichment_enabled": True,
        "upstream_core_reused": True,
        "daily_source_discovery_rerun": False,
        "commercial_analysis_stage": "SEPARATE_MANUAL_WORKFLOW",
    }
    _assert_read_only(enriched, "targeted enriched brief")
    _write_json(output_dir / "targeted-domain-market-intelligence-brief.json", enriched)

    result = {
        **gate,
        "status": "TARGETED_ENRICHMENT_COMPLETE",
        "openai_hunt_status": hunt.get("status"),
        "openai_api_request_count": int(hunt.get("api_request_count") or 0),
        "openai_estimated_cost_usd": float(hunt.get("estimated_cost_usd") or 0.0),
        "targeted_followup_status": followup.get("status"),
        "targeted_brave_request_count": int(followup.get("search_request_count") or 0),
        "evidence_candidate_count": int(followup.get("evidence_candidate_count") or 0),
    }
    _write_json(output_dir / "targeted-market-enrichment-summary.json", result)
    (output_dir / "targeted-market-enrichment-summary.txt").write_text(
        "TARGETED MARKET ENRICHMENT\n"
        f"status: {result['status']}\n"
        f"eligible_signal_count: {result['eligible_signal_count']}\n"
        f"openai_api_request_count: {result['openai_api_request_count']}\n"
        f"openai_estimated_cost_usd: ${result['openai_estimated_cost_usd']:.6f}\n"
        f"targeted_brave_request_count: {result['targeted_brave_request_count']}\n"
        f"evidence_candidate_count: {result['evidence_candidate_count']}\n"
        "automatic_purchase: false\n",
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    brief = _load_object(Path(args.brief), "domain market intelligence brief")
    _assert_read_only(brief, "upstream core brief")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gate = build_targeted_enrichment_gate(brief)
    _write_json(output_dir / "targeted-enrichment-gate.json", gate)
    (output_dir / "targeted-enrichment-gate.txt").write_text(
        _render_gate(gate), encoding="utf-8"
    )
    if args.gate_only:
        print(json.dumps(gate, ensure_ascii=False, sort_keys=True))
        return 0

    result = run_targeted_enrichment(brief, output_dir=output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
