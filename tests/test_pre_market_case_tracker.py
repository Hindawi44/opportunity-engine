import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.pre_market_case_tracker import (
    LIQUIDATION_CHANNEL_CANDIDATE,
    NO_PUBLIC_SALE_CHANNEL_FOUND,
    SALE_LISTING_CANDIDATE,
    VERIFIED_ACTIVE_INVENTORY_SALE,
    load_case_registry,
    observation_from_sale_channel_report,
    update_case_registry,
    write_case_tracker_artifacts,
)


def report(
    *,
    estate_orgnr: str = "938018014",
    debtor_orgnr: str = "986425284",
    debtor_name: str = "MENSWEAR NORGE AS",
    candidates=None,
    scan_complete: bool = True,
    public_sale_found: bool = False,
    inventory_sale_verified: bool = False,
    liquidation_channel_verified: bool = False,
    captured_at: str = "2026-07-30T11:00:00+00:00",
):
    return {
        "schema_version": "pre-market-sale-channel-search-1.0",
        "captured_at": captured_at,
        "estate": {
            "estate_orgnr": estate_orgnr,
            "estate_name": f"{debtor_name} KONKURSBO",
            "debtor_orgnr": debtor_orgnr,
            "debtor_name": debtor_name,
            "opened_date": "2026-07-01",
            "municipality": "OSLO",
            "estate_manager_name": "Adv. Example Manager",
            "estate_manager_identified": True,
        },
        "scan_complete": scan_complete,
        "candidates": candidates or [],
        "public_sale_found": public_sale_found,
        "inventory_sale_verified": inventory_sale_verified,
        "liquidation_channel_verified": liquidation_channel_verified,
    }


def observation(**kwargs):
    return observation_from_sale_channel_report(report(**kwargs))


def test_complete_empty_search_creates_no_public_channel_case_and_human_action():
    result = update_case_registry({}, [observation()], captured_at="2026-07-30T12:00:00Z")

    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.state == NO_PUBLIC_SALE_CHANNEL_FOUND
    assert case.public_sale_found is False
    assert case.inventory_sale_verified is False
    assert case.to_dict()["top5_eligible"] is False
    assert result.operator_actions[0].action == "ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL"
    assert result.operator_actions[0].to_dict()["automatic_email"] is False
    assert len(result.changes) == 1
    assert result.changes[0].change_type == "CASE_CREATED"
    assert result.alerts == ()


def test_new_sale_candidate_on_later_run_creates_state_change_and_alert():
    first = update_case_registry({}, [observation()], captured_at="2026-07-30T12:00:00Z")
    sale_url = "https://www.vareauksjonen.no/Listing/Details/123"
    second_observation = observation(
        candidates=[
            {
                "candidate_state": SALE_LISTING_CANDIDATE,
                "url": sale_url,
            }
        ],
        captured_at="2026-07-31T08:00:00Z",
    )

    second = update_case_registry(
        {case.case_id: case for case in first.cases},
        [second_observation],
        captured_at="2026-07-31T08:05:00Z",
    )

    assert second.cases[0].state == SALE_LISTING_CANDIDATE
    assert second.operator_actions[0].action == "VERIFY_PUBLIC_SALE_PAGE"
    assert {change.change_type for change in second.changes} == {
        "STATE_CHANGED",
        "NEW_SALE_LISTING_CANDIDATE",
    }
    assert len(second.alerts) == 2
    assert second.cases[0].sale_listing_candidate_urls == (sale_url,)


def test_liquidation_candidate_has_distinct_state_and_action():
    url = "https://example-liquidator.no/bo/menswear"
    result = update_case_registry(
        {},
        [
            observation(
                candidates=[
                    {
                        "candidate_state": LIQUIDATION_CHANNEL_CANDIDATE,
                        "url": url,
                    }
                ]
            )
        ],
        captured_at="2026-07-30T12:00:00Z",
    )

    assert result.cases[0].state == LIQUIDATION_CHANNEL_CANDIDATE
    assert result.operator_actions[0].action == "VERIFY_LIQUIDATION_CHANNEL_MANDATE"
    assert result.cases[0].liquidation_channel_candidate_urls == (url,)
    assert result.alerts == ()


def test_identical_second_observation_produces_no_change_or_alert():
    first = update_case_registry({}, [observation()], captured_at="2026-07-30T12:00:00Z")
    previous = {case.case_id: case for case in first.cases}

    second = update_case_registry(
        previous,
        [observation(captured_at="2026-07-31T08:00:00Z")],
        captured_at="2026-07-31T08:05:00Z",
    )

    assert second.changes == ()
    assert second.alerts == ()
    assert second.cases[0].first_seen_at == "2026-07-30T12:00:00Z"
    assert second.cases[0].last_changed_at == "2026-07-30T12:00:00Z"
    assert second.cases[0].last_checked_at == "2026-07-31T08:00:00Z"


def test_partial_run_preserves_unobserved_existing_cases():
    first = update_case_registry(
        {},
        [
            observation(),
            observation(
                estate_orgnr="938022038",
                debtor_orgnr="925287879",
                debtor_name="KEEPFIT AS",
            ),
        ],
        captured_at="2026-07-30T12:00:00Z",
    )
    previous = {case.case_id: case for case in first.cases}

    second = update_case_registry(
        previous,
        [observation(captured_at="2026-07-31T08:00:00Z")],
        captured_at="2026-07-31T08:05:00Z",
    )

    assert len(second.cases) == 2
    assert second.observed_case_count == 1
    assert {case.debtor_name for case in second.cases} == {
        "MENSWEAR NORGE AS",
        "KEEPFIT AS",
    }


def test_verified_sale_is_only_state_eligible_for_top5_and_analysis():
    result = update_case_registry(
        {},
        [
            observation(
                public_sale_found=True,
                inventory_sale_verified=True,
            )
        ],
        captured_at="2026-07-30T12:00:00Z",
    )

    case = result.cases[0]
    payload = case.to_dict()
    assert case.state == VERIFIED_ACTIVE_INVENTORY_SALE
    assert payload["top5_eligible"] is True
    assert payload["analysis_eligible"] is True
    assert result.operator_actions[0].action == "REVIEW_FOR_COMMERCIAL_ANALYSIS"
    assert len(result.verified_cases) == 1


def test_registry_artifacts_round_trip_and_keep_commercial_top5_empty(tmp_path: Path):
    result = update_case_registry({}, [observation()], captured_at="2026-07-30T12:00:00Z")
    paths = write_case_tracker_artifacts(result, tmp_path)

    loaded = load_case_registry(paths["registry"])
    commercial = json.loads(paths["commercial_top5"].read_text(encoding="utf-8"))
    actions = json.loads(paths["operator_actions"].read_text(encoding="utf-8"))
    alerts = json.loads(paths["alerts"].read_text(encoding="utf-8"))

    assert list(loaded) == ["estate:938018014"]
    assert loaded["estate:938018014"].state == NO_PUBLIC_SALE_CHANNEL_FOUND
    assert commercial == []
    assert actions[0]["recommended_action"] == "ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL"
    assert alerts == []


def test_duplicate_case_observation_is_rejected():
    item = observation()
    with pytest.raises(ValueError, match="duplicate observation"):
        update_case_registry({}, [item, item])


def test_report_without_estate_object_is_rejected():
    with pytest.raises(ValueError, match="estate object"):
        observation_from_sale_channel_report({"candidates": []})


def test_source_report_history_is_deduplicated():
    first_observation = observation_from_sale_channel_report(
        report(),
        source_report="artifacts/menswear/sale-channel-search.json",
    )
    first = update_case_registry({}, [first_observation], captured_at="2026-07-30T12:00:00Z")
    previous = {case.case_id: case for case in first.cases}
    second = update_case_registry(
        previous,
        [first_observation],
        captured_at="2026-07-31T12:00:00Z",
    )

    assert second.cases[0].source_reports == (
        "artifacts/menswear/sale-channel-search.json",
    )
