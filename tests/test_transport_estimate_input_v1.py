from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from opportunity_engine.logistics import (
    TransportEstimateError,
    TransportEstimateInputV1,
    build_transport_estimate_snapshot,
)


def _payload() -> dict:
    return {
        "schema_version": "transport-estimate-input-v1",
        "estimate_id": "transport-unified-auksjonen-614288-to-mahmoud-namsos-v1",
        "opportunity_id": "unified-auksjonen-614288",
        "origin": {
            "country_code": "NO",
            "city": "Tønsberg",
            "postal_code": None,
            "coordinates": None,
        },
        "destination": {
            "country_code": "NO",
            "city": "Namsos",
            "postal_code": None,
            "coordinates": None,
        },
        "shipment": {
            "cargo_type": "UNKNOWN",
            "weight_kg": None,
            "volume_m3": None,
            "pallet_count": None,
            "package_count": None,
            "item_count": None,
            "longest_length_m": None,
        },
        "handling": {
            "loading_required": None,
            "unloading_required": None,
            "forklift_required": None,
            "tail_lift_required": None,
            "dismantling_required": None,
        },
        "transport_mode": "UNKNOWN",
        "quote": {
            "status": "UNKNOWN",
            "currency_code": "NOK",
            "low_nok": None,
            "expected_nok": None,
            "high_nok": None,
            "source_ref": None,
            "notes": [],
        },
        "assumptions": [
            "No map, route, carrier, or external-price lookup was performed."
        ],
        "evidence_refs": [
            "data/decision_intelligence.json#unified-auksjonen-614288:city"
        ],
    }


def _manual_quote_ready_payload() -> dict:
    payload = _payload()
    payload["shipment"].update(
        {
            "cargo_type": "BULKY",
            "item_count": 4,
            "longest_length_m": 2.0,
        }
    )
    payload["handling"] = {
        "loading_required": True,
        "unloading_required": True,
        "forklift_required": None,
        "tail_lift_required": None,
        "dismantling_required": False,
    }
    payload["transport_mode"] = "CARRIER"
    return payload


def test_unknown_shipment_is_not_converted_to_zero() -> None:
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(_payload())
    )

    assert snapshot["transport_status"] == "REQUIRES_SHIPMENT_INPUTS"
    assert snapshot["confidence"] == "LOW"
    assert snapshot["route_precision"] == "CITY_LEVEL_INPUT_ONLY"
    assert snapshot["transport_cost_range"] is None
    assert snapshot["landed_cost_input_readiness"] == {
        "ready": False,
        "status": "TRANSPORT_COMPONENT_PENDING",
    }
    assert "shipment.cargo_type" in snapshot["missing_inputs"]
    assert "shipment.one_of_weight_volume_pallet_package_item_or_length" in snapshot[
        "missing_inputs"
    ]


def test_missing_origin_city_blocks_route_readiness() -> None:
    payload = _payload()
    payload["origin"]["city"] = None
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(payload)
    )

    assert snapshot["transport_status"] == "REQUIRES_ROUTE_INPUTS"
    assert snapshot["confidence"] == "NONE"
    assert snapshot["route_precision"] == "INCOMPLETE"
    assert "origin.city" in snapshot["missing_inputs"]


def test_known_shipment_becomes_ready_for_manual_quote() -> None:
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(_manual_quote_ready_payload())
    )

    assert snapshot["transport_status"] == "READY_FOR_MANUAL_QUOTE"
    assert snapshot["confidence"] == "LOW"
    assert snapshot["known_shipment_metrics"] == ["item_count", "longest_length_m"]
    assert snapshot["transport_cost_range"] is None
    assert snapshot["landed_cost_input_readiness"]["ready"] is False


def test_estimated_manual_quote_exposes_range() -> None:
    payload = _manual_quote_ready_payload()
    payload["quote"] = {
        "status": "ESTIMATED",
        "currency_code": "NOK",
        "low_nok": 8000,
        "expected_nok": 11000,
        "high_nok": 15000,
        "source_ref": None,
        "notes": ["Manual estimate based on declared bulky-item inputs."],
    }
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(payload)
    )

    assert snapshot["transport_status"] == "ESTIMATE_AVAILABLE"
    assert snapshot["confidence"] == "MEDIUM"
    assert snapshot["transport_cost_range"] == {
        "low_nok": 8000,
        "expected_nok": 11000,
        "high_nok": 15000,
    }
    assert snapshot["landed_cost_input_readiness"] == {
        "ready": True,
        "status": "TRANSPORT_COMPONENT_READY",
    }


def test_confirmed_quote_requires_exact_amount_and_source() -> None:
    payload = _manual_quote_ready_payload()
    payload["quote"] = {
        "status": "CONFIRMED",
        "currency_code": "NOK",
        "low_nok": 12000,
        "expected_nok": 12000,
        "high_nok": 12000,
        "source_ref": "carrier-quote:2026-07-31-001",
        "notes": ["Carrier quote supplied manually."],
    }
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(payload)
    )

    assert snapshot["transport_status"] == "CONFIRMED_QUOTE"
    assert snapshot["confidence"] == "HIGH"
    assert snapshot["transport_cost_range"]["expected_nok"] == 12000

    payload["quote"]["source_ref"] = None
    with pytest.raises(TransportEstimateError, match="requires source_ref"):
        TransportEstimateInputV1.from_dict(payload)


def test_confirmed_quote_rejects_range() -> None:
    payload = _manual_quote_ready_payload()
    payload["quote"] = {
        "status": "CONFIRMED",
        "currency_code": "NOK",
        "low_nok": 10000,
        "expected_nok": 12000,
        "high_nok": 14000,
        "source_ref": "carrier-quote:test",
        "notes": [],
    }
    with pytest.raises(TransportEstimateError, match="one exact amount"):
        TransportEstimateInputV1.from_dict(payload)


def test_estimated_quote_requires_assumption_note() -> None:
    payload = _manual_quote_ready_payload()
    payload["quote"] = {
        "status": "ESTIMATED",
        "currency_code": "NOK",
        "low_nok": 1000,
        "expected_nok": 2000,
        "high_nok": 3000,
        "source_ref": None,
        "notes": [],
    }
    with pytest.raises(TransportEstimateError, match="assumption note"):
        TransportEstimateInputV1.from_dict(payload)


def test_not_applicable_transport_requires_reason_and_is_ready() -> None:
    payload = _payload()
    payload["quote"] = {
        "status": "NOT_APPLICABLE",
        "currency_code": "NOK",
        "low_nok": None,
        "expected_nok": None,
        "high_nok": None,
        "source_ref": "seller-terms:free-delivery",
        "notes": ["Seller provides documented free delivery to Namsos."],
    }
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(payload)
    )

    assert snapshot["transport_status"] == "TRANSPORT_NOT_APPLICABLE"
    assert snapshot["confidence"] == "HIGH"
    assert snapshot["transport_cost_range"] is None
    assert snapshot["landed_cost_input_readiness"]["ready"] is True


def test_unknown_quote_cannot_contain_zero_or_amounts() -> None:
    payload = _payload()
    payload["quote"].update({"low_nok": 0, "expected_nok": 0, "high_nok": 0})
    with pytest.raises(TransportEstimateError):
        TransportEstimateInputV1.from_dict(payload)


def test_snapshot_scope_keeps_decision_pipeline_unchanged() -> None:
    snapshot = build_transport_estimate_snapshot(
        TransportEstimateInputV1.from_dict(_manual_quote_ready_payload())
    )
    assert snapshot["scope"] == {
        "map_or_route_lookup_enabled": False,
        "carrier_quote_lookup_enabled": False,
        "external_price_lookup_enabled": False,
        "automatic_distance_calculation_enabled": False,
        "changes_final_decision": False,
        "changes_ranking": False,
        "changes_top5": False,
        "changes_alerts": False,
        "automatic_purchase_allowed": False,
    }


def test_cli_writes_snapshot(tmp_path: Path) -> None:
    input_path = tmp_path / "transport-input.json"
    output_path = tmp_path / "transport-output.json"
    input_path.write_text(
        json.dumps(_manual_quote_ready_payload(), ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_transport_estimate.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    snapshot = json.loads(output_path.read_text(encoding="utf-8"))
    assert snapshot["transport_status"] == "READY_FOR_MANUAL_QUOTE"
    assert snapshot["destination"]["city"] == "Namsos"
