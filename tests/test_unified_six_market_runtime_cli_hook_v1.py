from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.unified_six_market_runtime_cli_hook import (
    UNIFIED_PIPELINE_FILENAME,
    UNIFIED_PHONE_SUMMARY_FILENAME,
    build_unified_runtime_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_INIT = ROOT / "src/opportunity_engine/discovery/__init__.py"
RUNTIME_HOOK = ROOT / "src/opportunity_engine/discovery/unified_six_market_runtime_cli_hook.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _core_report() -> dict:
    return {
        "generated_at": "2026-08-23T09:00:00+00:00",
        "market_coverage": ["NO", "SE", "DE"],
        "markets": [
            {
                "market_code": "NO",
                "currency": "NOK",
                "source_count": 1,
                "source_execution_counts": {"SUCCESS": 1},
                "deduplicated_record_count": 1,
                "active_count": 1,
                "top5_eligible_count": 1,
            },
            {
                "market_code": "SE",
                "currency": "SEK",
                "source_count": 1,
                "source_execution_counts": {"VALID_ZERO_RESULT": 1},
                "deduplicated_record_count": 0,
                "active_count": 0,
                "top5_eligible_count": 0,
            },
            {
                "market_code": "DE",
                "currency": "EUR",
                "source_count": 1,
                "source_execution_counts": {"SUCCESS": 1},
                "deduplicated_record_count": 1,
                "active_count": 0,
                "top5_eligible_count": 0,
            },
        ],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _france_cycle() -> dict:
    return {
        "status": "SUCCESS",
        "source_country": "FR",
        "discovery_status": "SUCCESS",
        "discovery_accepted_signal_count": 2,
        "persistent_case_count": 1,
        "follow_up": {"status": "SUCCESS", "case_count": 1, "commercial_lead_count": 0},
        "exact_lot_verification_status": "NOT_BUILT_YET_REQUIRES_SOURCE_SPECIFIC_VALIDATION",
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _italy_cycle() -> dict:
    return {
        "status": "SUCCESS",
        "source_country": "IT",
        "discovery_status": "SUCCESS",
        "discovery_accepted_signal_count": 1,
        "persistent_case_count": 1,
        "follow_up": {"status": "SUCCESS", "case_count": 1, "commercial_lead_count": 1},
        "exact_lot_verification": {
            "engine_version": "ITALY_EXACT_LOT_VERIFICATION_V1",
            "status": "SUCCESS",
            "candidate_lead_count": 1,
            "source_page_verified_count": 1,
            "verified_active_exact_lot_lead_count": 1,
        },
        "commercial_qualification": {
            "engine_version": "ITALY_COMMERCIAL_QUALIFICATION_V1",
            "status": "SUCCESS",
            "qualification_count": 1,
            "financial_decision_ready_count": 0,
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _netherlands_cycle() -> dict:
    return {
        "status": "SUCCESS",
        "source_country": "NL",
        "discovery_status": "VALID_ZERO",
        "discovery_accepted_signal_count": 0,
        "persistent_case_count": 1,
        "follow_up": {"status": "SUCCESS", "case_count": 1, "commercial_lead_count": 0},
        "exact_lot_verification_status": "NOT_BUILT_YET_REQUIRES_SOURCE_SPECIFIC_VALIDATION",
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_runtime_build_writes_one_six_market_authority_artifact(tmp_path: Path) -> None:
    _write_json(tmp_path / "multi-market-daily-checkpoint.json", _core_report())
    _write_json(tmp_path / "france-case-memory-v1.json", _france_cycle())
    _write_json(tmp_path / "italy-case-memory-v1.json", _italy_cycle())
    _write_json(tmp_path / "netherlands-case-memory-v1.json", _netherlands_cycle())

    paths = build_unified_runtime_artifacts(tmp_path)

    assert paths["pipeline"] == tmp_path / UNIFIED_PIPELINE_FILENAME
    assert paths["phone_summary"] == tmp_path / UNIFIED_PHONE_SUMMARY_FILENAME

    ledger = json.loads(paths["pipeline"].read_text(encoding="utf-8"))
    assert ledger["market_coverage"] == ["NO", "SE", "DE", "FR", "IT", "NL"]
    assert ledger["pipeline_contract"] == "UNIFIED_SIX_MARKET_PIPELINE_V1"
    assert ledger["runtime_authority"] == "PRIMARY_DAILY_OPERATOR_VIEW"
    assert ledger["runtime_emission_stage"] == "AFTER_LIFECYCLE_REVIEW_AND_DOMAIN_INTELLIGENCE"
    assert ledger["legacy_three_market_checkpoint_retained"] is True
    assert ledger["country_specific_bypass_allowed"] is False

    summary = paths["phone_summary"].read_text(encoding="utf-8")
    assert "المسار الموحد" in summary
    for code in ("NO", "SE", "DE", "FR", "IT", "NL"):
        assert code in summary
    assert "sidecar" not in summary.casefold()
    assert "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي" in summary


def test_runtime_authority_preserves_missing_capabilities_instead_of_hiding_them(tmp_path: Path) -> None:
    _write_json(tmp_path / "multi-market-daily-checkpoint.json", _core_report())
    _write_json(tmp_path / "france-case-memory-v1.json", _france_cycle())
    _write_json(tmp_path / "italy-case-memory-v1.json", _italy_cycle())
    _write_json(tmp_path / "netherlands-case-memory-v1.json", _netherlands_cycle())

    paths = build_unified_runtime_artifacts(tmp_path)
    ledger = json.loads(paths["pipeline"].read_text(encoding="utf-8"))

    by_market = {item["market_code"]: item for item in ledger["markets"]}
    for code in ("FR", "NL"):
        stages = {item["stage"]: item for item in by_market[code]["stages"]}
        assert stages["EXACT_LOT_VERIFICATION"]["status"] == "NOT_IMPLEMENTED"
        assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "BLOCKED_BY_EXACT_LOT"

    italy_stages = {item["stage"]: item for item in by_market["IT"]["stages"]}
    assert italy_stages["EXACT_LOT_VERIFICATION"]["verified_active_exact_lot_count"] == 1


def test_final_daily_bulletin_cli_is_the_runtime_emission_point() -> None:
    init_text = DISCOVERY_INIT.read_text(encoding="utf-8")
    hook_text = RUNTIME_HOOK.read_text(encoding="utf-8")

    assert "install_unified_six_market_runtime_cli_hook" in init_text
    assert "install_unified_six_market_runtime_cli_hook()" in init_text
    assert '_TARGET_CLI = "build_domain_market_intelligence_feed.py"' in hook_text
    assert '_TARGET_CLI = "run_multi_market_daily_operator_checkpoint.py"' not in hook_text
