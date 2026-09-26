"""Persistent 60-day follow-up for official Norwegian bankruptcies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scripts.run_norway_bankruptcy_watchlist import (
    SALE_VERIFIED,
    WAITING,
    finalize_watchlist,
    prepare_watchlist,
)

NOW = datetime(2026, 9, 26, 6, tzinfo=timezone.utc)
ORG = "123456789"
COMPANY = "Nord Industri AS"
OFFICIAL = f"https://data.brreg.no/enhetsregisteret/api/enheter/{ORG}"
SALE = "https://advokatfirma.no/konkursbo/nord-industri"


def events(*, include: bool = True) -> dict:
    rows = []
    if include:
        rows.append(
            {
                "organisation_number": ORG,
                "company_name": COMPANY,
                "official_url": OFFICIAL,
                "source_country": "NO",
                "event_kinds": ["konkurs"],
                "event_date": "2026-09-25",
                "location": "Namsos",
            }
        )
    return {
        "schema_version": "norway-insolvency-event-sample-1",
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS",
        "captured_at": NOW.isoformat(),
        "events": rows,
    }


def link_row() -> dict:
    return {
        "classification": "OFFICIAL_BANKRUPTCY_LINKED_ASSET_SALE",
        "company_name": COMPANY,
        "organisation_number": ORG,
        "event_kind": "KONKURS",
        "event_date": "2026-09-25",
        "location": "Namsos",
        "official_bankruptcy_url": OFFICIAL,
        "sale_url": SALE,
        "sale_page_title": "Nord Industri AS konkursbo – auksjon",
        "search_provider": "Exa",
        "identity_match_method": "OFFICIAL_ORGANISATION_NUMBER_ON_PAGE",
        "bankruptcy_language_verified_on_page": True,
        "sale_language_verified_on_page": True,
        "bankruptcy_estate_sale_relationship_verified_on_page": True,
        "liquidation_only": False,
        "surplus_only": False,
        "dealer_only": False,
        "ended_marker_found": False,
        "inventory_contents_verified": False,
        "sale_availability_fully_verified": False,
        "human_review_required": True,
    }


def link_report(
    *, links=None, rejected=None, paid=2, coverage="BOUNDED_BANKRUPTCY_LINK_HUNT"
) -> dict:
    rows = list(links or [])
    return {
        "schema_version": "norway-bankruptcy-link-hunt-1.0",
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_LINK_CHASE",
        "captured_at": NOW.isoformat(),
        "coverage": coverage,
        "event_input_count": 1,
        "events_searched": 1,
        "official_bankruptcy_events_considered": 1,
        "provider_request_counts": {
            "Exa": min(paid, 1),
            "Brave Search": max(0, paid - 1),
        },
        "provider_request_counts_by_organisation": (
            {
                ORG: {
                    "Exa": min(paid, 1),
                    "Brave Search": max(0, paid - 1),
                }
            }
            if paid
            else {}
        ),
        "paid_provider_requests": paid,
        "page_reads": 1,
        "page_read_limit": 15,
        "verified_bankruptcy_sale_link_count": len(rows),
        "verified_bankruptcy_sale_links": rows,
        "rejected_hit_count": len(rejected or []),
        "rejected_hits": list(rejected or []),
        "provider_errors": [],
        "policy": {},
        "openai_requests": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_new_bankruptcy_survives_empty_days_and_rechecks_after_three_days() -> None:
    watchlist, due, delta = prepare_watchlist(events(), now=NOW)

    assert len(watchlist["cases"]) == 1
    case = watchlist["cases"][0]
    assert case["status"] == WAITING
    assert case["expires_at"] == (NOW + timedelta(days=60)).isoformat()
    assert due["watchlist_selected_case_count"] == 1
    assert delta["changes"][0]["change_type"] == "OFFICIAL_BANKRUPTCY_ADDED"

    watchlist, _, _ = finalize_watchlist(
        watchlist, due, link_report(links=[]), delta, now=NOW
    )
    case = watchlist["cases"][0]
    assert case["check_count"] == 1
    assert case["paid_search_requests"] == 2
    assert case["next_check_at"] == (NOW + timedelta(days=3)).isoformat()

    one_day, not_due, no_change = prepare_watchlist(
        events(include=False), watchlist, now=NOW + timedelta(days=1)
    )
    assert len(one_day["cases"]) == 1
    assert not_due["events"] == []
    assert no_change["change_count"] == 0

    _, due_again, _ = prepare_watchlist(
        events(include=False), one_day, now=NOW + timedelta(days=3)
    )
    assert due_again["watchlist_selected_case_count"] == 1
    assert due_again["events"][0]["organisation_number"] == ORG


def test_new_verified_link_is_forwarded_once_and_then_rechecked_directly() -> None:
    watchlist, due, delta = prepare_watchlist(events(), now=NOW)
    finalized, first_delta, new_link_report = finalize_watchlist(
        watchlist,
        due,
        link_report(links=[link_row()], paid=1),
        delta,
        now=NOW,
    )
    case = finalized["cases"][0]
    assert case["status"] == SALE_VERIFIED
    assert case["verified_sale_links"][0]["status"] == "ACTIVE"
    assert new_link_report["verified_bankruptcy_sale_links"] == [link_row()]
    assert {change["change_type"] for change in first_delta["changes"]} >= {
        "NEW_VERIFIED_BANKRUPTCY_SALE_LINK",
        "CASE_STATUS_CHANGED",
    }

    prepared, due_again, second_delta = prepare_watchlist(
        events(include=False), finalized, now=NOW + timedelta(days=3)
    )
    assert due_again["events"][0]["known_sale_urls"] == [SALE]
    repeated = link_row()
    repeated["search_provider"] = "Watchlist direct recheck"
    repeated_final, repeated_delta, repeated_new = finalize_watchlist(
        prepared,
        due_again,
        link_report(links=[repeated], paid=0),
        second_delta,
        now=NOW + timedelta(days=3),
    )
    assert repeated_final["cases"][0]["status"] == SALE_VERIFIED
    assert repeated_delta["change_count"] == 0
    assert repeated_new["verified_bankruptcy_sale_link_count"] == 0


def test_explicit_ended_marker_reopens_case_without_losing_history() -> None:
    watchlist, due, delta = prepare_watchlist(events(), now=NOW)
    active, _, _ = finalize_watchlist(
        watchlist, due, link_report(links=[link_row()]), delta, now=NOW
    )
    prepared, due_again, clean_delta = prepare_watchlist(
        events(include=False), active, now=NOW + timedelta(days=3)
    )
    rejection = {
        "organisation_number": ORG,
        "company_name": COMPANY,
        "url": SALE,
        "provider": "Watchlist direct recheck",
        "reason": "SALE_PAGE_EXPLICITLY_ENDED",
    }
    ended, ended_delta, _ = finalize_watchlist(
        prepared,
        due_again,
        link_report(links=[], rejected=[rejection], paid=1),
        clean_delta,
        now=NOW + timedelta(days=3),
    )
    assert ended["cases"][0]["status"] == WAITING
    assert ended["cases"][0]["verified_sale_links"][0]["status"] == "ENDED"
    assert {change["change_type"] for change in ended_delta["changes"]} == {
        "VERIFIED_SALE_LINK_ENDED",
        "CASE_STATUS_CHANGED",
    }


def test_case_expires_only_after_sixty_days() -> None:
    watchlist, _, _ = prepare_watchlist(events(), now=NOW)
    before, _, _ = prepare_watchlist(
        events(include=False), watchlist, now=NOW + timedelta(days=59)
    )
    assert len(before["cases"]) == 1
    expired, due, delta = prepare_watchlist(
        events(include=False), before, now=NOW + timedelta(days=60)
    )
    assert expired["cases"] == []
    assert due["events"] == []
    assert delta["changes"][0]["change_type"] == "CASE_EXPIRED_AFTER_60_DAYS"


def test_temporary_direct_recheck_failure_retries_next_day() -> None:
    watchlist, due, delta = prepare_watchlist(events(), now=NOW)
    failed, _, _ = finalize_watchlist(
        watchlist,
        due,
        link_report(
            links=[],
            paid=0,
            coverage="DIRECT_WATCHLIST_RECHECK_FAILED",
        ),
        delta,
        now=NOW,
    )
    assert failed["cases"][0]["next_check_at"] == (NOW + timedelta(days=1)).isoformat()


def test_mixed_or_liquidation_event_can_never_enter_watchlist() -> None:
    report = events()
    report["events"][0]["event_kinds"] = ["underAvvikling"]
    with pytest.raises(ValueError, match="official Norwegian bankruptcy"):
        prepare_watchlist(report, now=NOW)

    report = events()
    report["scope"] = "NO_ONLY_INSOLVENCY_LIQUIDATION_ALL_SECTORS"
    with pytest.raises(ValueError, match="Liquidation or mixed"):
        prepare_watchlist(report, now=NOW)


def test_due_budget_defers_without_dropping_cases() -> None:
    rows = []
    for index in range(6):
        org = f"12345678{index}"
        rows.append(
            {
                "organisation_number": org,
                "company_name": f"Selskap {index} AS",
                "official_url": f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}",
                "source_country": "NO",
                "event_kinds": ["konkurs"],
                "event_date": "2026-09-25",
                "location": "Namsos",
            }
        )
    report = events(include=False)
    report["events"] = rows
    watchlist, due, _ = prepare_watchlist(report, now=NOW, max_due_cases=5)
    assert len(watchlist["cases"]) == 6
    assert due["watchlist_due_case_count"] == 6
    assert due["watchlist_selected_case_count"] == 5
    assert due["watchlist_deferred_due_case_count"] == 1
