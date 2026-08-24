from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.unified_search_truth_reconciliation_cli_hook import (
    reconcile_runtime_artifacts,
    reconcile_unified_search_truth,
)


STAGE_ORDER = (
    "DISCOVERY",
    "SIGNAL_VALIDATION",
    "ENTITY_RESOLUTION",
    "MEMORY",
    "FOLLOW_UP",
    "EXACT_LOT_VERIFICATION",
    "COMMERCIAL_QUALIFICATION",
    "EVIDENCE",
    "OPPORTUNITY_DECISION",
    "REPORT",
)


def _market(
    code: str,
    *,
    discovery: str = "FAILURE",
    exact: str = "NOT_IMPLEMENTED",
    qualification: str = "BLOCKED_BY_EXACT_LOT",
    evidence: str = "BLOCKED_BY_COMMERCIAL_QUALIFICATION",
    decision: str = "NOT_READY",
    existing_exact: int = 0,
    qualification_count: int = 0,
    financial_ready: int = 0,
) -> dict:
    statuses = {
        "DISCOVERY": discovery,
        "SIGNAL_VALIDATION": "SUCCESS",
        "ENTITY_RESOLUTION": "SUCCESS",
        "MEMORY": "SUCCESS",
        "FOLLOW_UP": "SUCCESS",
        "EXACT_LOT_VERIFICATION": exact,
        "COMMERCIAL_QUALIFICATION": qualification,
        "EVIDENCE": evidence,
        "OPPORTUNITY_DECISION": decision,
        "REPORT": "SUCCESS",
    }
    stages = []
    for name in STAGE_ORDER:
        row = {"stage": name, "status": statuses[name]}
        if name == "DISCOVERY":
            row["source_execution_counts"] = {"SUCCESS": 1, "FAILURE": 3}
        if name == "EXACT_LOT_VERIFICATION":
            row["verified_active_exact_lot_count"] = existing_exact
        if name == "COMMERCIAL_QUALIFICATION":
            row["qualification_count"] = qualification_count
            row["financial_decision_ready_count"] = financial_ready
        stages.append(row)
    return {"market_code": code, "currency": "EUR", "stages": stages}


def _ledger() -> dict:
    return {
        "schema_version": "unified-six-market-pipeline-1.0",
        "generated_at": "2026-08-24T18:00:00+00:00",
        "market_coverage": ["NO", "SE", "DE", "FR", "IT", "NL"],
        "markets": [
            _market("NO", exact="ADAPTED_FROM_CANONICAL_PIPELINE", qualification="ADAPTED_FROM_CANONICAL_PIPELINE", evidence="ADAPTED_FROM_CANONICAL_PIPELINE", decision="CANDIDATE_AVAILABLE"),
            _market("SE", exact="ADAPTED_FROM_CANONICAL_PIPELINE", qualification="ADAPTED_FROM_CANONICAL_PIPELINE", evidence="NOT_READY", decision="BLOCKED_BY_DISCOVERY_FAILURE"),
            _market("DE", exact="ADAPTED_FROM_CANONICAL_PIPELINE", qualification="ADAPTED_FROM_CANONICAL_PIPELINE", evidence="NOT_READY", decision="BLOCKED_BY_DISCOVERY_FAILURE"),
            _market("FR"),
            _market(
                "IT",
                discovery="SUCCESS",
                exact="SUCCESS",
                qualification="SUCCESS",
                evidence="REQUIRES_EVIDENCE",
                decision="NOT_READY",
                existing_exact=1,
                qualification_count=1,
            ),
            _market("NL", discovery="VALID_ZERO"),
        ],
        "search_runtime": {
            "CLOTHING_INVENTORY": {
                "provider": "exa",
                "markets": {
                    "NO": {"status": "SUCCESS", "hits_received": 15, "strict_exact_lot_count": 1},
                    "SE": {"status": "SUCCESS", "hits_received": 15, "strict_exact_lot_count": 1},
                    "DE": {"status": "SUCCESS", "hits_received": 14, "strict_exact_lot_count": 10},
                    "FR": {"status": "SUCCESS", "hits_received": 5, "strict_exact_lot_count": 4},
                    "IT": {"status": "SUCCESS", "hits_received": 5, "strict_exact_lot_count": 0},
                    "NL": {"status": "SUCCESS", "hits_received": 5, "strict_exact_lot_count": 0},
                },
            },
            "FABRIC_PROCUREMENT": {
                "provider": "exa",
                "markets": {
                    "FR": {"status": "SUCCESS", "hits_received": 5, "candidate_count": 4},
                    "IT": {"status": "SUCCESS", "hits_received": 5, "candidate_count": 4},
                    "NL": {"status": "SUCCESS", "hits_received": 5, "candidate_count": 4},
                },
            },
        },
        "automatic_purchase": False,
    }


def _stages(ledger: dict, code: str) -> dict[str, dict]:
    market = next(row for row in ledger["markets"] if row["market_code"] == code)
    return {row["stage"]: row for row in market["stages"]}


def test_verified_exact_lot_overrides_false_market_failure_but_preserves_source_failures() -> None:
    reconciled, audit = reconcile_unified_search_truth(_ledger())

    for code, exact_count in (("SE", 1), ("DE", 10)):
        stages = _stages(reconciled, code)
        assert stages["DISCOVERY"]["status"] == "SUCCESS"
        assert stages["DISCOVERY"]["legacy_status_before_search_truth"] == "FAILURE"
        assert stages["DISCOVERY"]["source_failures_preserved"] is True
        assert stages["DISCOVERY"]["partial_source_failure_count"] == 3
        assert stages["EXACT_LOT_VERIFICATION"]["status"] == "SUCCESS"
        assert stages["EXACT_LOT_VERIFICATION"]["verified_active_exact_lot_count"] == exact_count
        assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "REQUIRES_VERIFICATION"
        assert stages["OPPORTUNITY_DECISION"]["status"] == "CANDIDATE_AVAILABLE_REQUIRES_VERIFICATION"

    assert audit["status"] == "SUCCESS"
    assert audit["market_change_count"] == 6


def test_france_exact_lot_capability_cannot_remain_not_implemented() -> None:
    reconciled, _ = reconcile_unified_search_truth(_ledger())
    stages = _stages(reconciled, "FR")

    assert stages["DISCOVERY"]["status"] == "SUCCESS"
    assert stages["EXACT_LOT_VERIFICATION"]["status"] == "SUCCESS"
    assert stages["EXACT_LOT_VERIFICATION"]["verified_active_exact_lot_count"] == 4
    assert stages["EXACT_LOT_VERIFICATION"]["capability_implemented"] is True
    assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "REQUIRES_VERIFICATION"
    assert stages["OPPORTUNITY_DECISION"]["status"] == "CANDIDATE_AVAILABLE_REQUIRES_VERIFICATION"


def test_zero_exact_lot_run_reports_valid_zero_not_missing_capability() -> None:
    reconciled, _ = reconcile_unified_search_truth(_ledger())
    stages = _stages(reconciled, "NL")

    assert stages["EXACT_LOT_VERIFICATION"]["status"] == "VALID_ZERO"
    assert stages["EXACT_LOT_VERIFICATION"]["capability_implemented"] is True
    assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "NOT_READY"


def test_existing_italy_qualification_truth_is_not_downgraded_by_exa_zero() -> None:
    reconciled, _ = reconcile_unified_search_truth(_ledger())
    stages = _stages(reconciled, "IT")

    assert stages["EXACT_LOT_VERIFICATION"]["status"] == "SUCCESS"
    assert stages["EXACT_LOT_VERIFICATION"]["verified_active_exact_lot_count"] == 1
    assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "SUCCESS"
    assert stages["COMMERCIAL_QUALIFICATION"]["qualification_count"] == 1


def test_search_development_is_locked_to_same_unified_runtime_path() -> None:
    reconciled, audit = reconcile_unified_search_truth(_ledger())
    contract = reconciled["search_development_contract"]

    assert reconciled["separated_country_search_paths"] is False
    assert contract["mode"] == "ONE_UNIFIED_SEARCH_RUNTIME"
    assert contract["country_specific_search_paths_allowed"] is False
    assert contract["search_development_must_reuse_unified_runtime"] is True
    assert contract["new_agent_required"] is False
    assert contract["new_source_required"] is False
    assert "RETRIEVAL_RECALL" in contract["development_axes"]
    assert audit["search_development_contract"] == contract


def test_artifact_reconciliation_regenerates_summary_from_corrected_truth(tmp_path: Path) -> None:
    ledger = _ledger()
    (tmp_path / "unified-six-market-pipeline-v1.json").write_text(
        json.dumps(ledger, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "unified-search-runtime-v1.json").write_text(
        json.dumps(
            {
                "schema_version": "unified-search-runtime-1.0",
                "clothing_inventory": ledger["search_runtime"]["CLOTHING_INVENTORY"],
                "fabric_procurement": ledger["search_runtime"]["FABRIC_PROCUREMENT"],
                "separated_country_search_paths": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    paths = reconcile_runtime_artifacts(tmp_path)

    final_ledger = json.loads(paths["pipeline"].read_text(encoding="utf-8"))
    assert _stages(final_ledger, "SE")["DISCOVERY"]["status"] == "SUCCESS"
    assert _stages(final_ledger, "FR")["COMMERCIAL_QUALIFICATION"]["status"] == "REQUIRES_VERIFICATION"
    assert paths["audit"].exists()
    summary = paths["summary"].read_text(encoding="utf-8")
    assert "SE: اكتشاف SUCCESS" in summary
    assert "FR: اكتشاف SUCCESS | Exact Lot SUCCESS | تجاري REQUIRES_VERIFICATION" in summary
    assert "FR أقمشة: SUCCESS" in summary
    assert "تطوير البحث: نفس المسار الموحد فقط" in summary
