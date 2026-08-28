import pytest

from opportunity_engine.discovery.one_opportunity_commercial_analysis import CommercialInputError
from opportunity_engine.discovery.one_opportunity_commercial_vat_basis_v1 import (
    apply_commercial_inputs_with_vat_basis,
    render_commercial_analysis_with_vat_basis,
)


OPPORTUNITY_ID = "https://ny.auksjonen.no/auksjon/torget/test/528194"


def _daily_analysis() -> dict:
    return {
        "schema_version": "one-opportunity-daily-analysis-1.0",
        "generated_at": "2026-08-28T12:00:00+00:00",
        "execution_mode": "MANUAL_READ_ONLY",
        "selection_status": "SELECTED",
        "selected_opportunity": {
            "opportunity_identity": OPPORTUNITY_ID,
            "workflow_status": "ACTIVE_OPPORTUNITY",
            "listing_status": "ACTIVE",
        },
        "analysis_state": "REQUIRES_COMMERCIAL_INPUTS",
        "known_facts": {
            "title": "Commercial VAT basis test lot",
            "market_code": "NO",
            "source_names": ["Auksjonen.no"],
            "source_price": {
                "amount": 100000.0,
                "currency": "NOK",
                "kind": "SOURCE_PRICE",
                "is_final_payable_price": False,
            },
        },
        "required_analysis_tasks": [],
        "financial_readiness": {"ready_for_financial_engine": False},
        "next_human_action": {
            "action": "COMPLETE_ANALYSIS_INPUTS",
            "opportunity_identity": OPPORTUNITY_ID,
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _apply(**overrides: object) -> dict:
    kwargs = {
        "opportunity_identity": OPPORTUNITY_ID,
        "quantity_condition_confirmed": True,
        "final_payable_price_nok": 125000,
        "recoverable_input_vat_nok": 25000,
        "transport_nok": 10000,
        "conservative_resale_nok": 250000,
        "resale_output_vat_nok": 50000,
        "resale_comparable_count": 6,
        "review_note": "Explicit VAT basis checked.",
    }
    kwargs.update(overrides)
    return apply_commercial_inputs_with_vat_basis(_daily_analysis(), **kwargs)


def test_vat_registered_style_inputs_use_net_economic_basis() -> None:
    report = _apply()

    assert report["schema_version"] == "one-opportunity-commercial-vat-basis-1.0"
    assert report["vat_basis"]["explicit"] is True
    assert report["vat_basis"]["inferred_vat_rate"] is None
    assert report["vat_basis"]["cash_final_payable_price_nok"] == 125000.0
    assert report["vat_basis"]["recoverable_input_vat_nok"] == 25000.0
    assert report["vat_basis"]["economic_acquisition_price_nok"] == 100000.0
    assert report["vat_basis"]["gross_conservative_resale_nok"] == 250000.0
    assert report["vat_basis"]["resale_output_vat_nok"] == 50000.0
    assert report["vat_basis"]["economic_resale_revenue_nok"] == 200000.0

    readiness = report["financial_readiness"]
    assert readiness["ready_for_financial_engine"] is True
    assert readiness["total_cost_nok"] == 110000.0
    assert readiness["expected_profit_nok"] == 90000.0
    assert readiness["roi"] == 0.8182
    assert readiness["maximum_final_cash_payable_price_nok"] is None
    assert readiness["maximum_economic_acquisition_price_nok"] is not None
    assert report["financial_decision"]["decision"] == "BUY"
    assert report["automatic_purchase"] is False
    assert report["automatic_bid"] is False


def test_zero_vat_adjustments_preserve_legacy_economics() -> None:
    report = _apply(
        final_payable_price_nok=7000,
        recoverable_input_vat_nok=0,
        transport_nok=1000,
        conservative_resale_nok=12000,
        resale_output_vat_nok=0,
        resale_comparable_count=3,
    )

    assert report["vat_basis"]["economic_acquisition_price_nok"] == 7000.0
    assert report["vat_basis"]["economic_resale_revenue_nok"] == 12000.0
    assert report["financial_readiness"]["total_cost_nok"] == 8000.0
    assert report["financial_readiness"]["expected_profit_nok"] == 4000.0
    assert report["financial_readiness"]["roi"] == 0.5


def test_recoverable_input_vat_cannot_exceed_cash_purchase() -> None:
    with pytest.raises(CommercialInputError, match="cannot exceed final_payable"):
        _apply(recoverable_input_vat_nok=125001)


def test_resale_output_vat_cannot_exceed_gross_resale() -> None:
    with pytest.raises(CommercialInputError, match="cannot exceed conservative_resale"):
        _apply(resale_output_vat_nok=250001)


def test_vat_inputs_are_required_not_inferred() -> None:
    with pytest.raises(CommercialInputError, match="recoverable_input_vat_nok is required"):
        _apply(recoverable_input_vat_nok="")
    with pytest.raises(CommercialInputError, match="resale_output_vat_nok is required"):
        _apply(resale_output_vat_nok="")


def test_phone_summary_distinguishes_cash_gross_and_economic_values() -> None:
    summary = render_commercial_analysis_with_vat_basis(_apply())

    assert summary.count("الإجراء البشري الوحيد:") == 1
    assert "المبلغ النقدي النهائي للشراء: 125000.0 NOK" in summary
    assert "تكلفة الاقتناء الاقتصادية: 100000.0 NOK" in summary
    assert "إعادة البيع المحافظة الإجمالية: 250000.0 NOK" in summary
    assert "إيراد إعادة البيع الاقتصادي: 200000.0 NOK" in summary
    assert "إجمالي التكلفة الاقتصادية: 110000.0 NOK" in summary
    assert "لا شراء، لا مزايدة" in summary
