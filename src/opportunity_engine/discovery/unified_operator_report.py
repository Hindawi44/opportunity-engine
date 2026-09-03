"""Render the single operator-facing report over existing daily artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


JSON_FILENAME = "unified-operator-report-v1.json"
TEXT_FILENAME = "unified-operator-report-v1.txt"
MARKET_COVERAGE = ("NO", "SE", "DE", "FR", "IT", "NL")


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


def _eligible_rows(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = checkpoint.get("deduplicated_opportunities") or []
    return [
        dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("top5_eligible") is True
    ]


def _top5(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Keep checkpoint ranking while preventing one market from taking every slot.

    The compatibility checkpoint is already ordered by its canonical eligibility
    and score rules.  The first pass therefore keeps its order but takes at most
    one row per market.  Only after every represented eligible market has had a
    chance does the second pass fill remaining slots from the original ranking.
    """
    eligible = _eligible_rows(checkpoint)
    selected: list[dict[str, Any]] = []
    selected_indexes: set[int] = set()
    represented_markets: set[str] = set()

    for index, row in enumerate(eligible):
        market = str(row.get("market_code") or "").strip().upper()
        if not market or market in represented_markets:
            continue
        selected.append(row)
        selected_indexes.add(index)
        represented_markets.add(market)
        if len(selected) == 5:
            return selected

    for index, row in enumerate(eligible):
        if index in selected_indexes:
            continue
        selected.append(row)
        if len(selected) == 5:
            break
    return selected


def _stage(market: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for raw in market.get("stages") or []:
        if isinstance(raw, Mapping) and raw.get("stage") == name:
            return raw
    return {}


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _six_market_search_truth(
    runtime: Mapping[str, Any],
    pipeline: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> list[dict[str, Any]]:
    clothing = _mapping(runtime.get("clothing_inventory"))
    runtime_markets = _mapping(clothing.get("markets"))
    pipeline_markets = {
        str(raw.get("market_code") or "").strip().upper(): raw
        for raw in pipeline.get("markets") or []
        if isinstance(raw, Mapping)
    }
    checkpoint_records = [
        raw
        for raw in checkpoint.get("deduplicated_opportunities") or []
        if isinstance(raw, Mapping)
    ]
    checkpoint_market_rows = {
        str(raw.get("market_code") or "").strip().upper(): raw
        for raw in checkpoint.get("markets") or []
        if isinstance(raw, Mapping)
    }

    truth: list[dict[str, Any]] = []
    for market_code in MARKET_COVERAGE:
        runtime_market = _mapping(runtime_markets.get(market_code))
        pipeline_market = _mapping(pipeline_markets.get(market_code))
        discovery = _stage(pipeline_market, "DISCOVERY")
        verification = _stage(pipeline_market, "EXACT_LOT_VERIFICATION")
        urls = [
            str(value).strip()
            for value in runtime_market.get("exact_lot_urls") or []
            if str(value).strip()
        ]
        exact_lot_count = _int(runtime_market.get("strict_exact_lot_count"))
        if exact_lot_count == 0:
            exact_lot_count = _int(
                verification.get("verified_active_exact_lot_count")
                or verification.get("verified_exact_lot_count")
                or discovery.get("verified_exact_lot_count")
            )
        hits_received = _int(
            runtime_market.get("hits_received") or discovery.get("unified_search_hits")
        )
        checkpoint_rows = [
            raw
            for raw in checkpoint_records
            if str(raw.get("market_code") or "").strip().upper() == market_code
        ]
        checkpoint_summary = _mapping(checkpoint_market_rows.get(market_code))
        checkpoint_eligible_count = sum(
            raw.get("top5_eligible") is True for raw in checkpoint_rows
        )
        if not checkpoint_rows:
            checkpoint_eligible_count = _int(
                checkpoint_summary.get("top5_eligible_count")
            )
        checkpoint_connected = bool(checkpoint_rows or checkpoint_summary)
        truth.append(
            {
                "market_code": market_code,
                "search_status": runtime_market.get("status")
                or discovery.get("unified_search_status")
                or discovery.get("status")
                or "NO_RUNTIME_TRUTH",
                "search_hits_received": hits_received,
                "verified_exact_lot_count": exact_lot_count,
                "representative_exact_lot_url": urls[0] if urls else None,
                "commercial_checkpoint_connected": checkpoint_connected,
                "commercial_checkpoint_record_count": len(checkpoint_rows)
                or _int(checkpoint_summary.get("deduplicated_record_count")),
                "commercial_checkpoint_top5_eligible_count": checkpoint_eligible_count,
                "requires_commercial_checkpoint_connection": bool(
                    exact_lot_count > 0 and not checkpoint_connected
                ),
            }
        )
    return truth


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
    top5 = _top5(checkpoint)
    search_truth = _six_market_search_truth(runtime, pipeline, checkpoint)
    market_search_leaders = [
        {
            "market_code": row["market_code"],
            "verified_exact_lot_count": row["verified_exact_lot_count"],
            "representative_exact_lot_url": row["representative_exact_lot_url"],
            "commercial_checkpoint_connected": row["commercial_checkpoint_connected"],
        }
        for row in search_truth
        if row["representative_exact_lot_url"]
    ]
    disconnected = [
        row for row in search_truth if row["requires_commercial_checkpoint_connection"]
    ]
    return {
        "schema_version": "unified-operator-report-1.1",
        "generated_at": pipeline.get("generated_at") or checkpoint.get("generated_at"),
        "status": central.get("status") or runtime.get("status") or "SUCCESS",
        "authority": "UNIFIED_OPERATOR_REPORT_V1",
        "market_coverage": list(MARKET_COVERAGE),
        "pipeline_contract": pipeline.get("pipeline_contract"),
        "markets": pipeline.get("markets") or [],
        "six_market_search_truth": search_truth,
        "market_search_leaders": market_search_leaders,
        "commercial_checkpoint_gap_markets": [
            row["market_code"] for row in disconnected
        ],
        "unconnected_verified_exact_lot_count": sum(
            row["verified_exact_lot_count"] for row in disconnected
        ),
        "source_execution_counts": source_counts,
        "opportunity_status_counts": status_counts,
        "top5_eligible_count": int(checkpoint.get("top5_eligible_count") or 0),
        "top5_opportunities": top5,
        "top5_market_coverage": list(
            dict.fromkeys(
                str(row.get("market_code") or "").strip().upper()
                for row in top5
                if str(row.get("market_code") or "").strip()
            )
        ),
        "top5_market_diversity_enforced": True,
        "top5_scope": "COMMERCIAL_CHECKPOINT_ELIGIBLE_ONLY",
        "search_truth_is_not_commercial_qualification": True,
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
    search_truth = [
        row
        for row in report.get("six_market_search_truth") or []
        if isinstance(row, Mapping)
    ]
    search_counts = " | ".join(
        f"{row.get('market_code')}: {row.get('verified_exact_lot_count', 0)}"
        for row in search_truth
    )
    disconnected = " | ".join(
        str(value) for value in report.get("commercial_checkpoint_gap_markets") or []
    )
    top5_markets = " | ".join(
        str(value) for value in report.get("top5_market_coverage") or []
    )
    search_leader_lines = [
        (
            f"مرشح البحث {row.get('market_code')}: "
            f"{row.get('representative_exact_lot_url')} "
            f"(Exact-Lot: {row.get('verified_exact_lot_count', 0)})"
        )
        for row in report.get("market_search_leaders") or []
        if isinstance(row, Mapping) and row.get("representative_exact_lot_url")
    ]
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
        f"Exact-Lot موثّق حسب السوق: {search_counts or 'لا يوجد'}",
        f"توزيع Top 5: {top5_markets or 'لا يوجد مؤهل'}",
        (
            "بحث موحّد غير مربوط بعد بالقائمة التجارية: "
            f"{disconnected or 'لا يوجد'}"
        ),
        *search_leader_lines,
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
