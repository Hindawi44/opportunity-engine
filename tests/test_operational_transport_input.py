from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.costs import build_operational_landed_cost_export
from opportunity_engine.logistics import (
    TransportEstimateError,
    build_operational_transport_export,
)
from opportunity_engine.markets import MarketProfileV1


ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = ROOT / "data" / "decision_intelligence.json"
BUYER_PATH = ROOT / "config" / "buyers" / "mahmoud_namsos_v1.json"
MARKET_PATH = ROOT / "config" / "markets" / "no_v1.json"


def _decision_payload() -> dict:
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _buyer() -> BuyerProfileV1:
    return BuyerProfileV1.from_path(BUYER_PATH)


def _market() -> MarketProfileV1:
    return MarketProfileV1.from_path(MARKET_PATH)


def _landed_payload() -> dict:
    return build_operational_landed_cost_export(_decision_payload(), _buyer())


def _transport_component(landed_payload: dict) -> dict:
    return next(
        component
        for component in landed_payload["landed_cost_estimate"]["components"]
        if component["component_id"] == "transport"
    )


def test_real_operational_selection_builds_unknown_transport_input() -> None:
    landed = _landed_payload()
    export = build_operational_transport_export(landed, _buyer(), _market())

    assert export["selection_status"] == "SELECTED"
    source = export["source_opportunity"]
    transport_input = export["transport_input"]
    snapshot = export["transport_snapshot"]
    assert source is not None
    assert transport_input is not None
    assert snapshot is not None

    assert source["opportunity_id"] == landed["source_opportunity"]["opportunity_id"]
    assert source["final_decision"] == landed["source_opportunity"]["final_decision"]
    assert source["opportunity_score"] == landed["source_opportunity"]["opportunity_score"]
    assert transport_input["origin"] == {
        "country_code": "NO",
        "city": landed["source_opportunity"]["source_city"],
        "postal_code": None,
        "coordinates": None,
    }
    assert transport_input["destination"] == _buyer().location
    assert transport_input["shipment"] == {
        "cargo_type": "UNKNOWN",
        "weight_kg": None,
        "volume_m3": None,
        "pallet_count": None,
        "package_count": None,
        "item_count": None,
        "longest_length_m": None,
    }
    assert transport_input["transport_mode"] == "UNKNOWN"
    assert transport_input["quote"]["status"] == "UNKNOWN"
    assert snapshot["transport_status"] == "REQUIRES_SHIPMENT_INPUTS"
    assert snapshot["transport_cost_range"] is None
    assert snapshot["landed_cost_input_readiness"]["ready"] is False


def test_listing_title_is_not_parsed_into_shipment_measurements() -> None:
    landed = _landed_payload()
    assert "800kg" in landed["source_opportunity"]["title"]

    export = build_operational_transport_export(landed, _buyer(), _market())

    shipment = export["transport_input"]["shipment"]
    assert shipment["weight_kg"] is None
    assert shipment["item_count"] is None
    assert shipment["longest_length_m"] is None


def test_structured_logistics_values_are_copied_without_derivation() -> None:
    landed = deepcopy(_landed_payload())
    source = landed["source_opportunity"]
    source.update(
        {
            "source_country_code": "NO",
            "source_postal_code": "3110",
            "cargo_type": "PALLETIZED",
            "weight_kg": 800,
            "volume_m3": 3.2,
            "pallet_count": 2,
            "package_count": None,
            "item_count": 4,
            "longest_length_m": 2.0,
            "loading_required": True,
            "unloading_required": True,
            "forklift_required": None,
            "tail_lift_required": True,
            "dismantling_required": False,
            "transport_mode": "CARRIER",
        }
    )

    export = build_operational_transport_export(landed, _buyer(), _market())
    snapshot = export["transport_snapshot"]

    assert snapshot["origin"]["postal_code"] == "3110"
    assert snapshot["shipment"]["weight_kg"] == 800
    assert snapshot["shipment"]["volume_m3"] == 3.2
    assert snapshot["shipment"]["pallet_count"] == 2
    assert snapshot["shipment"]["item_count"] == 4
    assert snapshot["transport_mode"] == "CARRIER"
    assert snapshot["handling"]["tail_lift_required"] is True
    assert snapshot["transport_status"] == "READY_FOR_MANUAL_QUOTE"
    assert snapshot["transport_cost_range"] is None


def test_estimated_landed_transport_component_becomes_transport_quote() -> None:
    landed = deepcopy(_landed_payload())
    component = _transport_component(landed)
    component.update(
        {
            "status": "ESTIMATED",
            "economic_treatment": "ECONOMIC_COST",
            "required_for_qualification": True,
            "low_nok": 8000,
            "expected_nok": 11000,
            "high_nok": 15000,
            "source_ref": "manual-transport-estimate:test",
            "notes": ["Manual estimate based on seller-provided shipment details."],
        }
    )

    export = build_operational_transport_export(landed, _buyer(), _market())
    snapshot = export["transport_snapshot"]

    assert snapshot["transport_status"] == "ESTIMATE_AVAILABLE"
    assert snapshot["confidence"] == "MEDIUM"
    assert snapshot["transport_cost_range"] == {
        "low_nok": 8000,
        "expected_nok": 11000,
        "high_nok": 15000,
    }
    assert snapshot["landed_cost_input_readiness"]["ready"] is True


def test_confirmed_landed_transport_component_requires_evidence() -> None:
    landed = deepcopy(_landed_payload())
    component = _transport_component(landed)
    component.update(
        {
            "status": "CONFIRMED",
            "economic_treatment": "ECONOMIC_COST",
            "required_for_qualification": True,
            "low_nok": 12000,
            "expected_nok": 12000,
            "high_nok": 12000,
            "source_ref": None,
            "notes": ["Carrier quote."],
        }
    )

    with pytest.raises(TransportEstimateError, match="requires source_ref"):
        build_operational_transport_export(landed, _buyer(), _market())


def test_zero_landed_selection_produces_zero_safe_transport_sidecar() -> None:
    landed = build_operational_landed_cost_export(
        {"decision_count": 0, "decisions": []},
        _buyer(),
    )

    export = build_operational_transport_export(landed, _buyer(), _market())

    assert export["selection_status"] == "NO_ELIGIBLE_OPPORTUNITY"
    assert export["source_opportunity"] is None
    assert export["transport_input"] is None
    assert export["transport_snapshot"] is None


def test_mismatched_buyer_is_rejected() -> None:
    landed = deepcopy(_landed_payload())
    landed["buyer_profile_id"] = "ANOTHER_BUYER"

    with pytest.raises(TransportEstimateError, match="buyer_profile_id"):
        build_operational_transport_export(landed, _buyer(), _market())


def test_cross_market_origin_is_rejected_for_domestic_profile() -> None:
    landed = deepcopy(_landed_payload())
    landed["source_opportunity"]["source_country_code"] = "SE"

    with pytest.raises(TransportEstimateError, match="outside"):
        build_operational_transport_export(landed, _buyer(), _market())


def test_snapshot_scope_keeps_official_decision_pipeline_unchanged() -> None:
    snapshot = build_operational_transport_export(
        _landed_payload(), _buyer(), _market()
    )["transport_snapshot"]

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


def test_cli_writes_operational_transport_sidecar(tmp_path: Path) -> None:
    landed_path = tmp_path / "operational-landed-cost.json"
    output_path = tmp_path / "operational-transport-input.json"
    landed_path.write_text(
        json.dumps(_landed_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_operational_transport_input.py",
            "--landed-cost",
            str(landed_path),
            "--buyer",
            str(BUYER_PATH),
            "--market",
            str(MARKET_PATH),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(result.stdout)
    assert saved["selection_status"] == "SELECTED"
    assert saved["transport_snapshot"]["transport_status"] == (
        "REQUIRES_SHIPMENT_INPUTS"
    )
    assert printed["opportunity_id"] == saved["source_opportunity"]["opportunity_id"]
    assert printed["output"] == str(output_path)
