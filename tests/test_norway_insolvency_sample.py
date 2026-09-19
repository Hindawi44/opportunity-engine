"""Contract: official insolvency event != assets for sale; no sector gate."""
from datetime import datetime, timezone

import pytest

from scripts.run_norway_insolvency_sample import FILTERS, render_arabic, sample

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


def test_all_sectors_company_is_discovered_from_official_status_not_clothing():
    calls = []
    def fetcher(status, size):
        calls.append((status, size))
        return registry([entity()] if status == "konkurs" else [])
    report = sample(fetcher=fetcher, now=NOW)
    assert calls == [(status, 25) for status in FILTERS]
    assert report["scope"] == "NO_ONLY_INSOLVENCY_LIQUIDATION_ALL_SECTORS"
    assert report["unique_sampled_companies"] == 1
    assert report["events"][0]["company_name"] == "Nord Industri AS"
    assert report["events"][0]["event_kinds"] == ["konkurs"]
    assert report["events"][0]["official_url"].endswith("/123456789")
    assert report["events"][0]["sale_listing_url"] is None
    assert report["verified_insolvency_sale_count"] == 0
    assert report["verified_insolvency_sale_links"] == []
    assert report["ordinary_auction_listings_excluded"] is True
    assert "لا يُعامل أي إعلان مزاد عام" in render_arabic(report)


def test_bankruptcy_liquidation_and_forced_liquidation_dedupe_same_company():
    def fetcher(status, size):
        return registry([entity(**{status: True})])
    report = sample(fetcher=fetcher, now=NOW)
    assert report["unique_sampled_companies"] == 1
    assert report["events"][0]["event_kinds"] == list(FILTERS)
    assert report["displayed_event_count"] == 1


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
        if status == "konkurs":
            raise RuntimeError("HTTP 503")
        return registry([])
    report = sample(fetcher=fetcher, now=NOW)
    assert report["coverage"] == "PARTIAL_SOURCE_FAILURE"
    assert report["filter_queries_successful"] == 2
    assert len(report["source_errors"]) == 1


def test_total_failure_is_explicit_not_zero_opportunities():
    def broken(status, size):
        raise RuntimeError("offline")
    report = sample(fetcher=broken, now=NOW)
    assert report["coverage"] == "SOURCE_UNAVAILABLE"
    assert report["filter_queries_successful"] == 0
    assert len(report["source_errors"]) == 3


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
