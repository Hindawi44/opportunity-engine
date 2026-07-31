from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.costs import build_operational_landed_cost_export
from opportunity_engine.logistics import (
    build_operational_transport_export,
    build_shipment_evidence_queue,
)
from opportunity_engine.markets import MarketProfileV1


ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = ROOT / "data" / "decision_intelligence.json"
BUYER_PATH = ROOT / "config" / "buyers" / "mahmoud_namsos_v1.json"
MARKET_PATH = ROOT / "config" / "markets" / "no_v1.json"


def _decisions() -> dict:
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _buyer() -> BuyerProfileV1:
    return BuyerProfileV1.from_path(BUYER_PATH)


def _market() -> MarketProfileV1:
    return MarketProfileV1.from_path(MARKET_PATH)


def _landed() -> dict:
    return build_operational_landed_cost_export(_decisions(), _buyer())


def _transport(landed: dict | None = None) -> dict:
    return build_operational_transport_export(
        landed or _landed(),
        _buyer(),
        _market(),
    )


def _task(queue: dict, task_type: str) -> dict:
    return next(task for task in queue["tasks"] if task["task_type"] == task_type)


def test_real_operational_transport_builds_blocking_evidence_queue() -> None:
    transport = _transport()
    queue = build_shipment_evidence_queue(transport)

    assert queue["selection_status"] == "SELECTED"
    assert queue["workflow_status"] == "EVIDENCE_REQUIRED_FOR_QUOTE"
    assert queue["next_action"] == "COLLECT_SHIPMENT_EVIDENCE"
    assert queue["source_opportunity"]["opportunity_id"] == transport[
        "source_opportunity"
    ]["opportunity_id"]
    assert queue["source_opportunity"]["final_decision"] == transport[
        "source_opportunity"
    ]["final_decision"]
    assert queue["source_opportunity"]["opportunity_score"] == transport[
        "source_opportunity"
    ]["opportunity_score"]

    task_types = {task["task_type"] for task in queue["tasks"]}
    assert task_types == {
        "CARGO_TYPE",
        "SHIPMENT_MEASUREMENTS",
        "TRANSPORT_MODE",
        "LOADING_REQUIREMENT",
        "UNLOADING_REQUIREMENT",
        "FORKLIFT_REQUIREMENT",
        "TAIL_LIFT_REQUIREMENT",
        "DISMANTLING_REQUIREMENT",
    }
    assert queue["task_count"] == 8
    assert queue["blocking_task_count"] == 8
    assert all(task["status"] == "OPEN" for task in queue["tasks"])
    assert all(task["blocks_manual_quote"] is True for task in queue["tasks"])
    assert all(task["blocks_qualification"] is True for task in queue["tasks"])


def test_title_measurement_does_not_resolve_structured_evidence_task() -> None:
    landed = deepcopy(_landed())
    landed["source_opportunity"]["title"] = (
        "4 stk komplette lagerreoler 800kg - synthetic shipment evidence test"
    )
    transport = _transport(landed)
    assert "800kg" in transport["source_opportunity"]["title"]

    queue = build_shipment_evidence_queue(transport)
    measurement = _task(queue, "SHIPMENT_MEASUREMENTS")

    assert measurement["current_value"] is None
    assert "shipment.weight_kg" in measurement["requested_fields"]
    assert "shipment.volume_m3" in measurement["requested_fields"]
    assert measurement["evidence_refs"] == []
    assert queue["scope"]["listing_prose_extraction_enabled"] is False


def test_structured_shipment_evidence_removes_completed_tasks() -> None:
    landed = deepcopy(_landed())
    landed["source_opportunity"].update(
        {
            "cargo_type": "PALLETIZED",
            "weight_kg": 800,
            "pallet_count": 2,
            "item_count": 4,
            "longest_length_m": 2.0,
            "loading_required": True,
            "unloading_required": True,
            "forklift_required": False,
            "tail_lift_required": True,
            "dismantling_required": False,
            "transport_mode": "CARRIER",
        }
    )

    queue = build_shipment_evidence_queue(_transport(landed))

    assert queue["workflow_status"] == "READY_FOR_MANUAL_QUOTE"
    assert queue["next_action"] == "REQUEST_MANUAL_TRANSPORT_QUOTE"
    assert queue["task_count"] == 0
    assert queue["blocking_task_count"] == 0
    assert queue["manual_quote_readiness"] == {
        "ready": False,
        "transport_status": "READY_FOR_MANUAL_QUOTE",
    }


def test_existing_estimated_quote_makes_remaining_tasks_non_blocking() -> None:
    landed = deepcopy(_landed())
    transport_component = next(
        component
        for component in landed["landed_cost_estimate"]["components"]
        if component["component_id"] == "transport"
    )
    transport_component.update(
        {
            "status": "ESTIMATED",
            "economic_treatment": "ECONOMIC_COST",
            "required_for_qualification": True,
            "low_nok": 8000,
            "expected_nok": 11000,
            "high_nok": 15000,
            "source_ref": "manual-transport-estimate:test",
            "notes": ["Manual estimate based on available shipment information."],
        }
    )

    queue = build_shipment_evidence_queue(_transport(landed))

    assert queue["workflow_status"] == "EVIDENCE_REVIEW_OPTIONAL"
    assert queue["next_action"] == "REVIEW_OPTIONAL_SHIPMENT_EVIDENCE"
    assert queue["manual_quote_readiness"]["ready"] is True
    assert queue["task_count"] > 0
    assert queue["blocking_task_count"] == 0
    assert all(task["blocks_manual_quote"] is False for task in queue["tasks"])
    assert all(task["blocks_qualification"] is False for task in queue["tasks"])


def test_zero_opportunity_produces_valid_empty_queue() -> None:
    landed = build_operational_landed_cost_export(
        {"decision_count": 0, "decisions": []},
        _buyer(),
    )
    transport = build_operational_transport_export(landed, _buyer(), _market())

    queue = build_shipment_evidence_queue(transport)

    assert queue["selection_status"] == "NO_ELIGIBLE_OPPORTUNITY"
    assert queue["workflow_status"] == "NO_ELIGIBLE_OPPORTUNITY"
    assert queue["next_action"] == "NONE"
    assert queue["source_opportunity"] is None
    assert queue["task_count"] == 0
    assert queue["blocking_task_count"] == 0
    assert queue["tasks"] == []


def test_unmapped_future_input_creates_blocking_manual_review_task() -> None:
    transport = deepcopy(_transport())
    transport["transport_snapshot"]["missing_inputs"].append(
        "shipment.future_structured_field"
    )

    queue = build_shipment_evidence_queue(transport)
    task = _task(queue, "UNMAPPED_TRANSPORT_INPUT")

    assert task["requested_fields"] == ["shipment.future_structured_field"]
    assert task["source_channel"] == "MANUAL_REVIEW"
    assert task["blocks_manual_quote"] is True


def test_scope_disables_automatic_contact_and_decision_changes() -> None:
    queue = build_shipment_evidence_queue(_transport())

    assert queue["scope"] == {
        "listing_prose_extraction_enabled": False,
        "automatic_seller_contact_allowed": False,
        "automatic_carrier_contact_allowed": False,
        "automatic_quote_request_allowed": False,
        "persistent_task_state_enabled": False,
        "changes_final_decision": False,
        "changes_ranking": False,
        "changes_top5": False,
        "changes_alerts": False,
        "automatic_purchase_allowed": False,
    }


def test_cli_writes_shipment_evidence_queue(tmp_path: Path) -> None:
    transport_path = tmp_path / "operational-transport.json"
    output_path = tmp_path / "shipment-evidence-queue.json"
    transport_path.write_text(
        json.dumps(_transport(), ensure_ascii=False),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_shipment_evidence_queue.py",
            "--transport-input",
            str(transport_path),
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
    assert saved["workflow_status"] == "EVIDENCE_REQUIRED_FOR_QUOTE"
    assert saved["task_count"] == 8
    assert printed["opportunity_id"] == saved["source_opportunity"]["opportunity_id"]
    assert printed["task_count"] == saved["task_count"]
    assert printed["output"] == str(output_path)
