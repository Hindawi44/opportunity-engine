import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

import opportunity_engine.discovery.confirmed_dossier_intake as intake_module
from opportunity_engine.discovery.confirmed_dossier_intake import (
    ConfirmedDossierIntakeError,
    build_confirmed_dossier_report,
    load_confirmed_dossier_intake,
    validate_confirmed_dossier_intake,
)
from scripts.run_clothing_inventory_single_case import (
    build_final_report,
    build_operator_summary,
    main,
    write_report_outputs,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    REPOSITORY_ROOT
    / "tests/fixtures/confirmed_clothing_inventory_dossier_incomplete.json"
)


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _assert_intake_error(
    payload: dict,
    expected_status: str,
) -> ConfirmedDossierIntakeError:
    with pytest.raises(ConfirmedDossierIntakeError) as exc_info:
        validate_confirmed_dossier_intake(payload)
    assert exc_info.value.status == expected_status
    return exc_info.value


def test_valid_incomplete_confirmed_opportunity_is_retained() -> None:
    payload = load_confirmed_dossier_intake(FIXTURE)
    report = build_confirmed_dossier_report(payload)

    assert report["schema_version"] == (
        "confirmed-clothing-inventory-dossier-intake-v1"
    )
    assert report["execution_mode"] == "CONFIRMED_DOSSIER_INTAKE"
    assert report["opportunity_status"] == (
        "CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY"
    )
    assert report["dossier_status"] == "DOSSIER_EVIDENCE_REQUIRED"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["final_decision"] == "NO_DECISION"
    assert report["retained_in_opportunity_report"] is True
    assert report["eligibility"]["eligible_for_analysis"] is False

    dossier = report["dossier"]
    assert dossier["opportunity_id"] == payload["opportunity_id"]
    assert report["canonical_opportunity"]["opportunity_id"] == payload["opportunity_id"]
    assert dossier["qualification_status"] == "SALE_CONFIRMED"
    assert dossier["confirmed_facts"]["location"] == "Trøndelag"
    assert dossier["confirmed_facts"]["product_categories"] == [
        "clothing",
        "footwear",
    ]
    assert dossier["seller_claims"] == {}
    assert set(dossier["unknown_fields"]) >= {
        "quantity",
        "asking_price_nok",
        "contact",
        "vat_statement",
        "buyer_fees_nok",
        "condition",
        "pickup_terms",
        "packing_terms",
        "transport_terms",
    }
    assert dossier["supported_inferences"] == payload["supported_inferences"]
    assert dossier["provenance"]["records"] == payload["provenance"]["records"]
    assert dossier["provenance"]["field_evidence"]["quantity"] == {
        "classification": "UNKNOWN",
        "evidence_refs": [],
        "unit": "items",
    }
    assert "verified physical quantity" in dossier["missing_evidence"]


def test_report_contains_no_financial_or_investment_decision_manufacture() -> None:
    report = build_confirmed_dossier_report(_payload())

    for key in (
        "market_comparables",
        "acquisition_cost_evidence",
        "financial_integration",
        "decision_intelligence",
        "opportunity_score",
        "expected_profit_nok",
        "roi_percent",
        "maximum_safe_bid_nok",
        "recommendation",
    ):
        assert key not in report

    rendered = json.dumps(report, ensure_ascii=False)
    for decision in ('"BUY_REVIEW"', '"WATCH"', '"REJECT"'):
        assert decision not in rendered

    for key in (
        "analysis_invoked",
        "market_analysis_invoked",
        "acquisition_cost_analysis_invoked",
        "scoring_invoked",
        "decision_intelligence_invoked",
        "automatic_purchase_decision",
        "automatic_bid",
        "automatic_contact",
        "automatic_reservation",
        "automatic_payment",
    ):
        assert report[key] is False


def test_source_agnostic_intake_module_has_no_named_source_branching() -> None:
    source = Path(intake_module.__file__).read_text(encoding="utf-8")
    for named_source in ("AXL", "Auksjonen", "FINN", "Norsk Avvikling"):
        assert named_source not in source


def test_valid_intake_writes_all_stable_outputs(tmp_path: Path) -> None:
    report = build_confirmed_dossier_report(_payload())
    paths = write_report_outputs(report, tmp_path)

    assert set(paths) == {"dossier", "report", "summary"}
    for path in paths.values():
        assert path.exists()

    dossier = json.loads(paths["dossier"].read_text(encoding="utf-8"))
    final_report = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert dossier["opportunity_id"] == _payload()["opportunity_id"]
    assert final_report["dossier_status"] == "DOSSIER_EVIDENCE_REQUIRED"
    assert "Stable opportunity ID: confirmed-clothing-inventory-example-001" in summary
    assert "Final decision: NO_DECISION" in summary
    assert "Retained in opportunity report: yes" in summary
    assert "Automatic purchase/bid/contact/reservation/payment: false" in summary
    assert build_operator_summary(report) == summary


def test_seller_claims_and_conflicts_remain_separate() -> None:
    payload = _payload()
    payload["fields"]["quantity"] = {
        "value": 250,
        "unit": "items",
        "classification": "SELLER_CLAIM_UNVERIFIED",
        "evidence_refs": ["source-sale-page"],
    }
    payload["fields"]["condition"] = {
        "value": ["new stock", "mixed condition"],
        "classification": "CONFLICTING_EVIDENCE",
        "evidence_refs": ["source-sale-page", "source-category-page"],
    }

    report = build_confirmed_dossier_report(payload)
    dossier = report["dossier"]

    assert dossier["seller_claims"]["quantity"] == 250
    assert "quantity" not in dossier["confirmed_facts"]
    conflict = dossier["confirmed_facts"]["conflicting_evidence"]["condition"]
    assert conflict["classification"] == "CONFLICTING_EVIDENCE"
    assert conflict["evidence_refs"] == [
        "source-sale-page",
        "source-category-page",
    ]


def test_non_https_source_is_rejected_without_dossier() -> None:
    payload = _payload()
    payload["source"]["primary_url"] = "http://inventory.example.no/opportunity"
    error = _assert_intake_error(payload, "INTAKE_REJECTED_UNTRACEABLE")
    assert "HTTPS" in str(error)


def test_ended_input_is_rejected_without_dossier() -> None:
    payload = _payload()
    payload["listing_status"] = "ENDED"
    _assert_intake_error(payload, "INTAKE_REJECTED_NOT_ACTIVE")


def test_unconfirmed_input_is_rejected_without_dossier() -> None:
    payload = _payload()
    payload["qualification_status"] = "CONTACT_REQUIRED"
    _assert_intake_error(payload, "INTAKE_REJECTED_NOT_CONFIRMED")


def test_unknown_evidence_reference_fails_traceability_validation() -> None:
    payload = _payload()
    payload["fields"]["location"]["evidence_refs"] = ["missing-evidence-id"]
    _assert_intake_error(payload, "INTAKE_REJECTED_UNTRACEABLE")


def test_true_automatic_action_flag_fails_validation() -> None:
    payload = _payload()
    payload["safety"]["automatic_contact"] = True
    _assert_intake_error(payload, "INTAKE_VALIDATION_FAILED")


def test_confirmed_intake_cli_writes_retained_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_clothing_inventory_single_case.py",
            "--confirmed-intake-file",
            str(FIXTURE),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert main() == 0
    assert (output_dir / "opportunity-dossier.json").exists()
    assert (output_dir / "final-report.json").exists()
    assert (output_dir / "operator-summary.txt").exists()


@pytest.mark.parametrize("conflicting_option", ["--live", "--html-file"])
def test_confirmed_intake_cli_is_exclusive_with_live_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    conflicting_option: str,
) -> None:
    argv = [
        "run_clothing_inventory_single_case.py",
        "--confirmed-intake-file",
        str(FIXTURE),
        conflicting_option,
    ]
    if conflicting_option == "--html-file":
        html_file = tmp_path / "page.html"
        html_file.write_text("<html></html>", encoding="utf-8")
        argv.append(str(html_file))
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


@pytest.mark.parametrize("forbidden_option", ["--comparables-file", "--costs-file"])
def test_confirmed_intake_cli_rejects_financial_evidence_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    forbidden_option: str,
) -> None:
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_clothing_inventory_single_case.py",
            "--confirmed-intake-file",
            str(FIXTURE),
            forbidden_option,
            str(evidence_file),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_invalid_cli_input_returns_nonzero_and_writes_no_normal_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload()
    payload["listing_status"] = "ENDED"
    invalid_path = tmp_path / "ended.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_clothing_inventory_single_case.py",
            "--confirmed-intake-file",
            str(invalid_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert main() == 2
    assert not (output_dir / "opportunity-dossier.json").exists()
    assert not (output_dir / "final-report.json").exists()
    assert not (output_dir / "operator-summary.txt").exists()


def test_preserved_runner_mode_retains_existing_behavior() -> None:
    report = build_final_report()

    assert report["execution_mode"] == "PRESERVED_CASE"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["analysis_invoked"] is False
