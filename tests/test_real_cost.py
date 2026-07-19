import pytest

from opportunity_engine.ods.real_cost import RealCostEngine, RealCostInputs


def test_calculates_complete_cost_with_fee_rate_and_vat() -> None:
    report = RealCostEngine().calculate(
        RealCostInputs(
            purchase_price_nok=10000,
            auction_fee_rate=0.15,
            vat_status="excluded",
            transport_nok=1000,
            dismantling_nok=500,
            storage_nok=250,
            repair_nok=300,
            cleaning_nok=100,
            selling_cost_nok=200,
            other_cost_nok=150,
            contingency_rate=0.10,
        )
    )

    assert report.auction_fee_nok == 1500.0
    assert report.vat_nok == 2875.0
    assert report.direct_costs_nok == 2500.0
    assert report.contingency_nok == 1687.5
    assert report.total_cost_nok == 18562.5
    assert report.is_complete is True
    assert report.missing_fields == ()


def test_unknown_values_are_not_assumed_zero() -> None:
    report = RealCostEngine().calculate(
        RealCostInputs(purchase_price_nok=5000, vat_status="unknown")
    )

    assert report.total_cost_nok is None
    assert "auction_fee_nok" in report.missing_fields
    assert "vat_status" in report.missing_fields
    assert "transport_nok" in report.missing_fields
    assert report.is_complete is False
    assert report.warnings


def test_included_vat_adds_no_extra_vat() -> None:
    report = RealCostEngine().calculate(
        RealCostInputs(
            purchase_price_nok=1000,
            auction_fee_nok=100,
            vat_status="included",
            transport_nok=0,
            dismantling_nok=0,
            storage_nok=0,
            repair_nok=0,
            cleaning_nok=0,
            selling_cost_nok=0,
            other_cost_nok=0,
        )
    )

    assert report.vat_nok == 0.0
    assert report.total_cost_nok == 1100.0
    assert report.is_complete is True


def test_rejects_negative_values_and_percentage_style_rates() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        RealCostInputs(purchase_price_nok=-1)
    with pytest.raises(ValueError, match="decimal"):
        RealCostInputs(purchase_price_nok=1, auction_fee_rate=15)
