from copy import deepcopy
import json
from pathlib import Path

import pytest

from opportunity_engine.buyers import BuyerProfileV1
from opportunity_engine.costs import (
    LandedCostEstimateError,
    build_estimate_from_decision_record,
    build_landed_cost_snapshot,
    build_operational_landed_cost_export,
    select_operational_decision,
)
from scripts.build_operational_landed_cost import main as build_operational_main


ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = ROOT / "data" / "decision_intelligence.json"
BUYER_PATH = ROOT / "config" / "buyers" / "mahmoud_namsos_v1.json"


def _decision_payload() -> dict:
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _buyer() -> BuyerProfileV1:
    return BuyerProfileV1.from_path(BUYER_PATH)


def _component(snapshot: dict, component_id: str) -> dict:
    return next(
        component
        for component in snapshot["components"]
        if component["component_id"] == component_id
    )


def test_real_decision_file_builds_one_conservative_landed_cost_sidecar() -> None:
    payload = _decision_payload()
    export = build_operational_landed_cost_export(payload, _buyer())

    assert export["selection_status"] == "SELECTED"
    selected = export["source_opportunity"]
    snapshot = export["landed_cost_estimate"]
    assert selected is not None
    assert snapshot is not None

    source_record = next(
        record
        for record in payload["decisions"]
        if record["opportunity_id"] == selected["opportunity_id"]
    )
    assert selected["final_decision"] == source_record["final_decision"]
    assert selected["opportunity_score"] == source_record["opportunity_score"]
    assert snapshot["opportunity_id"] == source_record["opportunity_id"]
    assert snapshot["destination"]["city"] == "Namsos"
    assert snapshot["destination"]["country_code"] == "NO"
    assert snapshot["currency_code"] == "NOK"

    purchase = _component(snapshot, "purchase_price")
    assert purchase["status"] == "CONFIRMED"
    assert purchase["low_nok"] == source_record["asking_price_nok"]
    assert purchase["expected_nok"] == source_record["asking_price_nok"]
    assert purchase["high_nok"] == source_record["asking_price_nok"]
    assert snapshot["known_cash_required_range"]["expected_nok"] >= source_record[
        "asking_price_nok"
    ]
    assert snapshot["scope"]["changes_final_decision"] is False
    assert snapshot["scope"]["changes_ranking"] is False
    assert snapshot["scope"]["changes_top5"] is False
    assert snapshot["scope"]["changes_alerts"] is False


def test_real_decision_missing_costs_remain_unknown_not_zero() -> None:
    payload = _decision_payload()
    record = select_operational_decision(payload)
    assert record is not None

    snapshot = build_landed_cost_snapshot(
        build_estimate_from_decision_record(record, _buyer())
    )
    mapped_missing = {
        "auction_fee_nok": "auction_fee",
        "transport_cost_nok": "transport",
        "dismantling_cost_nok": "dismantling",
        "storage_cost_nok": "storage",
        "repair_cost_nok": "repair",
        "other_costs_nok": "other_costs",
        "vat_nok": "vat",
    }
    for source_field, component_id in mapped_missing.items():
        if source_field in record.get("missing_evidence", []):
            component = _component(snapshot, component_id)
            assert component["status"] == "UNKNOWN"
            assert component["low_nok"] is None
            assert component["expected_nok"] is None
            assert component["high_nok"] is None
            assert component_id in snapshot["missing_required_inputs"]

    if snapshot["missing_required_inputs"]:
        assert snapshot["complete_cash_required_range"] is None
        assert snapshot["complete_net_economic_cost_range"] is None
        assert snapshot["qualification_readiness"]["ready"] is False


def test_zero_decisions_produce_a_valid_empty_sidecar() -> None:
    export = build_operational_landed_cost_export(
        {"decision_count": 0, "decisions": []},
        _buyer(),
    )

    assert export["selection_status"] == "NO_ELIGIBLE_OPPORTUNITY"
    assert export["source_opportunity"] is None
    assert export["landed_cost_estimate"] is None


def test_selector_skips_records_without_known_asking_price() -> None:
    payload = {
        "decision_count": 2,
        "decisions": [
            {"opportunity_id": "missing-price", "asking_price_nok": None},
            {"opportunity_id": "known-price", "asking_price_nok": 1500},
        ],
    }

    selected = select_operational_decision(payload)

    assert selected is not None
    assert selected["opportunity_id"] == "known-price"


def test_explicit_unknown_opportunity_id_is_rejected() -> None:
    with pytest.raises(LandedCostEstimateError, match="opportunity_id not found"):
        build_operational_landed_cost_export(
            _decision_payload(),
            _buyer(),
            opportunity_id="does-not-exist",
        )


def test_known_costs_are_copied_exactly_and_vat_recoverability_is_separate() -> None:
    payload = _decision_payload()
    base = select_operational_decision(payload)
    assert base is not None
    record = deepcopy(base)
    record.update(
        {
            "auction_fee_nok": 500,
            "transport_cost_nok": 1200,
            "vat_nok": 1175,
            "vat_recoverable": True,
            "missing_evidence": [],
        }
    )

    snapshot = build_landed_cost_snapshot(
        build_estimate_from_decision_record(record, _buyer())
    )

    assert _component(snapshot, "auction_fee")["expected_nok"] == 500
    assert _component(snapshot, "transport")["expected_nok"] == 1200
    vat = _component(snapshot, "vat")
    assert vat["status"] == "CONFIRMED"
    assert vat["economic_treatment"] == "RECOVERABLE_CASH_OUTFLOW"
    assert snapshot["known_recoverable_cash_outflow_range"]["expected_nok"] == 1175
    assert snapshot["known_net_economic_cost_range"]["expected_nok"] == (
        record["asking_price_nok"] + 500 + 1200
    )


def test_known_vat_without_recoverability_keeps_economic_treatment_unknown() -> None:
    record = deepcopy(select_operational_decision(_decision_payload()))
    assert record is not None
    record["vat_nok"] = 750
    record.pop("vat_recoverable", None)
    record.pop("vat_status", None)

    snapshot = build_landed_cost_snapshot(
        build_estimate_from_decision_record(record, _buyer())
    )

    vat = _component(snapshot, "vat")
    assert vat["status"] == "CONFIRMED"
    assert vat["economic_treatment"] == "UNKNOWN"
    assert "vat" in snapshot["unknown_economic_treatments"]
    assert snapshot["complete_net_economic_cost_range"] is None


def test_cli_writes_operational_sidecar_from_real_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "operational-landed-cost.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_operational_landed_cost.py",
            "--decisions",
            str(DECISIONS_PATH),
            "--buyer",
            str(BUYER_PATH),
            "--output",
            str(output),
        ],
    )

    assert build_operational_main() == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)

    assert saved["selection_status"] == "SELECTED"
    assert saved["source_opportunity"]["opportunity_id"] == printed[
        "opportunity_id"
    ]
    assert printed["estimate_status"] in {
        "REQUIRES_COST_INPUTS",
        "PARTIAL_ESTIMATE",
        "COMPLETE",
    }
    assert printed["output"] == str(output)
