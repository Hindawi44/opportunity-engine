"""VAT-aware wrapper for one-opportunity commercial decisions.

The existing commercial decision engine remains authoritative for ROI and
profit policy. This wrapper changes only the financial basis fed into that
engine: acquisition and resale are converted from explicit cash/gross amounts
to explicit economic amounts after user-supplied VAT adjustments.

No VAT rate, recoverability status, or tax treatment is inferred here.
"""
from __future__ import annotations

from typing import Any, Mapping

from opportunity_engine.discovery.one_opportunity_commercial_analysis import (
    CommercialInputError,
    apply_commercial_inputs,
)

SCHEMA_VERSION = "one-opportunity-commercial-vat-basis-1.0"


def _number(value: object, *, name: str, allow_zero: bool) -> float:
    if value in (None, ""):
        raise CommercialInputError(f"{name} is required for explicit VAT basis")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CommercialInputError(f"invalid numeric value for {name}: {value!r}") from exc
    if parsed < 0 or (parsed == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise CommercialInputError(f"{name} must be {qualifier}: {value!r}")
    return parsed


def apply_commercial_inputs_with_vat_basis(
    daily_analysis: Mapping[str, Any],
    *,
    opportunity_identity: str,
    quantity_condition_confirmed: bool,
    final_payable_price_nok: object,
    recoverable_input_vat_nok: object,
    transport_nok: object,
    conservative_resale_nok: object,
    resale_output_vat_nok: object,
    resale_comparable_count: object,
    review_note: str = "",
) -> dict[str, Any]:
    """Apply explicit cash/gross values and run the decision on net economics."""
    cash_final_payable = _number(
        final_payable_price_nok,
        name="final_payable_price_nok",
        allow_zero=False,
    )
    recoverable_input_vat = _number(
        recoverable_input_vat_nok,
        name="recoverable_input_vat_nok",
        allow_zero=True,
    )
    gross_resale = _number(
        conservative_resale_nok,
        name="conservative_resale_nok",
        allow_zero=False,
    )
    resale_output_vat = _number(
        resale_output_vat_nok,
        name="resale_output_vat_nok",
        allow_zero=True,
    )

    if recoverable_input_vat > cash_final_payable:
        raise CommercialInputError(
            "recoverable_input_vat_nok cannot exceed final_payable_price_nok"
        )
    if resale_output_vat > gross_resale:
        raise CommercialInputError(
            "resale_output_vat_nok cannot exceed conservative_resale_nok"
        )

    economic_acquisition = round(cash_final_payable - recoverable_input_vat, 2)
    economic_resale = round(gross_resale - resale_output_vat, 2)
    if economic_acquisition <= 0:
        raise CommercialInputError("economic acquisition price must remain positive")
    if economic_resale <= 0:
        raise CommercialInputError("economic resale revenue must remain positive")

    report = apply_commercial_inputs(
        daily_analysis,
        opportunity_identity=opportunity_identity,
        quantity_condition_confirmed=quantity_condition_confirmed,
        final_payable_price_nok=economic_acquisition,
        transport_nok=transport_nok,
        conservative_resale_nok=economic_resale,
        resale_comparable_count=resale_comparable_count,
        review_note=review_note,
    )
    report["schema_version"] = SCHEMA_VERSION
    report["vat_basis"] = {
        "explicit": True,
        "inferred_vat_rate": None,
        "cash_final_payable_price_nok": cash_final_payable,
        "recoverable_input_vat_nok": recoverable_input_vat,
        "economic_acquisition_price_nok": economic_acquisition,
        "gross_conservative_resale_nok": gross_resale,
        "resale_output_vat_nok": resale_output_vat,
        "economic_resale_revenue_nok": economic_resale,
        "decision_basis": "ECONOMIC_NET_OF_EXPLICIT_VAT",
    }

    commercial_inputs = report.get("commercial_inputs")
    if isinstance(commercial_inputs, dict):
        commercial_inputs.update(
            {
                "final_payable_price_nok": cash_final_payable,
                "recoverable_input_vat_nok": recoverable_input_vat,
                "economic_acquisition_price_nok": economic_acquisition,
                "conservative_resale_nok": gross_resale,
                "resale_output_vat_nok": resale_output_vat,
                "economic_resale_revenue_nok": economic_resale,
                "input_basis": "MANUAL_EXPLICIT_VAT_BASIS",
            }
        )

    explicit_values = report.get("explicit_analysis_values")
    if isinstance(explicit_values, dict):
        explicit_values.update(
            {
                "final_payable_price_nok": cash_final_payable,
                "recoverable_input_vat_nok": recoverable_input_vat,
                "economic_acquisition_price_nok": economic_acquisition,
                "conservative_resale_nok": gross_resale,
                "resale_output_vat_nok": resale_output_vat,
                "economic_resale_revenue_nok": economic_resale,
            }
        )

    readiness = report.get("financial_readiness")
    if isinstance(readiness, dict):
        maximum_economic = readiness.get("maximum_final_payable_price_nok")
        readiness.update(
            {
                "cash_final_payable_price_nok": cash_final_payable,
                "recoverable_input_vat_nok": recoverable_input_vat,
                "economic_acquisition_price_nok": economic_acquisition,
                "gross_conservative_resale_nok": gross_resale,
                "resale_output_vat_nok": resale_output_vat,
                "economic_resale_revenue_nok": economic_resale,
                "total_cost_basis": "ECONOMIC_NET_OF_RECOVERABLE_INPUT_VAT",
                "resale_basis": "ECONOMIC_NET_OF_EXPLICIT_OUTPUT_VAT",
                "maximum_economic_acquisition_price_nok": maximum_economic,
                "maximum_final_cash_payable_price_nok": None,
            }
        )

    decision = report.get("financial_decision")
    if isinstance(decision, dict):
        maximum_economic = decision.get("maximum_final_payable_price_nok")
        warnings = list(decision.get("warnings") or [])
        warnings.append(
            "Maximum cash payable price is not inferred from the economic maximum because recoverable VAT may vary with the final purchase price."
        )
        decision.update(
            {
                "maximum_economic_acquisition_price_nok": maximum_economic,
                "maximum_final_cash_payable_price_nok": None,
                "decision_basis": "ECONOMIC_NET_OF_EXPLICIT_VAT",
                "warnings": warnings,
            }
        )

    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        report[key] = False
    return report


def render_commercial_analysis_with_vat_basis(report: Mapping[str, Any]) -> str:
    """Render one compact VAT-aware, phone-readable commercial decision."""
    facts = report.get("known_facts") or {}
    vat = report.get("vat_basis") or {}
    values = report.get("explicit_analysis_values") or {}
    readiness = report.get("financial_readiness") or {}
    decision = report.get("financial_decision") or {}
    lines = [
        "التحليل التجاري لفرصة واحدة — أساس ضريبي صريح",
        f"الوقت: {report.get('generated_at')}",
        f"الفرصة: {facts.get('title') or 'غير متوفرة'}",
        f"السوق: {facts.get('market_code') or ''} | المصدر: {', '.join(facts.get('source_names') or [])}",
        f"الحالة: {report.get('analysis_state')}",
        f"المبلغ النقدي النهائي للشراء: {vat.get('cash_final_payable_price_nok')} NOK",
        f"VAT شراء قابل للاسترداد — مدخل صريح: {vat.get('recoverable_input_vat_nok')} NOK",
        f"تكلفة الاقتناء الاقتصادية: {vat.get('economic_acquisition_price_nok')} NOK",
        f"النقل/الاستلام: {values.get('transport_nok') if values.get('transport_nok') is not None else 'غير مكتمل'} NOK",
        f"إعادة البيع المحافظة الإجمالية: {vat.get('gross_conservative_resale_nok')} NOK",
        f"VAT إعادة البيع — مدخل صريح: {vat.get('resale_output_vat_nok')} NOK",
        f"إيراد إعادة البيع الاقتصادي: {vat.get('economic_resale_revenue_nok')} NOK",
    ]
    if report.get("analysis_state") == "FINANCIAL_DECISION_COMPLETE":
        roi = readiness.get("roi")
        roi_text = "غير متوفر" if roi is None else f"{roi * 100:.2f}%"
        lines += [
            f"إجمالي التكلفة الاقتصادية: {readiness.get('total_cost_nok')} NOK",
            f"الربح المتوقع: {readiness.get('expected_profit_nok')} NOK",
            f"ROI الاقتصادي: {roi_text}",
            f"الحد الأعلى لتكلفة الاقتناء الاقتصادية: {readiness.get('maximum_economic_acquisition_price_nok')} NOK",
            "الحد الأعلى للدفع النقدي النهائي: غير محسوب دون ربط VAT بالسعر النهائي.",
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
