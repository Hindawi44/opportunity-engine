"""Select one active opportunity for conservative daily analysis.

The result contains source-backed facts and explicit missing commercial inputs.
No costs, resale values, profit, or maximum purchase price are estimated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "one-opportunity-daily-analysis-1.0"
ACTIVE_STAGE = "ACTIVE_OPPORTUNITY"


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _metadata(record: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        return {}
    value = record.get("metadata")
    return value if isinstance(value, Mapping) else {}


def _candidates(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for raw in checkpoint.get("deduplicated_opportunities") or []:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        if _text(item.get("listing_status")).upper() != "ACTIVE":
            continue
        if _text(item.get("workflow_status")).upper() != ACTIVE_STAGE:
            continue
        if item.get("analysis_eligible") is not True:
            continue
        found.append(item)
    return found


def select_one(checkpoint: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, int]:
    candidates = _candidates(checkpoint)
    if not candidates:
        return None, "NO_ACTIVE_ANALYSIS_ELIGIBLE_OPPORTUNITY", 0
    action = checkpoint.get("next_human_action")
    preferred = _text(action.get("opportunity_identity")) if isinstance(action, Mapping) else ""
    for item in candidates:
        if preferred and _text(item.get("opportunity_identity")) == preferred:
            return item, "CHECKPOINT_NEXT_HUMAN_ACTION", len(candidates)
    candidates.sort(
        key=lambda item: (
            item.get("top5_eligible") is not True,
            -(_number(item.get("discovery_score")) or 0.0),
            _text(item.get("opportunity_identity")),
        )
    )
    return candidates[0], "DETERMINISTIC_ACTIVE_OPPORTUNITY_RANK", len(candidates)


def _tasks(candidate: Mapping[str, Any], detail: Mapping[str, Any] | None) -> list[str]:
    values: list[str] = []
    for source in (candidate, _metadata(detail)):
        raw = source.get("analysis_tasks") if isinstance(source, Mapping) else None
        if isinstance(raw, str) and _text(raw):
            values.append(_text(raw))
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend(_text(item) for item in raw if _text(item))
    if values:
        return list(dict.fromkeys(values))
    return [
        "confirm quantity and condition from the exact item page",
        "calculate final payable price including auction fees and VAT",
        "calculate pickup or delivery logistics",
        "document conservative resale-market evidence",
    ]


def _source_price(candidate: Mapping[str, Any], detail: Mapping[str, Any] | None) -> dict[str, Any]:
    detail = detail or {}
    currency = _text(detail.get("currency") or candidate.get("currency")).upper() or None
    for key, kind in (("bid_price", "CURRENT_BID"), ("price", "SOURCE_PRICE")):
        amount = _number(detail.get(key))
        if amount is not None:
            return {"amount": amount, "currency": currency, "kind": kind, "is_final_payable_price": False}
    for key, kind in (("bid_price_nok", "CURRENT_BID"), ("price_nok", "SOURCE_PRICE")):
        amount = _number(candidate.get(key))
        if amount is not None:
            return {"amount": amount, "currency": "NOK", "kind": kind, "is_final_payable_price": False}
    return {"amount": None, "currency": currency, "kind": "UNKNOWN", "is_final_payable_price": False}


def _explicit_values(detail: Mapping[str, Any] | None) -> dict[str, Any]:
    metadata = _metadata(detail)
    comparables = metadata.get("resale_comparables")
    count = len(comparables) if isinstance(comparables, Sequence) and not isinstance(comparables, (str, bytes)) else 0
    return {
        "final_payable_price_nok": _number(metadata.get("final_payable_price_nok")),
        "transport_nok": _number(metadata.get("transport_nok")),
        "conservative_resale_nok": _number(metadata.get("conservative_resale_nok")),
        "resale_comparable_count": count,
    }


def build_daily_analysis(
    checkpoint: Mapping[str, Any],
    *,
    detail_records: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    selected, reason, count = select_one(checkpoint)
    timestamp = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    safety = {
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    if selected is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": timestamp,
            "execution_mode": "MANUAL_READ_ONLY",
            "selection_status": "VALID_ZERO_RESULT",
            "selection_reason": reason,
            "eligible_candidate_count": 0,
            "selected_opportunity": None,
            "analysis_state": "NO_ACTIVE_OPPORTUNITY",
            "known_facts": {},
            "required_analysis_tasks": [],
            "financial_readiness": {
                "ready_for_financial_engine": False,
                "total_cost_nok": None,
                "conservative_resale_nok": None,
                "expected_profit_nok": None,
                "maximum_purchase_price_nok": None,
            },
            "next_human_action": {"action": "WAIT_FOR_ACTIVE_OPPORTUNITY", "opportunity_identity": None},
            **safety,
        }

    identity = _text(selected.get("opportunity_identity"))
    detail = (detail_records or {}).get(identity)
    explicit = _explicit_values(detail)
    ready = (
        explicit["final_payable_price_nok"] is not None
        and explicit["transport_nok"] is not None
        and explicit["conservative_resale_nok"] is not None
        and explicit["resale_comparable_count"] > 0
    )
    tasks = [] if ready else _tasks(selected, detail)
    source_names = selected.get("source_names") or []
    if isinstance(source_names, str):
        source_names = [source_names]
    action = "RUN_FINANCIAL_DECISION_ENGINE" if ready else "COMPLETE_ANALYSIS_INPUTS"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp,
        "execution_mode": "MANUAL_READ_ONLY",
        "selection_status": "SELECTED",
        "selection_reason": reason,
        "eligible_candidate_count": count,
        "selected_opportunity": {
            "opportunity_identity": identity,
            "workflow_status": ACTIVE_STAGE,
            "listing_status": "ACTIVE",
            "discovery_score": _number(selected.get("discovery_score")) or 0.0,
        },
        "analysis_state": "READY_FOR_FINANCIAL_ENGINE" if ready else "REQUIRES_COMMERCIAL_INPUTS",
        "known_facts": {
            "title": selected.get("title") or (detail or {}).get("title"),
            "market_code": selected.get("market_code"),
            "source_names": list(source_names),
            "source_url": selected.get("canonical_url") or (detail or {}).get("source_url"),
            "source_price": _source_price(selected, detail),
            "quantity": _number((detail or {}).get("quantity")),
            "location": (detail or {}).get("location"),
            "verified": True,
            "top5_eligible": selected.get("top5_eligible") is True,
            "analysis_eligible": True,
        },
        "required_analysis_tasks": tasks,
        "explicit_analysis_values": explicit,
        "financial_readiness": {
            "ready_for_financial_engine": ready,
            "total_cost_nok": None,
            "conservative_resale_nok": explicit["conservative_resale_nok"],
            "expected_profit_nok": None,
            "maximum_purchase_price_nok": None,
        },
        "next_human_action": {"action": action, "opportunity_identity": identity, "required_analysis_tasks": tasks},
        "source_detail_found": detail is not None,
        **safety,
    }


def render_daily_analysis(report: Mapping[str, Any]) -> str:
    lines = ["تحليل فرصة اليوم — مخزون الملابس", f"الوقت: {report.get('generated_at')}"]
    if report.get("selection_status") == "VALID_ZERO_RESULT":
        lines += ["الحالة: لا توجد فرصة نشطة مؤهلة للتحليل اليوم.", "القرار الحالي: انتظار فرصة مؤهلة."]
        return "\n".join(lines) + "\n"
    facts = report.get("known_facts") or {}
    price = facts.get("source_price") or {}
    lines += [
        f"الحالة: {report.get('analysis_state')}",
        f"الفرصة: {facts.get('title')}",
        f"السوق: {facts.get('market_code')} | المصدر: {', '.join(facts.get('source_names') or [])}",
        f"السعر الحالي: {price.get('amount') if price.get('amount') is not None else 'غير متوفر'} {price.get('currency') or ''}",
        f"الكمية: {facts.get('quantity') if facts.get('quantity') is not None else 'غير متوفرة'}",
        f"الموقع: {facts.get('location') or 'غير متوفر'}",
        f"الإجراء البشري الوحيد: {(report.get('next_human_action') or {}).get('action')}",
    ]
    tasks = report.get("required_analysis_tasks") or []
    if tasks:
        lines.append("المطلوب قبل الحساب المالي:")
        lines.extend(f"- {task}" for task in tasks)
    lines.append("لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.")
    return "\n".join(lines) + "\n"
