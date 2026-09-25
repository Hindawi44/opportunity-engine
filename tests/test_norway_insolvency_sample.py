"""Contract: official bankruptcy event != assets for sale; no sector gate."""
from datetime import datetime, timezone

import pytest

from scripts.run_norway_insolvency_sample import (
    FILTERS,
    build_recent_sample,
    render_arabic,
    sample,
)

NOW = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)


def entity(number="123456789", **changes):
    value = {"organisasjonsnummer": number, "navn": "Nord Industri AS",
             "konkurs": True, "konkursdato": "2026-09-18",
             "forretningsadresse": {"landkode": "NO", "poststed": "Namsos"},
             "naeringskode1": {"kode": "25.110", "beskrivelse": "Metal structures"}}
    value.update(changes)
    return value


def registry(rows):
    return {"_embedded": {"enheter": rows}, "page": {"totalElements": len(rows)}}


def recent_source(*, status="SUCCESS", signals=None, errors=None):
    return {
        "source_key": "BRREG_ENHETSREGISTERET_API",
        "source_country": "NO",
        "status": status,
        "bankruptcy_only": True,
        "all_sectors": True,
        "lookback_days": 7,
        "retrieved_record_count": 12,
        "candidate_entity_count": 1,
        "entity_fetch_count": 1,
        "errors": errors or [],
        "signals": signals or [],
    }


def recent_signal():
    return {
        "signal_id": "official-notice:no:brreg:123456789:konkurs",
        "company_name": "Nord Industri AS",
        "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
        "event_date": "2026-09-23T00:00:00Z",
        "location": "Namsos",
        "metadata": {
            "organisation_number": "123456789",
            "event_kind": "KONKURS",
        },
    }


def test_all_sectors_company_is_discovered_from_official_status_not_clothing():
    calls = []
    def fetcher(status, size):
        calls.append((status, size))
        return registry([entity()] if status == "konkurs" else [])
    report = sample(fetcher=fetcher, now=NOW)
    assert calls == [(status, 25) for status in FILTERS]
    assert FILTERS == ("konkurs",)
    assert report["scope"] == "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS"
    assert report["unique_sampled_companies"] == 1
    assert report["events"][0]["company_name"] == "Nord Industri AS"
    assert report["events"][0]["event_kinds"] == ["konkurs"]
    assert report["events"][0]["official_url"].endswith("/123456789")
    assert report["events"][0]["sale_listing_url"] is None
    assert report["verified_insolvency_sale_count"] == 0
    assert report["verified_insolvency_sale_links"] == []
    assert report["ordinary_auction_listings_excluded"] is True
    assert report["liquidation_events_excluded"] is True
    assert report["forced_dissolution_events_excluded"] is True
    assert report["surplus_only_links_excluded"] is True
    assert report["dealer_links_excluded"] is True
    assert "avvikling" not in report["events"][0]["followup_search"].casefold()
    assert "لا يُعامل أي إعلان مزاد عام" in render_arabic(report)


def test_recent_official_updates_become_bankruptcy_only_events():
    report = build_recent_sample(
        recent_source(signals=[recent_signal()]),
        max_cards=5,
        update_limit=500,
        entity_limit=20,
        now=NOW,
    )
    assert report["source_mode"] == "RECENT_OFFICIAL_UPDATES"
    assert report["coverage"] == "BOUNDED_RECENT_UPDATES_NOT_FULL_NORWAY"
    assert report["events"][0]["event_kinds"] == ["konkurs"]
    assert report["events"][0]["event_date"] == "2026-09-23"
    assert "avvikling" not in report["events"][0]["followup_search"].casefold()
    assert "تحديثات رسمية حديثة" in render_arabic(report)


def test_recent_converter_rejects_any_non_bankruptcy_signal():
    signal = recent_signal()
    signal["metadata"]["event_kind"] = "AVVIKLING"
    report = build_recent_sample(recent_source(signals=[signal]), now=NOW)
    assert report["events"] == []
    assert report["invalid_official_signal_count"] == 1
    assert report["coverage"] == "PARTIAL_SOURCE_FAILURE"


def test_recent_official_source_failure_is_not_reported_as_zero_events():
    report = build_recent_sample(
        recent_source(
            status="BLOCKED_DIRECT_ACCESS",
            errors=["official API unavailable"],
        ),
        now=NOW,
    )
    assert report["coverage"] == "SOURCE_UNAVAILABLE"
    assert report["filter_queries_successful"] == 0
    assert report["source_errors"]


def test_liquidation_flags_cannot_enter_bankruptcy_only_sample():
    def fetcher(status, size):
        assert status == "konkurs"
        return registry([
            entity(konkurs=False, underAvvikling=True),
            entity(
                "222222222",
                konkurs=False,
                underTvangsavviklingEllerTvangsopplosning=True,
            ),
        ])
    report = sample(fetcher=fetcher, now=NOW)
    assert report["unique_sampled_companies"] == 0
    assert report["events"] == []


def test_unrelated_ordinary_listing_or_false_registry_flags_do_not_qualify():
    def fetcher(status, size):
        return registry([entity(konkurs=False, underAvvikling=False,
                                underTvangsavviklingEllerTvangsopplosning=False,
                                listing_url="https://www.auksjonen.no/example"),
                         entity("222222222", forretningsadresse={"landkode": "SE"}),
                         entity("not-an-org-number")])
    report = sample(fetcher=fetcher, now=NOW)
    assert report["unique_sampled_companies"] == 0
    assert report["verified_insolvency_sale_count"] == 0


def test_one_failed_status_is_not_converted_to_zero_coverage():
    def fetcher(status, size):
        raise RuntimeError("HTTP 503")
    report = sample(fetcher=fetcher, now=NOW)
    assert report["coverage"] == "SOURCE_UNAVAILABLE"
    assert report["filter_queries_successful"] == 0
    assert len(report["source_errors"]) == 1


def test_total_failure_is_explicit_not_zero_opportunities():
    def broken(status, size):
        raise RuntimeError("offline")
    report = sample(fetcher=broken, now=NOW)
    assert report["coverage"] == "SOURCE_UNAVAILABLE"
    assert report["filter_queries_successful"] == 0
    assert len(report["source_errors"]) == 1


def test_invalid_payload_and_bounded_budget_fail_closed():
    report = sample(fetcher=lambda status, size: {"_embedded": {}, "page": {"totalElements": 5}}, now=NOW)
    assert report["coverage"] == "SOURCE_UNAVAILABLE"
    assert report["unique_sampled_companies"] == 0
    for invalid in (0, 51):
        with pytest.raises(ValueError):
            sample(size=invalid)
    with pytest.raises(ValueError):
        sample(max_cards=11)
    report = sample(fetcher=lambda status, size: registry([]), now=NOW)
    assert report["paid_provider_requests"] == 0
    assert all(report[k] is False for k in ("automatic_contact", "automatic_bid", "automatic_purchase", "automatic_payment"))
