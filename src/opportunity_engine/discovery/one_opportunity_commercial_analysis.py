"""Apply explicit commercial inputs to one selected daily opportunity.

This module never estimates missing values. It accepts one manually reviewed,
analysis-eligible opportunity, validates explicit NOK inputs, and delegates the
profit decision to the existing conservative ODS decision engine.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from opportunity_engine.ods.market_pricing import MarketPriceReport
from opportunity_engine.ods.opportunity_profit import OpportunityProfitDecisionEngine
from opportunity_engine.ods.real_cost import RealCostReport

SCHEMA_VERSION = "one-opportunity-commercial-analysis-1.0"


class CommercialInputError(ValueError):
    """Raised when explicit commercial inputs are invalid or target the wrong lot."""


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: object, *, allow_zero: bool) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CommercialInputError(f"invalid numeric value: {value!r}") from exc
    if parsed < 0 or (parsed == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise CommercialInputError(f"value must be {qualifier}: {value!r}")
    return parsed


def _integer(value: object, *, minimum: int = 0) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise CommercialInputError(f"invalid integer value: {value!r}") from exc
    if parsed < minimum:
        raise CommercialInputError(f"integer must be at least {minimum}: {value!r}")
    return parsed


def _normalise_zero_source_price(report: dict[str, Any]) -> None:
    facts = report.get("known_facts")
    if not isinstance(facts, dict):
        return
    price = facts.get("source_price")
    if not isinstance(price, dict):
        return
    amount = price.get("amount")
    try:
        parsed = float(amount)
    except (TypeError, ValueError):
        return
    if parsed != 0:
        return
    price["amount"] = None
    price["kind"] = "UNKNOWN"
    price["zero_value_treated_as_missing"] = True


def _market_confidence(comparable_count: int) -> str:
    if comparable_count < 1:
        return "insufficient"
    if comparable_count < 3:
        return "low"
    if comparable_count < 6:
        return "medium"
    return "high"


def _required_tasks(
    *,
    quantity_condition_confirmed: bool,
    final_payable_price_nok: float | None,
    transport_nok: float | None,
    conservative_resale_nok: float | None,
    resale_comparable_count: int | None,
) -> list[str]:
    tasks: list[str] = []
    if not quantity_condition_confirmed:
        tasks.append("confirm quantity and condition from the exact item page")
    if final_payable_price_nok is None:
        tasks.append("enter final payable price including auction fees and VAT")
    if transport_nok is None:
        tasks.append("enter pickup or delivery cost in NOK")
    if conservative_resale_nok is None:
        tasks.append("enter conservative total resale value in NOK")
    if not resale_comparable_count:
        tasks.append("enter the number of documented resale comparables")
    return tasks


def apply_commercial_inputs(
    daily_analysis: Mapping[str, Any],
    *,
    opportunity_identity: str,
    quantity_condition_confirmed: bool,
    final_payable_price_nok: object,
    transport_nok: object,
    conservative_resale_nok: object,
    resale_comparable_count: object,
    review_note: str = "",
) -> dict[str, Any]:
    """Validate explicit inputs and produce one conservative financial decision."""
    report = deepcopy(dict(daily_analysis))
    report["schema_version"] = SCHEMA_VERSION
    _normalise_zero_source_price(report)

    if report.get("selection_status") != "SELECTED":
        raise CommercialInputError("latest checkpoint has no selected active opportunity")
    selected = report.get("selected_opportunity")
    if not isinstance(selected, Mapping):
        raise CommercialInputError("selected opportunity is missing")

    expected_identity = _text(selected.get("opportunity_identity"))
    supplied_identity = _text(opportunity_identity)
    if not supplied_identity:
        raise CommercialInputError("opportunity_identity is required")
    if supplied_identity != expected_identity:
        raise CommercialInputError(
            "commercial inputs do not match the currently selected opportunity"
        )

    final_payable = _number(final_payable_price_nok, allow_zero=False)
    transport = _number(transport_nok, allow_zero=True)
    conservative_resale = _number(conservative_resale_nok, allow_zero=False)
    comparable_count = _integer(resale_comparable_count, minimum=0)

    tasks = _required_tasks(
        quantity_condition_confirmed=quantity_condition_confirmed,
        final_payable_price_nok=final_payable,
        transport_nok=transport,
        conservative_resale_nok=conservative_resale,
        resale_comparable_count=comparable_count,
    )

    report["commercial_inputs"] = {
        "opportunity_identity": supplied_identity,
        "quantity_condition_confirmed": quantity_condition_confirmed,
        "final_payable_price_nok": final_payable,
        "transport_nok": transport,
        "conservative_resale_nok": conservative_resale,
        "resale_comparable_count": comparable_count or 0,
        "review_note": _text(review_note) or None,
        "input_basis": "MANUAL_EXPLICIT_INPUT",
    }
    report["explicit_analysis_values"] = {
        "final_payable_price_nok": final_payable,
        "transport_nok": transport,
        "conservative_resale_nok": conservative_resale,
        "resale_comparable_count": comparable_count or 0,
    }
    report["required_analysis_tasks"] = tasks

    if tasks:
        report["analysis_state"] = "REQUIRES_COMMERCIAL_INPUTS"
        report["financial_readiness"] = {
            "ready_for_financial_engine": False,
            "total_cost_nok": None,
            "conservative_resale_nok": conservative_resale,
            "expected_profit_nok": None,
            "roi": None,
            "margin_on_resale": None,
            "maximum_final_payable_price_nok": None,
            "maximum_source_bid_nok": None,
        }
        report["financial_decision"] = None
        report["next_human_action"] = {
            "action": "COMPLETE_ANALYSIS_INPUTS",
            "opportunity_identity": supplied_identity,
            "required_analysis_tasks": tasks,
        }
        return report

    assert final_payable is not None
    assert transport is not None
    assert conservative_resale is not None
    assert comparable_count is not None and comparable_count > 0

    total_cost = final_payable + transport
    market = MarketPriceReport(
        opportunity_id=supplied_identity,
        comparable_count=comparable_count,
        low_price_nok=None,
        median_price_nok=None,
        high_price_nok=None,
        conservative_resale_nok=conservative_resale,
        confidence=_market_confidence(comparable_count),
        comparable_ids=tuple(f"manual-comparable:{index}" for index in range(1, comparable_count + 1)),
        warnings=(
            "Conservative resale is a manual aggregate input; individual comparable details are not stored in this version.",
        ),
    )
    costs = RealCostReport(
        purchase_price_nok=final_payable,
        auction_fee_nok=0.0,
        vat_nok=0.0,
        direct_costs_nok=round(transport, 2),
        contingency_nok=0.0,
        total_cost_nok=round(total_cost, 2),
        missing_fields=(),
        warnings=(
            "purchase_price_nok represents the entered final payable price including auction fees and VAT.",
        ),
        is_complete=True,
    )
    decision = OpportunityProfitDecisionEngine().decide(market, costs)
    decision_code = {"buy": "BUY", "monitor": "WATCH", "reject": "REJECT"}[decision.decision]
    next_action = {
        "BUY": "REVIEW_BUY_OR_BID_CANDIDATE",
        "WATCH": "WATCH_OPPORTUNITY",
        "REJECT": "REJECT_OPPORTUNITY",
    }[decision_code]

    report["analysis_state"] = "FINANCIAL_DECISION_COMPLETE"
    report["required_analysis_tasks"] = []
    report["financial_readiness"] = {
        "ready_for_financial_engine": True,
        "total_cost_nok": decision.total_cost_nok,
        "conservative_resale_nok": decision.conservative_resale_nok,
        "expected_profit_nok": decision.expected_profit_nok,
        "roi": decision.roi,
        "margin_on_resale": decision.margin_on_resale,
        "maximum_final_payable_price_nok": decision.maximum_purchase_price_nok,
        "maximum_source_bid_nok": None,
    }
    report["financial_decision"] = {
        "decision": decision_code,
        "engine_decision": decision.decision,
        "decision_label": decision.decision_label,
        "confidence": decision.confidence,
        "is_actionable": decision.is_actionable,
        "blockers": list(decision.blockers),
        "warnings": list(decision.warnings)
        + [
            "Maximum source bid is not calculated because the auction fee and VAT formula was not supplied separately."
        ],
        "reasons": list(decision.reasons),
        "maximum_total_cost_nok": decision.maximum_total_cost_nok,
        "maximum_final_payable_price_nok": decision.maximum_purchase_price_nok,
        "maximum_source_bid_nok": None,
    }
    report["next_human_action"] = {
        "action": next_action,
        "opportunity_identity": supplied_identity,
        "decision": decision_code,
    }
    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        report[key] = False
    return report


def render_commercial_analysis(report: Mapping[str, Any]) -> str:
    """Render one compact, phone-readable commercial decision."""
    facts = report.get("known_facts") or {}
    values = report.get("explicit_analysis_values") or {}
    readiness = report.get("financial_readiness") or {}
    decision = report.get("financial_decision") or {}
    lines = [
        "التحليل التجاري لفرصة واحدة — مخزون الملابس",
        f"الوقت: {report.get('generated_at')}",
        f"الفرصة: {facts.get('title') or 'غير متوفرة'}",
        f"السوق: {facts.get('market_code') or ''} | المصدر: {', '.join(facts.get('source_names') or [])}",
        f"الحالة: {report.get('analysis_state')}",
        f"السعر النهائي المدخل: {values.get('final_payable_price_nok') if values.get('final_payable_price_nok') is not None else 'غير مكتمل'} NOK",
        f"النقل/الاستلام: {values.get('transport_nok') if values.get('transport_nok') is not None else 'غير مكتمل'} NOK",
        f"إعادة البيع المحافظة: {values.get('conservative_resale_nok') if values.get('conservative_resale_nok') is not None else 'غير مكتملة'} NOK",
    ]
    if report.get("analysis_state") == "FINANCIAL_DECISION_COMPLETE":
        roi = readiness.get("roi")
        roi_text = "غير متوفر" if roi is None else f"{roi * 100:.2f}%"
        lines += [
            f"إجمالي التكلفة: {readiness.get('total_cost_nok')} NOK",
            f"الربح المتوقع: {readiness.get('expected_profit_nok')} NOK",
            f"ROI: {roi_text}",
            f"الحد الأعلى للسعر النهائي شامل الرسوم والضريبة: {readiness.get('maximum_final_payable_price_nok')} NOK",
            "الحد الأعلى للمزايدة داخل الموقع: غير محسوب دون صيغة الرسوم والضريبة منفصلة.",
            f"القرار: {decision.get('decision')} | {decision.get('decision_label')}",
            f"الثقة: {decision.get('confidence')}",
        ]
    else:
        lines.append("المعلومات الناقصة:")
        lines.extend(f"- {item}" for item in report.get("required_analysis_tasks") or [])
    lines.append(
        f"الإجراء البشري الوحيد: {(report.get('next_human_action') or {}).get('action')}"
    )
    lines.append("لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.")
    return "\n".join(lines) + "\n"
