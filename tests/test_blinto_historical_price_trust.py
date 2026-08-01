from pathlib import Path

from opportunity_engine.discovery.blinto_historical_price_trust import (
    apply_blinto_historical_price_trust_gate,
)


def _result(candidate):
    return {
        "all_discovered_candidates": [candidate],
        "discovery_top5": [],
        "search_run_report": {},
    }


def test_content_mismatch_keeps_raw_bid_but_excludes_historical_price_analysis():
    candidate = {
        "opportunity_state": "HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW",
        "verification_content_match": False,
        "historical_market_evidence_eligible": False,
        "historical_data_fields_trusted": False,
        "bid_price_sek": 2000,
        "reference_value_sek": 50000,
        "confirmed_information": [
            "traceable public sources: 1",
            "public Blinto bid value: 2000 SEK",
            "public Blinto reference value: 50000 SEK (not current sale price)",
        ],
        "verification": [
            {
                "verification_content_match": False,
                "inventory_type": "workwear_inventory",
                "quantity": 20,
                "price_nok": None,
                "bid_price_nok": None,
                "clothing_inventory_evidence": True,
            }
        ],
    }

    corrected = apply_blinto_historical_price_trust_gate(_result(candidate))
    review = corrected["all_discovered_candidates"][0]
    verification = review["verification"][0]

    assert review["bid_price_sek"] == 2000
    assert review["reference_value_sek"] == 50000
    assert review["bid_price_trusted"] is False
    assert review["reference_value_trusted"] is False
    assert review["exclude_from_historical_price_analysis"] is True
    assert (
        review["historical_price_analysis_exclusion_reason"]
        == "verification_content_mismatch"
    )
    assert verification["inventory_type"] is None
    assert verification["quantity"] is None
    assert verification["clothing_inventory_evidence"] is False
    assert verification["historical_data_fields_trusted"] is False
    assert verification["exclude_from_historical_price_analysis"] is True
    assert not any(
        value.startswith("public Blinto bid value:")
        for value in review["confirmed_information"]
    )
    assert not any(
        value.startswith("public Blinto reference value:")
        for value in review["confirmed_information"]
    )
    assert (
        "raw Blinto bid value observed: 2000 SEK "
        "(excluded from historical price analysis)"
        in review["confirmed_information"]
    )
    assert corrected["search_run_report"]["historical_price_trust_gate"] == {
        "source": "BLINTO",
        "applied": True,
        "trusted_historical_candidates": 0,
        "excluded_historical_candidates": 1,
        "excluded_bid_values": 1,
        "excluded_reference_values": 1,
    }


def test_matching_historical_item_marks_extracted_prices_trusted():
    candidate = {
        "opportunity_state": "HISTORICAL_MARKET_EVIDENCE",
        "verification_content_match": True,
        "historical_market_evidence_eligible": True,
        "historical_data_fields_trusted": True,
        "bid_price_sek": 5400,
        "reference_value_sek": 50000,
        "confirmed_information": [],
        "verification": [
            {
                "verification_content_match": True,
                "inventory_type": "workwear_inventory",
                "quantity": 38,
                "clothing_inventory_evidence": True,
            }
        ],
    }

    corrected = apply_blinto_historical_price_trust_gate(_result(candidate))
    historical = corrected["all_discovered_candidates"][0]
    verification = historical["verification"][0]

    assert historical["bid_price_trusted"] is True
    assert historical["reference_value_trusted"] is True
    assert historical["exclude_from_historical_price_analysis"] is False
    assert historical["historical_price_analysis_exclusion_reason"] is None
    assert verification["inventory_type"] == "workwear_inventory"
    assert verification["quantity"] == 38
    assert verification["clothing_inventory_evidence"] is True
    assert verification["historical_data_fields_trusted"] is True
    assert verification["exclude_from_historical_price_analysis"] is False
    assert "public Blinto bid value: 5400 SEK" in historical["confirmed_information"]
    assert corrected["search_run_report"]["historical_price_trust_gate"] == {
        "source": "BLINTO",
        "applied": True,
        "trusted_historical_candidates": 1,
        "excluded_historical_candidates": 0,
        "excluded_bid_values": 0,
        "excluded_reference_values": 0,
    }


def test_non_historical_candidate_is_not_assigned_historical_price_trust():
    candidate = {
        "opportunity_state": "CONFIRMED_SALE",
        "listing_status": "ACTIVE",
        "bid_price_sek": 2900,
        "confirmed_information": ["public Blinto bid value: 2900 SEK"],
    }

    corrected = apply_blinto_historical_price_trust_gate(_result(candidate))
    active = corrected["all_discovered_candidates"][0]

    assert "bid_price_trusted" not in active
    assert "exclude_from_historical_price_analysis" not in active
    assert active["confirmed_information"] == ["public Blinto bid value: 2900 SEK"]


def test_live_runner_applies_price_trust_after_blinto_enrichment_before_writing():
    script = Path("scripts/run_sweden_clothing_inventory_discovery_search.py").read_text(
        encoding="utf-8"
    )

    assert (
        script.index("enrich_blinto_discovery_result(result)")
        < script.index("apply_blinto_historical_price_trust_gate(result)")
        < script.index("write_discovery_artifacts(result, output_dir)")
    )
