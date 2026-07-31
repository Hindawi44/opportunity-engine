from copy import deepcopy
import json
from pathlib import Path

import pytest

from opportunity_engine.costs import (
    CostComponentV1,
    LandedCostEstimateError,
    LandedCostEstimateV1,
    build_landed_cost_snapshot,
)
from scripts.build_landed_cost_estimate import main as build_landed_cost_main


def _component(
    component_id: str,
    *,
    status: str,
    treatment: str,
    required: bool = True,
    low: int | float | None = None,
    expected: int | float | None = None,
    high: int | float | None = None,
    source_ref: str | None = None,
    notes: list[str] | None = None,
) -> dict:
    return {
        "component_id": component_id,
        "label": component_id.replace("_", " ").title(),
        "status": status,
        "economic_treatment": treatment,
        "required_for_qualification": required,
        "low_nok": low,
        "expected_nok": expected,
        "high_nok": high,
        "source_ref": source_ref,
        "notes": notes or [],
    }


def _payload(components: list[dict]) -> dict:
    return {
        "schema_version": "landed-cost-estimate-v1",
        "estimate_id": "LC-opportunity-123-NAMSOS-v1",
        "opportunity_id": "opportunity-123",
        "destination": {
            "country_code": "NO",
            "city": "Namsos",
            "postal_code": None,
            "coordinates": None,
        },
        "currency_code": "NOK",
        "components": components,
        "assumptions": [],
        "evidence_refs": [],
    }


def test_unknown_required_costs_preserve_partial_state_without_false_total() -> None:
    estimate = LandedCostEstimateV1.from_dict(
        _payload(
            [
                _component(
                    "purchase_price",
                    status="CONFIRMED",
                    treatment="ECONOMIC_COST",
                    low=50_000,
                    expected=50_000,
                    high=50_000,
                    source_ref="listing:opportunity-123:price",
                ),
                _component(
                    "platform_fee",
                    status="ESTIMATED",
                    treatment="ECONOMIC_COST",
                    low=4_000,
                    expected=5_000,
                    high=6_000,
                    notes=["Platform fee requires final auction terms."],
                ),
                _component(
                    "transport_to_namsos",
                    status="UNKNOWN",
                    treatment="UNKNOWN",
                ),
            ]
        )
    )

    snapshot = build_landed_cost_snapshot(estimate)

    assert snapshot["estimate_status"] == "PARTIAL_ESTIMATE"
    assert snapshot["confidence"] == "LOW"
    assert snapshot["known_cash_required_range"] == {
        "low_nok": 54_000,
        "expected_nok": 55_000,
        "high_nok": 56_000,
    }
    assert snapshot["complete_cash_required_range"] is None
    assert snapshot["complete_net_economic_cost_range"] is None
    assert snapshot["missing_required_inputs"] == ["transport_to_namsos"]
    assert snapshot["qualification_readiness"] == {
        "ready": False,
        "status": "REQUIRES_COST_REVIEW",
    }
    assert snapshot["destination_precision"] == "CITY_LEVEL_INPUT_ONLY"


def test_recoverable_vat_is_cash_required_but_not_net_economic_cost() -> None:
    estimate = LandedCostEstimateV1.from_dict(
        _payload(
            [
                _component(
                    "purchase_price",
                    status="CONFIRMED",
                    treatment="ECONOMIC_COST",
                    low=40_000,
                    expected=40_000,
                    high=40_000,
                    source_ref="invoice:purchase-price",
                ),
                _component(
                    "transport_to_namsos",
                    status="ESTIMATED",
                    treatment="ECONOMIC_COST",
                    low=8_000,
                    expected=10_000,
                    high=12_000,
                    notes=["Manual carrier range; no quote has been obtained."],
                ),
                _component(
                    "recoverable_vat",
                    status="ESTIMATED",
                    treatment="RECOVERABLE_CASH_OUTFLOW",
                    low=10_000,
                    expected=12_500,
                    high=15_000,
                    notes=["Illustrative input; tax treatment must be verified."],
                ),
            ]
        )
    )

    snapshot = build_landed_cost_snapshot(estimate)

    assert snapshot["estimate_status"] == "COMPLETE"
    assert snapshot["confidence"] == "MEDIUM"
    assert snapshot["complete_cash_required_range"] == {
        "low_nok": 58_000,
        "expected_nok": 62_500,
        "high_nok": 67_000,
    }
    assert snapshot["known_recoverable_cash_outflow_range"] == {
        "low_nok": 10_000,
        "expected_nok": 12_500,
        "high_nok": 15_000,
    }
    assert snapshot["complete_net_economic_cost_range"] == {
        "low_nok": 48_000,
        "expected_nok": 50_000,
        "high_nok": 52_000,
    }
    assert snapshot["qualification_readiness"]["ready"] is True


def test_known_amount_with_unknown_treatment_requires_review() -> None:
    estimate = LandedCostEstimateV1.from_dict(
        _payload(
            [
                _component(
                    "purchase_price",
                    status="CONFIRMED",
                    treatment="ECONOMIC_COST",
                    low=25_000,
                    expected=25_000,
                    high=25_000,
                    source_ref="listing:price",
                ),
                _component(
                    "tax_or_duty",
                    status="ESTIMATED",
                    treatment="UNKNOWN",
                    low=2_000,
                    expected=3_000,
                    high=4_000,
                    notes=["Economic treatment is not verified."],
                ),
            ]
        )
    )

    snapshot = build_landed_cost_snapshot(estimate)

    assert snapshot["estimate_status"] == "PARTIAL_ESTIMATE"
    assert snapshot["confidence"] == "MEDIUM"
    assert snapshot["complete_cash_required_range"] == {
        "low_nok": 27_000,
        "expected_nok": 28_000,
        "high_nok": 29_000,
    }
    assert snapshot["complete_net_economic_cost_range"] is None
    assert snapshot["unknown_economic_treatments"] == ["tax_or_duty"]


def test_not_applicable_component_is_excluded_without_blocking_completion() -> None:
    estimate = LandedCostEstimateV1.from_dict(
        _payload(
            [
                _component(
                    "purchase_price",
                    status="CONFIRMED",
                    treatment="ECONOMIC_COST",
                    low=15_000,
                    expected=15_000,
                    high=15_000,
                    source_ref="listing:price",
                ),
                _component(
                    "customs_duty",
                    status="NOT_APPLICABLE",
                    treatment="NOT_APPLICABLE",
                ),
            ]
        )
    )

    snapshot = build_landed_cost_snapshot(estimate)

    assert snapshot["estimate_status"] == "COMPLETE"
    assert snapshot["confidence"] == "HIGH"
    assert snapshot["complete_cash_required_range"] == {
        "low_nok": 15_000,
        "expected_nok": 15_000,
        "high_nok": 15_000,
    }


def test_confirmed_component_requires_exact_amount_and_evidence() -> None:
    with pytest.raises(
        LandedCostEstimateError,
        match="CONFIRMED components must use one exact amount",
    ):
        CostComponentV1.from_dict(
            _component(
                "purchase_price",
                status="CONFIRMED",
                treatment="ECONOMIC_COST",
                low=10,
                expected=11,
                high=12,
                source_ref="listing:price",
            )
        )

    with pytest.raises(
        LandedCostEstimateError,
        match="CONFIRMED components require source_ref",
    ):
        CostComponentV1.from_dict(
            _component(
                "purchase_price",
                status="CONFIRMED",
                treatment="ECONOMIC_COST",
                low=10,
                expected=10,
                high=10,
            )
        )


def test_estimated_component_requires_ordered_range_and_assumption() -> None:
    with pytest.raises(
        LandedCostEstimateError,
        match="low <= expected <= high",
    ):
        CostComponentV1.from_dict(
            _component(
                "shipping",
                status="ESTIMATED",
                treatment="ECONOMIC_COST",
                low=20,
                expected=10,
                high=30,
                notes=["Manual estimate."],
            )
        )

    with pytest.raises(
        LandedCostEstimateError,
        match="ESTIMATED components require at least one note",
    ):
        CostComponentV1.from_dict(
            _component(
                "shipping",
                status="ESTIMATED",
                treatment="ECONOMIC_COST",
                low=10,
                expected=20,
                high=30,
            )
        )


def test_duplicate_component_ids_are_rejected() -> None:
    component = _component(
        "purchase_price",
        status="CONFIRMED",
        treatment="ECONOMIC_COST",
        low=1_000,
        expected=1_000,
        high=1_000,
        source_ref="listing:price",
    )
    with pytest.raises(
        LandedCostEstimateError,
        match="component_id values must be unique",
    ):
        LandedCostEstimateV1.from_dict(_payload([component, deepcopy(component)]))


def test_scope_never_changes_decision_ranking_alerts_or_purchase() -> None:
    estimate = LandedCostEstimateV1.from_dict(
        _payload(
            [
                _component(
                    "purchase_price",
                    status="UNKNOWN",
                    treatment="UNKNOWN",
                )
            ]
        )
    )

    snapshot = build_landed_cost_snapshot(estimate)

    assert snapshot["estimate_status"] == "REQUIRES_COST_INPUTS"
    assert snapshot["confidence"] == "NONE"
    assert snapshot["scope"] == {
        "route_or_shipping_quote_lookup_enabled": False,
        "tax_or_customs_rule_lookup_enabled": False,
        "changes_final_decision": False,
        "changes_ranking": False,
        "changes_top5": False,
        "changes_alerts": False,
        "automatic_purchase_allowed": False,
    }


def test_cli_writes_auditable_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "estimate-input.json"
    output_path = tmp_path / "estimate-output.json"
    input_path.write_text(
        json.dumps(
            _payload(
                [
                    _component(
                        "purchase_price",
                        status="CONFIRMED",
                        treatment="ECONOMIC_COST",
                        low=30_000,
                        expected=30_000,
                        high=30_000,
                        source_ref="listing:price",
                    ),
                    _component(
                        "transport_to_namsos",
                        status="UNKNOWN",
                        treatment="UNKNOWN",
                    ),
                ]
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_landed_cost_estimate.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert build_landed_cost_main() == 0
    snapshot = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)

    assert snapshot["estimate_status"] == "PARTIAL_ESTIMATE"
    assert snapshot["complete_cash_required_range"] is None
    assert printed["estimate_status"] == "PARTIAL_ESTIMATE"
    assert printed["qualification_status"] == "REQUIRES_COST_REVIEW"
    assert printed["output"] == str(output_path)
