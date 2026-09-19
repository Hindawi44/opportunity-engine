"""Deterministic tests: no network, paid search, purchases or database changes."""
import copy

import pytest

from scripts.run_event_first_hunter_pilot import build_event_report, render_arabic


def source_report(**overrides):
    source = {
        "source_key": "BRREG_ENHETSREGISTERET_API",
        "source_country": "NO",
        "status": "SUCCESS",
        "generated_at": "2026-09-19T08:00:00Z",
        "retrieved_record_count": 12,
        "candidate_entity_count": 1,
        "update_limit": 500,
        "entity_limit": 20,
        "errors": [],
        "signals": [{
            "signal_id": "official-notice:no:brreg:123456789:konkurs",
            "metadata": {"organisation_number": "123456789", "event_kind": "KONKURS"},
            "company_name": "Eksempel Tekstil AS",
            "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
            "event_date": "2026-09-18T00:00:00Z",
            "observed_at": "2026-09-19T08:00:00Z",
            "location": "Namsos",
        }],
    }
    source.update(overrides)
    return source


def test_event_is_only_a_lead_not_verified_inventory():
    result = build_event_report(source_report())
    assert result["coverage"] == "BOUNDED_SCAN_NOT_FULL_REGISTRY"
    assert result["unique_event_count"] == 1
    assert result["verified_inventory_links"] == result["paid_search_requests"] == 0
    lead = result["events"][0]
    assert lead["record_type"] == "OFFICIAL_EVENT_SIGNAL_ONLY"
    assert lead["inventory_link"] is None
    assert lead["inventory_verified"] is False
    assert "Eksempel Tekstil" in lead["research_query"]
    assert "لم يُعثر عليه" in render_arabic(result)
    assert result["automatic_purchase"] is False


def test_successful_zero_is_limited_sample_not_full_market_zero():
    result = build_event_report(source_report(status="VALID_ZERO", signals=[], candidate_entity_count=0))
    assert result["unique_event_count"] == 0
    assert result["coverage"] == "BOUNDED_SCAN_NOT_FULL_REGISTRY"
    assert "العينة المحدودة" in render_arabic(result)


def test_blocked_source_is_not_reported_as_zero_opportunities():
    result = build_event_report(source_report(status="BLOCKED_DIRECT_ACCESS", signals=[], errors=["connection failed"]))
    assert result["coverage"] == "BLOCKED_OR_FAILED"
    assert "لا يُعدّ ذلك صفر فرص" in render_arabic(result)


def test_hitting_update_or_entity_caps_reports_partial_coverage():
    for changes in ({"retrieved_record_count": 500}, {"candidate_entity_count": 21}):
        assert build_event_report(source_report(**changes))["coverage"] == "PARTIAL_BOUNDED_SCAN"


def test_rejects_wrong_source_and_forged_or_unrelated_urls():
    with pytest.raises(ValueError):
        build_event_report(source_report(source_key="ARBITRARY_SITE"))
    wrong = copy.deepcopy(source_report())
    wrong["signals"][0]["source_url"] = "https://some-shop.example/product"
    result = build_event_report(wrong)
    assert result["events"] == []
    assert result["invalid_signal_count"] == 1
    assert result["coverage"] == "PARTIAL_BOUNDED_SCAN"


def test_deduplicate_events_and_limit_visible_cards_without_losing_count():
    raw = source_report()
    clone = copy.deepcopy(raw["signals"][0])
    raw["signals"].append(clone)
    assert build_event_report(raw)["unique_event_count"] == 1
    new_event = copy.deepcopy(clone)
    new_event["signal_id"] = "official-notice:no:brreg:987654321:konkurs"
    new_event["metadata"]["organisation_number"] = "987654321"
    new_event["source_url"] = "https://data.brreg.no/enhetsregisteret/api/enheter/987654321"
    raw["signals"].append(new_event)
    result = build_event_report(raw, max_cards=1)
    assert result["unique_event_count"] == 2
    assert result["displayed_event_count"] == 1
    assert result["truncated_display_count"] == 1
