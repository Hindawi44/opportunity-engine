"""Render the single operator-facing report over existing daily artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


JSON_FILENAME = "unified-operator-report-v1.json"
TEXT_FILENAME = "unified-operator-report-v1.txt"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _human_action(
    central: Mapping[str, Any],
    domain: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    action = _mapping(central.get("primary_human_action"))
    if action:
        return {
            "authority": "CENTRAL_INTELLIGENCE",
            "action": action.get("action_type") or "NO_IMMEDIATE_ACTION",
            "target": action.get("target") or action.get("recommended_next_action"),
            "reason": action.get("reason") or "",
            "details": dict(action),
        }
    action = _mapping(domain.get("selected_human_action"))
    if action:
        return {
            "authority": "DOMAIN_MARKET_INTELLIGENCE",
            "action": action.get("action") or "NO_IMMEDIATE_ACTION",
            "target": action.get("opportunity_identity") or action.get("signal_id"),
            "reason": action.get("reason") or "",
            "details": dict(action),
        }
    action = _mapping(checkpoint.get("next_human_action"))
    return {
        "authority": "LEGACY_CHECKPOINT_FALLBACK",
        "action": action.get("action") or "NO_IMMEDIATE_ACTION",
        "target": action.get("opportunity_identity") or action.get("signal_id"),
        "reason": action.get("reason") or "",
        "details": dict(action),
    }


def _top5(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = checkpoint.get("deduplicated_opportunities") or []
    return [dict(row) for row in rows if isinstance(row, Mapping) and row.get("top5_eligible") is True][
        :5
    ]


def build_unified_operator_report(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir)
    pipeline = _load_json(root / "unified-six-market-pipeline-v1.json")
    runtime = _load_json(root / "unified-search-runtime-v1.json")
    checkpoint = _load_json(root / "multi-market-daily-checkpoint.json")
    domain = _load_json(root / "domain-market-intelligence-brief.json")
    central = _load_json(root / "central-intelligence-brief.json")
    if not pipeline or not runtime or not checkpoint:
        raise ValueError("Unified pipeline, search runtime, and checkpoint are required")

    source_counts = dict(_mapping(checkpoint.get("source_execution_counts")))
    status_counts = dict(_mapping(checkpoint.get("status_counts")))
    action = _human_action(central, domain, checkpoint)
    return {
        "schema_version": "unified-operator-report-1.0",
        "generated_at": pipeline.get("generated_at") or checkpoint.get("generated_at"),
        "status": central.get("status") or runtime.get("status") or "SUCCESS",
        "authority": "UNIFIED_OPERATOR_REPORT_V1",
        "market_coverage": ["NO", "SE", "DE", "FR", "IT", "NL"],
        "pipeline_contract": pipeline.get("pipeline_contract"),
        "markets": pipeline.get("markets") or [],
        "source_execution_counts": source_counts,
        "opportunity_status_counts": status_counts,
        "top5_eligible_count": int(checkpoint.get("top5_eligible_count") or 0),
        "top5_opportunities": _top5(checkpoint),
        "primary_human_action": action,
        "single_human_action_enforced": True,
        "compatibility_inputs": [
            "multi-market-daily-checkpoint.json",
            "domain-market-intelligence-brief.json",
            "central-intelligence-brief.json",
            "unified-six-market-pipeline-v1.json",
            "unified-search-runtime-v1.json",
        ],
        "legacy_reports_are_not_operator_authority": True,
        "decision_owner": "HUMAN_OPERATOR",
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def render_unified_operator_report(report: Mapping[str, Any]) -> str:
    sources = _mapping(report.get("source_execution_counts"))
    statuses = _mapping(report.get("opportunity_status_counts"))
    action = _mapping(report.get("primary_human_action"))
    markets = " | ".join(str(value) for value in report.get("market_coverage") or [])
    lines = [
        "تقرير المشغّل الموحد — Opportunity Engine",
        f"الوقت: {report.get('generated_at')}",
        f"التغطية: {markets}",
        (
            "المصادر: "
            f"نجاح {sources.get('SUCCESS', 0)} | "
            f"صفر صحيح {sources.get('VALID_ZERO_RESULT', 0)} | "
            f"فشل {sources.get('FAILURE', 0)} | "
            f"محجوب {sources.get('BLOCKED', 0)}"
        ),
        (
            "الفرص: "
            f"نشطة {statuses.get('ACTIVE', 0)} | "
            f"تاريخية {statuses.get('HISTORICAL', 0)} | "
            f"غير محسومة {statuses.get('UNRESOLVED', 0)} | "
            f"Top 5 مؤهل {report.get('top5_eligible_count', 0)}"
        ),
        f"الإجراء البشري الوحيد: {action.get('action', 'NO_IMMEDIATE_ACTION')}",
        f"الهدف: {action.get('target') or 'لا يوجد'}",
        f"السبب: {action.get('reason') or ''}",
        "القرار للبشر فقط؛ لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
    ]
    return "\n".join(lines) + "\n"


def write_unified_operator_report(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    report = build_unified_operator_report(root)
    json_path = root / JSON_FILENAME
    text_path = root / TEXT_FILENAME
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(render_unified_operator_report(report), encoding="utf-8")
    return {"json": json_path, "text": text_path}
