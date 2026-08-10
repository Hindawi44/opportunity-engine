"""Run the bounded fabric AI advisor after supplier discovery and before river projection."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

from opportunity_engine.discovery.openai_fabric_procurement_advisor import (
    attach_advisory_to_fabric_report,
    run_openai_fabric_procurement_advisor,
)

_INSTALLED = False
AdvisorRunner = Callable[..., dict[str, Any]]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _summary(advisor: Mapping[str, Any]) -> dict[str, Any]:
    assessments = [
        dict(item)
        for item in (advisor.get("assessments") or [])
        if isinstance(item, Mapping)
    ]
    high = [item for item in assessments if item.get("review_priority") == "HIGH"]
    return {
        "status": advisor.get("status"),
        "model": advisor.get("model"),
        "selected_candidate_count": advisor.get("selected_candidate_count", 0),
        "assessment_count": advisor.get("assessment_count", len(assessments)),
        "high_priority_count": len(high),
        "api_request_count": advisor.get("api_request_count", 0),
        "top_assessments": assessments[:5],
        "overall_note": advisor.get("overall_note"),
        "model_output_is_advisory": True,
        "source_evidence_required_for_verification": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": "HUMAN_OPERATOR",
        "automatic_contact": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _render_text(advisor: Mapping[str, Any]) -> str:
    assessments = [
        dict(item)
        for item in (advisor.get("assessments") or [])
        if isinstance(item, Mapping)
    ]
    lines = [
        "OPENAI FABRIC PROCUREMENT ADVISOR",
        f"status: {advisor.get('status')}",
        f"model: {advisor.get('model')}",
        f"selected_candidate_count: {advisor.get('selected_candidate_count', 0)}",
        f"assessment_count: {advisor.get('assessment_count', len(assessments))}",
        f"api_request_count: {advisor.get('api_request_count', 0)}",
        "decision_owner: HUMAN_OPERATOR",
        "model_output_is_advisory: true",
    ]
    for index, item in enumerate(assessments[:5], start=1):
        missing = ", ".join(item.get("missing_information") or []) or "none listed"
        lines.append(
            f"{index}. {item.get('review_priority')} | {item.get('candidate_id')} | "
            f"{item.get('material_summary')} | missing={missing}"
        )
    lines += [
        "AI does not verify price, quantity, composition, shipping or MOQ unless present in source evidence.",
        "automatic_purchase: false",
    ]
    return "\n".join(lines) + "\n"


def write_daily_openai_fabric_advisor(
    output_dir: Path,
    *,
    environment: Mapping[str, str] | None = None,
    runner: AdvisorRunner = run_openai_fabric_procurement_advisor,
) -> dict[str, Any] | None:
    fabric_path = output_dir / "fabric-procurement-watch.json"
    if not fabric_path.exists():
        return None
    try:
        fabric = json.loads(fabric_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(fabric, dict):
        return None

    try:
        advisor = runner(
            fabric,
            environment=environment if environment is not None else os.environ,
        )
    except Exception as exc:
        advisor = {
            "schema_version": "openai-fabric-procurement-advisor-1.0",
            "status": "FAILED",
            "model": None,
            "selected_candidate_count": 0,
            "api_request_count": 0,
            "assessment_count": 0,
            "assessments": [],
            "overall_note": "No model advisory was produced.",
            "usage": {},
            "error": f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}",
            "model_output_is_advisory": True,
            "source_evidence_required_for_verification": True,
            "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    _write_json(output_dir / "openai-fabric-procurement-advisor.json", advisor)
    (output_dir / "openai-fabric-procurement-advisor.txt").write_text(
        _render_text(advisor), encoding="utf-8"
    )

    if advisor.get("status") == "SUCCESS":
        fabric = attach_advisory_to_fabric_report(fabric, advisor)
        _write_json(fabric_path, fabric)

    brief_path = output_dir / "domain-market-intelligence-brief.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            brief = None
        if isinstance(brief, dict):
            brief["fabric_ai_advisor"] = _summary(advisor)
            _write_json(brief_path, brief)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if text_path.exists():
        base = text_path.read_text(encoding="utf-8").rstrip()
        text_path.write_text(
            base + "\n\n## Fabric AI advisor\n" + _render_text(advisor),
            encoding="utf-8",
        )
    return advisor


def install_openai_fabric_procurement_cli_hook() -> None:
    """Register after river and before fabric so atexit runs fabric -> AI -> river."""
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py":
        return
    try:
        output_index = sys.argv.index("--output-dir")
        output_dir = Path(sys.argv[output_index + 1])
    except (ValueError, IndexError):
        return

    def _run_after_fabric_before_river() -> None:
        advisor = write_daily_openai_fabric_advisor(output_dir)
        if advisor is None:
            return
        print(
            "daily_openai_fabric_procurement_advisor:",
            json.dumps(
                {
                    "status": advisor.get("status"),
                    "selected_candidate_count": advisor.get("selected_candidate_count"),
                    "assessment_count": advisor.get("assessment_count", 0),
                    "api_request_count": advisor.get("api_request_count", 0),
                },
                sort_keys=True,
            ),
        )

    atexit.register(_run_after_fabric_before_river)
    _INSTALLED = True
