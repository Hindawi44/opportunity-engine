import json
from pathlib import Path

from scripts.run_clothing_inventory_single_case import (
    build_final_report,
    build_operator_summary,
    write_outputs,
)


def test_single_case_report_preserves_traceability_and_unknowns() -> None:
    report = build_final_report()

    assert report["domain"] == "CLOTHING_INVENTORY"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert report["dossier"]["confirmed_facts"]["source_url"].startswith("https://")
    assert report["dossier"]["confirmed_facts"]["source_name"] == (
        "AUKSJONEN_NO_PUBLIC_LISTING"
    )
    assert "public_contact" in report["dossier"]["unknown_fields"]
    assert report["eligibility"]["eligible_for_analysis"] is False
    assert report["analysis_invoked"] is False


def test_single_case_report_prohibits_automatic_actions() -> None:
    report = build_final_report()

    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_single_case_writes_dossier_report_and_summary(tmp_path: Path) -> None:
    paths = write_outputs(tmp_path)

    assert set(paths) == {"dossier", "report", "summary"}
    for path in paths.values():
        assert path.exists()

    dossier = json.loads(paths["dossier"].read_text(encoding="utf-8"))
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert dossier["domain"] == "CLOTHING_INVENTORY"
    assert report["final_outcome"] == "EVIDENCE_REQUIRED"
    assert "Outcome: EVIDENCE_REQUIRED" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
    assert build_operator_summary(report) == summary
