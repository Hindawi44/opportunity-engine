from __future__ import annotations

from opportunity_engine.discovery.unified_six_market_pipeline import (
    STAGE_ORDER,
    UNIFIED_MARKET_CODES,
    build_unified_six_market_pipeline,
)


def _core_report() -> dict:
    return {
        "generated_at": "2026-08-23T08:00:00+00:00",
        "market_coverage": ["NO", "SE", "DE"],
        "markets": [
            {
                "market_code": "NO",
                "currency": "NOK",
                "source_count": 1,
                "source_execution_counts": {"SUCCESS": 1},
                "deduplicated_record_count": 2,
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
        "deduplicated_opportunities": [
            {
                "market_code": "NO",
                "opportunity_identity": "no:1",
                "listing_status": "ACTIVE",
                "top5_eligible": True,
                "analysis_eligible": False,
            }
        ],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _france_sidecar() -> dict:
    return {
        "status": "SUCCESS",
        "source_country": "FR",
        "discovery_status": "SUCCESS",
        "discovery_accepted_signal_count": 3,
        "persistent_case_count": 2,
        "follow_up": {
            "status": "SUCCESS",
            "case_count": 2,
            "commercial_lead_count": 0,
        },
        "exact_lot_verification_status": "NOT_BUILT_YET_REQUIRES_SOURCE_SPECIFIC_VALIDATION",
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _italy_sidecar() -> dict:
    return {
        "status": "SUCCESS",
        "source_country": "IT",
        "discovery_status": "SUCCESS",
        "discovery_accepted_signal_count": 1,
        "persistent_case_count": 1,
        "follow_up": {
            "status": "SUCCESS",
            "case_count": 1,
            "commercial_lead_count": 1,
        },
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


def _netherlands_sidecar() -> dict:
    return {
        "status": "SUCCESS",
        "source_country": "NL",
        "discovery_status": "VALID_ZERO",
        "discovery_accepted_signal_count": 0,
        "persistent_case_count": 1,
        "follow_up": {
            "status": "SUCCESS",
            "case_count": 1,
            "commercial_lead_count": 0,
        },
        "exact_lot_verification_status": "NOT_BUILT_YET_REQUIRES_SOURCE_SPECIFIC_VALIDATION",
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _ledger() -> dict:
    return build_unified_six_market_pipeline(
        _core_report(),
        france_sidecar=_france_sidecar(),
        italy_sidecar=_italy_sidecar(),
        netherlands_sidecar=_netherlands_sidecar(),
    )


def test_all_six_markets_share_one_ordered_pipeline_contract() -> None:
    ledger = _ledger()

    assert ledger["market_coverage"] == list(UNIFIED_MARKET_CODES)
    assert [row["market_code"] for row in ledger["markets"]] == list(UNIFIED_MARKET_CODES)
    assert ledger["pipeline_contract"] == "UNIFIED_SIX_MARKET_PIPELINE_V1"

    for market in ledger["markets"]:
        assert market["pipeline_contract"] == "UNIFIED_SIX_MARKET_PIPELINE_V1"
        assert [stage["stage"] for stage in market["stages"]] == list(STAGE_ORDER)
        assert market["automatic_contact"] is False
        assert market["automatic_bid"] is False
        assert market["automatic_purchase"] is False
        assert market["automatic_payment"] is False


def test_existing_italy_exact_lot_and_qualification_truth_is_preserved() -> None:
    italy = next(row for row in _ledger()["markets"] if row["market_code"] == "IT")
    stages = {stage["stage"]: stage for stage in italy["stages"]}

    assert stages["DISCOVERY"]["status"] == "SUCCESS"
    assert stages["FOLLOW_UP"]["status"] == "SUCCESS"
    assert stages["EXACT_LOT_VERIFICATION"]["status"] == "SUCCESS"
    assert stages["EXACT_LOT_VERIFICATION"]["verified_active_exact_lot_count"] == 1
    assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "SUCCESS"
    assert stages["COMMERCIAL_QUALIFICATION"]["qualification_count"] == 1
    assert stages["OPPORTUNITY_DECISION"]["status"] == "NOT_READY"


def test_missing_france_and_netherlands_exact_lot_capability_is_explicit_not_hidden() -> None:
    ledger = _ledger()
    for code in ("FR", "NL"):
        market = next(row for row in ledger["markets"] if row["market_code"] == code)
        stages = {stage["stage"]: stage for stage in market["stages"]}
        assert stages["EXACT_LOT_VERIFICATION"]["status"] == "NOT_IMPLEMENTED"
        assert stages["COMMERCIAL_QUALIFICATION"]["status"] == "BLOCKED_BY_EXACT_LOT"
        assert stages["OPPORTUNITY_DECISION"]["status"] == "NOT_READY"


def test_core_markets_are_adapted_into_same_contract_without_reclassifying_truth() -> None:
    ledger = _ledger()
    norway = next(row for row in ledger["markets"] if row["market_code"] == "NO")
    sweden = next(row for row in ledger["markets"] if row["market_code"] == "SE")

    no_stages = {stage["stage"]: stage for stage in norway["stages"]}
    se_stages = {stage["stage"]: stage for stage in sweden["stages"]}

    assert no_stages["DISCOVERY"]["status"] == "SUCCESS"
    assert no_stages["OPPORTUNITY_DECISION"]["status"] == "CANDIDATE_AVAILABLE"
    assert no_stages["OPPORTUNITY_DECISION"]["top5_eligible_count"] == 1
    assert se_stages["DISCOVERY"]["status"] == "VALID_ZERO"
    assert se_stages["OPPORTUNITY_DECISION"]["status"] == "VALID_ZERO"
