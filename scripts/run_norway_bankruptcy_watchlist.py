#!/usr/bin/env python3
"""Persist and schedule follow-up for official Norwegian bankruptcies.

The watchlist is deliberately small and deterministic.  An official bankruptcy
event is retained for sixty days, even when no sale link is visible on the day
of discovery.  Cases are rechecked on a bounded cadence and only newly verified
sale links are forwarded to the paid OpenAI analysis stage.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

WATCHLIST_SCHEMA = "norway-bankruptcy-watchlist-1.0"
DELTA_SCHEMA = "norway-bankruptcy-watchlist-delta-1.0"
EVENT_SCHEMA = "norway-insolvency-event-sample-1"
EVENT_SCOPE = "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS"
LINK_SCHEMA = "norway-bankruptcy-link-hunt-1.0"
LINK_SCOPE = "NO_ONLY_OFFICIAL_BANKRUPTCY_LINK_CHASE"
WATCHLIST_SCOPE = "NO_ONLY_OFFICIAL_BANKRUPTCY_60_DAY_FOLLOW_UP"

WAITING = "WAITING_FOR_SALE"
SALE_VERIFIED = "SALE_LINK_VERIFIED"
ALLOWED_CASE_STATUSES = {WAITING, SALE_VERIFIED}
ACTIVE_LINK = "ACTIVE"
ENDED_LINK = "ENDED"

DEFAULT_RETENTION_DAYS = 60
DEFAULT_RECHECK_DAYS = 3
DEFAULT_MAX_DUE_CASES = 5
MAX_CASES = 2_000
MAX_LINKS_PER_CASE = 5


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse_instant(value: object, *, field: str) -> datetime:
    text = _compact(value)
    if not text:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 instant") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _official_identity(row: Mapping[str, Any]) -> tuple[str, str, str]:
    organisation_number = _compact(row.get("organisation_number"))
    company_name = _compact(row.get("company_name"))
    official_url = _compact(row.get("official_url"))
    expected = (
        "https://data.brreg.no/enhetsregisteret/api/enheter/" + organisation_number
    )
    if (
        row.get("source_country") != "NO"
        or row.get("event_kinds") != ["konkurs"]
        or len(organisation_number) != 9
        or not organisation_number.isascii()
        or not organisation_number.isdigit()
        or not company_name
        or official_url != expected
    ):
        raise ValueError("Watchlist input must be one official Norwegian bankruptcy")
    return organisation_number, company_name, official_url


def _safe_norwegian_sale_url(value: object) -> str:
    raw = _compact(value)
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid verified sale URL") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not host.endswith(".no")
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or parsed.fragment
        or not parsed.path.startswith("/")
        or len(raw) > 2_000
    ):
        raise ValueError("Verified sale URL must be a Norwegian HTTPS URL")
    return raw


def _empty_watchlist(now: datetime) -> dict[str, Any]:
    return {
        "schema_version": WATCHLIST_SCHEMA,
        "scope": WATCHLIST_SCOPE,
        "generated_at": _iso(now),
        "retention_days": DEFAULT_RETENTION_DAYS,
        "recheck_days": DEFAULT_RECHECK_DAYS,
        "cases": [],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _validate_sale_link(row: Mapping[str, Any]) -> dict[str, Any]:
    url = _safe_norwegian_sale_url(row.get("sale_url"))
    status = _compact(row.get("status"))
    if status not in {ACTIVE_LINK, ENDED_LINK}:
        raise ValueError("Unknown watchlist sale-link status")
    first_verified_at = _parse_instant(
        row.get("first_verified_at"), field="first_verified_at"
    )
    last_verified_at = _parse_instant(
        row.get("last_verified_at"), field="last_verified_at"
    )
    if last_verified_at < first_verified_at:
        raise ValueError("Sale-link verification timestamps are reversed")
    ended_at: str | None = None
    if status == ENDED_LINK:
        ended_at = _iso(_parse_instant(row.get("ended_at"), field="ended_at"))
    return {
        "sale_url": url,
        "status": status,
        "sale_page_title": _compact(row.get("sale_page_title"))[:500],
        "identity_match_method": _compact(row.get("identity_match_method"))[:100],
        "first_verified_at": _iso(first_verified_at),
        "last_verified_at": _iso(last_verified_at),
        "ended_at": ended_at,
    }


def _validate_case(row: Mapping[str, Any]) -> dict[str, Any]:
    organisation_number, company_name, official_url = _official_identity(row)
    status = _compact(row.get("status"))
    if status not in ALLOWED_CASE_STATUSES:
        raise ValueError("Unknown bankruptcy-watchlist case status")
    first_seen = _parse_instant(row.get("first_seen_at"), field="first_seen_at")
    last_seen = _parse_instant(row.get("last_seen_at"), field="last_seen_at")
    expires_at = _parse_instant(row.get("expires_at"), field="expires_at")
    next_check = _parse_instant(row.get("next_check_at"), field="next_check_at")
    if last_seen < first_seen or expires_at <= first_seen:
        raise ValueError("Invalid watchlist case timeline")
    last_checked_raw = row.get("last_checked_at")
    last_checked = (
        _iso(_parse_instant(last_checked_raw, field="last_checked_at"))
        if _compact(last_checked_raw)
        else None
    )
    links_raw = row.get("verified_sale_links")
    if not isinstance(links_raw, list) or len(links_raw) > MAX_LINKS_PER_CASE:
        raise ValueError("verified_sale_links must be a bounded list")
    links: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for raw_link in links_raw:
        if not isinstance(raw_link, Mapping):
            raise ValueError("Invalid watchlist sale-link row")
        link = _validate_sale_link(raw_link)
        if link["sale_url"] in seen_urls:
            raise ValueError("Duplicate watchlist sale URL")
        seen_urls.add(link["sale_url"])
        links.append(link)
    active = any(link["status"] == ACTIVE_LINK for link in links)
    expected_status = SALE_VERIFIED if active else WAITING
    if status != expected_status:
        raise ValueError("Case status does not match active verified sale links")
    check_count = row.get("check_count", 0)
    paid_search_requests = row.get("paid_search_requests", 0)
    if (
        not isinstance(check_count, int)
        or check_count < 0
        or not isinstance(paid_search_requests, int)
        or paid_search_requests < 0
    ):
        raise ValueError("Watchlist counters must be non-negative integers")
    event_date = _compact(row.get("event_date")) or None
    if event_date is not None:
        try:
            datetime.fromisoformat(event_date[:10])
        except ValueError as exc:
            raise ValueError("event_date must be an ISO date") from exc
        event_date = event_date[:10]
    return {
        "organisation_number": organisation_number,
        "company_name": company_name,
        "official_url": official_url,
        "source_country": "NO",
        "event_kinds": ["konkurs"],
        "event_date": event_date,
        "location": _compact(row.get("location")) or None,
        "first_seen_at": _iso(first_seen),
        "last_seen_at": _iso(last_seen),
        "expires_at": _iso(expires_at),
        "status": status,
        "last_checked_at": last_checked,
        "next_check_at": _iso(next_check),
        "check_count": check_count,
        "paid_search_requests": paid_search_requests,
        "last_check_outcome": _compact(row.get("last_check_outcome")) or None,
        "verified_sale_links": links,
    }


def validate_watchlist(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate restored state before it can affect current discovery."""
    if payload.get("schema_version") != WATCHLIST_SCHEMA:
        raise ValueError("Unknown Norway bankruptcy-watchlist schema")
    if payload.get("scope") != WATCHLIST_SCOPE:
        raise ValueError("Foreign or mixed watchlist scope is forbidden")
    generated_at = _parse_instant(payload.get("generated_at"), field="generated_at")
    retention_days = payload.get("retention_days")
    recheck_days = payload.get("recheck_days")
    if retention_days != DEFAULT_RETENTION_DAYS or recheck_days != DEFAULT_RECHECK_DAYS:
        raise ValueError("Watchlist cadence contract changed")
    rows = payload.get("cases")
    if not isinstance(rows, list) or len(rows) > MAX_CASES:
        raise ValueError("Watchlist cases must be a bounded list")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("Invalid bankruptcy-watchlist case")
        case = _validate_case(raw)
        organisation_number = case["organisation_number"]
        if organisation_number in seen:
            raise ValueError("Duplicate organisation number in watchlist")
        seen.add(organisation_number)
        cases.append(case)
    cases.sort(key=lambda item: item["organisation_number"])
    return {
        "schema_version": WATCHLIST_SCHEMA,
        "scope": WATCHLIST_SCOPE,
        "generated_at": _iso(generated_at),
        "retention_days": DEFAULT_RETENTION_DAYS,
        "recheck_days": DEFAULT_RECHECK_DAYS,
        "cases": cases,
        "active_case_count": len(cases),
        "waiting_case_count": sum(case["status"] == WAITING for case in cases),
        "verified_sale_case_count": sum(
            case["status"] == SALE_VERIFIED for case in cases
        ),
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _validate_events_report(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("schema_version") != EVENT_SCHEMA:
        raise ValueError("Official Norway bankruptcy event report is required")
    if payload.get("scope") != EVENT_SCOPE:
        raise ValueError("Liquidation or mixed insolvency input is forbidden")
    rows = payload.get("events")
    if not isinstance(rows, list):
        raise ValueError("Official event report must contain an events list")
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("Invalid official bankruptcy event")
        organisation_number, company_name, official_url = _official_identity(raw)
        if organisation_number in seen:
            continue
        seen.add(organisation_number)
        events.append(
            {
                "organisation_number": organisation_number,
                "company_name": company_name,
                "official_url": official_url,
                "source_country": "NO",
                "event_kinds": ["konkurs"],
                "event_date": _compact(raw.get("event_date"))[:10] or None,
                "location": _compact(raw.get("location")) or None,
            }
        )
    return events


def _new_delta(now: datetime) -> dict[str, Any]:
    return {
        "schema_version": DELTA_SCHEMA,
        "scope": WATCHLIST_SCOPE,
        "generated_at": _iso(now),
        "changes": [],
        "change_count": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _append_change(
    delta: dict[str, Any],
    *,
    change_type: str,
    case: Mapping[str, Any],
    now: datetime,
    **extra: Any,
) -> None:
    row = {
        "change_type": change_type,
        "occurred_at": _iso(now),
        "organisation_number": case["organisation_number"],
        "company_name": case["company_name"],
    }
    row.update(extra)
    delta["changes"].append(row)
    delta["change_count"] = len(delta["changes"])


def _new_case(
    event: Mapping[str, Any], now: datetime, retention_days: int
) -> dict[str, Any]:
    return {
        **dict(event),
        "first_seen_at": _iso(now),
        "last_seen_at": _iso(now),
        "expires_at": _iso(now + timedelta(days=retention_days)),
        "status": WAITING,
        "last_checked_at": None,
        "next_check_at": _iso(now),
        "check_count": 0,
        "paid_search_requests": 0,
        "last_check_outcome": None,
        "verified_sale_links": [],
    }


def _case_event(case: Mapping[str, Any]) -> dict[str, Any]:
    active_urls = [
        link["sale_url"]
        for link in case["verified_sale_links"]
        if link["status"] == ACTIVE_LINK
    ]
    return {
        "organisation_number": case["organisation_number"],
        "company_name": case["company_name"],
        "official_url": case["official_url"],
        "source_country": "NO",
        "event_kinds": ["konkurs"],
        "event_date": case.get("event_date"),
        "location": case.get("location"),
        "evidence_status": "PERSISTED_OFFICIAL_BANKRUPTCY_WATCHLIST_CASE",
        "tracking_status": case["status"],
        "first_seen_at": case["first_seen_at"],
        "expires_at": case["expires_at"],
        # Two direct checks per case keep five due cases within the existing
        # fifteen-page budget while avoiding a paid search for a still-live URL.
        "known_sale_urls": active_urls[:2],
        "followup_search": (
            f'"{case["company_name"]}" "{case["organisation_number"]}" '
            "konkursbo (bostyrer OR auksjon OR selges OR varelager OR driftsmidler)"
        ),
    }


def prepare_watchlist(
    events_report: Mapping[str, Any],
    previous_watchlist: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    recheck_days: int = DEFAULT_RECHECK_DAYS,
    max_due_cases: int = DEFAULT_MAX_DUE_CASES,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Merge new official events and select the oldest due cases fairly."""
    stamp = _utc(now)
    if retention_days != DEFAULT_RETENTION_DAYS:
        raise ValueError("V1 retention must remain exactly 60 days")
    if recheck_days != DEFAULT_RECHECK_DAYS:
        raise ValueError("V1 paid-search recheck cadence must remain exactly 3 days")
    if not 1 <= max_due_cases <= DEFAULT_MAX_DUE_CASES:
        raise ValueError("max_due_cases must be between 1 and 5")
    events = _validate_events_report(events_report)
    watchlist = (
        validate_watchlist(previous_watchlist)
        if previous_watchlist is not None
        else _empty_watchlist(stamp)
    )
    delta = _new_delta(stamp)
    active_cases: list[dict[str, Any]] = []
    for case in watchlist["cases"]:
        if _parse_instant(case["expires_at"], field="expires_at") <= stamp:
            _append_change(
                delta,
                change_type="CASE_EXPIRED_AFTER_60_DAYS",
                case=case,
                now=stamp,
                previous_status=case["status"],
            )
            continue
        active_cases.append(case)
    by_org = {case["organisation_number"]: case for case in active_cases}

    for event in events:
        organisation_number = event["organisation_number"]
        case = by_org.get(organisation_number)
        if case is None:
            case = _new_case(event, stamp, retention_days)
            active_cases.append(case)
            by_org[organisation_number] = case
            _append_change(
                delta,
                change_type="OFFICIAL_BANKRUPTCY_ADDED",
                case=case,
                now=stamp,
                event_date=case.get("event_date"),
                expires_at=case["expires_at"],
            )
            continue
        changed_fields: list[str] = []
        for field in ("company_name", "event_date", "location"):
            incoming = event.get(field)
            if incoming and incoming != case.get(field):
                case[field] = incoming
                changed_fields.append(field)
        case["last_seen_at"] = _iso(stamp)
        if changed_fields:
            _append_change(
                delta,
                change_type="OFFICIAL_BANKRUPTCY_DATA_CHANGED",
                case=case,
                now=stamp,
                changed_fields=changed_fields,
            )

    due = [
        case
        for case in active_cases
        if _parse_instant(case["next_check_at"], field="next_check_at") <= stamp
    ]
    due.sort(
        key=lambda case: (
            _parse_instant(case["next_check_at"], field="next_check_at"),
            _parse_instant(case["first_seen_at"], field="first_seen_at"),
            case["organisation_number"],
        )
    )
    selected = due[:max_due_cases]
    active_cases.sort(key=lambda case: case["organisation_number"])
    watchlist = {
        **watchlist,
        "generated_at": _iso(stamp),
        "retention_days": retention_days,
        "recheck_days": recheck_days,
        "cases": active_cases,
        "active_case_count": len(active_cases),
        "waiting_case_count": sum(case["status"] == WAITING for case in active_cases),
        "verified_sale_case_count": sum(
            case["status"] == SALE_VERIFIED for case in active_cases
        ),
    }
    due_report = {
        "schema_version": EVENT_SCHEMA,
        "scope": EVENT_SCOPE,
        "captured_at": _iso(stamp),
        "source_mode": "PERSISTED_60_DAY_BANKRUPTCY_WATCHLIST",
        "coverage": "BOUNDED_DUE_WATCHLIST_CASES",
        "watchlist_active_case_count": len(active_cases),
        "watchlist_due_case_count": len(due),
        "watchlist_selected_case_count": len(selected),
        "watchlist_deferred_due_case_count": max(0, len(due) - len(selected)),
        "events": [_case_event(case) for case in selected],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    return validate_watchlist(watchlist), due_report, delta


def _validate_delta(payload: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    if (
        payload.get("schema_version") != DELTA_SCHEMA
        or payload.get("scope") != WATCHLIST_SCOPE
    ):
        raise ValueError("Invalid watchlist delta report")
    changes = payload.get("changes")
    if not isinstance(changes, list) or len(changes) > 5_000:
        raise ValueError("Watchlist changes must be a bounded list")
    return {
        **_new_delta(now),
        "changes": deepcopy(changes),
        "change_count": len(changes),
    }


def _validated_link_row(row: Mapping[str, Any]) -> tuple[str, str]:
    organisation_number = _compact(row.get("organisation_number"))
    sale_url = _safe_norwegian_sale_url(row.get("sale_url"))
    official_url = _compact(row.get("official_bankruptcy_url"))
    if (
        row.get("classification") != "OFFICIAL_BANKRUPTCY_LINKED_ASSET_SALE"
        or row.get("event_kind") != "KONKURS"
        or len(organisation_number) != 9
        or not organisation_number.isascii()
        or not organisation_number.isdigit()
        or official_url
        != "https://data.brreg.no/enhetsregisteret/api/enheter/" + organisation_number
        or row.get("bankruptcy_language_verified_on_page") is not True
        or row.get("sale_language_verified_on_page") is not True
        or row.get("bankruptcy_estate_sale_relationship_verified_on_page") is not True
        or row.get("liquidation_only") is not False
        or row.get("surplus_only") is not False
        or row.get("dealer_only") is not False
        or row.get("ended_marker_found") is not False
    ):
        raise ValueError("Unverified or non-bankruptcy link reached the watchlist")
    return organisation_number, sale_url


def finalize_watchlist(
    watchlist_payload: Mapping[str, Any],
    due_events_report: Mapping[str, Any],
    link_report: Mapping[str, Any],
    delta_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
    recheck_days: int = DEFAULT_RECHECK_DAYS,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply one bounded link-chase result and expose only newly proven links."""
    stamp = _utc(now)
    if recheck_days != DEFAULT_RECHECK_DAYS:
        raise ValueError("V1 recheck cadence must remain exactly 3 days")
    watchlist = validate_watchlist(watchlist_payload)
    selected_events = _validate_events_report(due_events_report)
    selected_orgs = {event["organisation_number"] for event in selected_events}
    if (
        link_report.get("schema_version") != LINK_SCHEMA
        or link_report.get("scope") != LINK_SCOPE
    ):
        raise ValueError("Norway bankruptcy-link hunt report is required")
    links_raw = link_report.get("verified_bankruptcy_sale_links")
    rejected_raw = link_report.get("rejected_hits")
    if not isinstance(links_raw, list) or not isinstance(rejected_raw, list):
        raise ValueError("Invalid bankruptcy-link evidence lists")
    if int(link_report.get("verified_bankruptcy_sale_link_count") or 0) != len(
        links_raw
    ):
        raise ValueError("Verified bankruptcy-link count mismatch")
    delta = _validate_delta(delta_payload, stamp)
    by_org = {case["organisation_number"]: case for case in watchlist["cases"]}
    if not selected_orgs.issubset(by_org):
        raise ValueError("Due event is missing from the restored watchlist")

    coverage = _compact(link_report.get("coverage")) or "UNKNOWN"
    retry_days = (
        1
        if coverage
        in {
            "SEARCH_PROVIDERS_UNAVAILABLE",
            "SEARCH_NOT_RUN",
            "SEARCH_PROVIDERS_FAILED",
            "DIRECT_WATCHLIST_RECHECK_FAILED",
        }
        else recheck_days
    )
    total_paid_raw = link_report.get("paid_provider_requests", 0)
    if (
        not isinstance(total_paid_raw, int)
        or isinstance(total_paid_raw, bool)
        or total_paid_raw < 0
    ):
        raise ValueError("paid_provider_requests must be a non-negative integer")
    total_paid = total_paid_raw
    paid_by_org: dict[str, int] = {org: 0 for org in selected_orgs}
    raw_per_org = link_report.get("provider_request_counts_by_organisation") or {}
    if not isinstance(raw_per_org, Mapping):
        raise ValueError("provider_request_counts_by_organisation must be an object")
    counted_paid = 0
    for raw_org, raw_counts in raw_per_org.items():
        org = _compact(raw_org)
        if org not in selected_orgs or not isinstance(raw_counts, Mapping):
            raise ValueError("Paid request accounting references a non-selected case")
        case_total = 0
        for provider, count in raw_counts.items():
            if (
                not _compact(provider)
                or not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
                or count > 2
            ):
                raise ValueError("Invalid per-provider paid request count")
            case_total += count
        if case_total > 2:
            raise ValueError("A case exceeded the Exa plus Brave request bound")
        paid_by_org[org] = case_total
        counted_paid += case_total
    if counted_paid != total_paid:
        raise ValueError("Per-case paid request accounting does not match total")
    for provider_error in link_report.get("provider_errors") or []:
        if not isinstance(provider_error, Mapping):
            raise ValueError("Invalid provider error row")
        org = _compact(provider_error.get("organisation_number"))
        if org and org not in selected_orgs:
            raise ValueError("Provider error belongs to a non-selected bankruptcy")
    previous_status = {org: by_org[org]["status"] for org in selected_orgs}
    for org in selected_orgs:
        case = by_org[org]
        case["last_checked_at"] = _iso(stamp)
        case["next_check_at"] = _iso(stamp + timedelta(days=retry_days))
        case["check_count"] += 1
        case["paid_search_requests"] += paid_by_org[org]
        case["last_check_outcome"] = coverage

    ended_by_org: dict[str, set[str]] = {}
    for raw_rejection in rejected_raw:
        if not isinstance(raw_rejection, Mapping):
            raise ValueError("Invalid rejected bankruptcy-link row")
        org = _compact(raw_rejection.get("organisation_number"))
        if org not in selected_orgs:
            raise ValueError("Rejected link belongs to a non-selected bankruptcy")
        if raw_rejection.get("reason") == "SALE_PAGE_EXPLICITLY_ENDED":
            ended_by_org.setdefault(org, set()).add(
                _safe_norwegian_sale_url(raw_rejection.get("url"))
            )
    for org, ended_urls in ended_by_org.items():
        case = by_org[org]
        for link in case["verified_sale_links"]:
            if link["sale_url"] not in ended_urls or link["status"] != ACTIVE_LINK:
                continue
            link["status"] = ENDED_LINK
            link["ended_at"] = _iso(stamp)
            _append_change(
                delta,
                change_type="VERIFIED_SALE_LINK_ENDED",
                case=case,
                now=stamp,
                sale_url=link["sale_url"],
            )

    new_links: list[dict[str, Any]] = []
    for raw_link in links_raw:
        if not isinstance(raw_link, Mapping):
            raise ValueError("Invalid verified bankruptcy-link row")
        org, sale_url = _validated_link_row(raw_link)
        if org not in selected_orgs:
            raise ValueError("Verified link belongs to a non-selected bankruptcy")
        case = by_org[org]
        existing = next(
            (
                link
                for link in case["verified_sale_links"]
                if link["sale_url"] == sale_url
            ),
            None,
        )
        if existing is None:
            if len(case["verified_sale_links"]) >= MAX_LINKS_PER_CASE:
                raise ValueError("Verified sale-link limit reached for watchlist case")
            case["verified_sale_links"].append(
                {
                    "sale_url": sale_url,
                    "status": ACTIVE_LINK,
                    "sale_page_title": _compact(raw_link.get("sale_page_title"))[:500],
                    "identity_match_method": _compact(
                        raw_link.get("identity_match_method")
                    )[:100],
                    "first_verified_at": _iso(stamp),
                    "last_verified_at": _iso(stamp),
                    "ended_at": None,
                }
            )
            new_links.append(dict(raw_link))
            _append_change(
                delta,
                change_type="NEW_VERIFIED_BANKRUPTCY_SALE_LINK",
                case=case,
                now=stamp,
                sale_url=sale_url,
            )
        else:
            existing["status"] = ACTIVE_LINK
            existing["last_verified_at"] = _iso(stamp)
            existing["ended_at"] = None
            existing["sale_page_title"] = _compact(raw_link.get("sale_page_title"))[
                :500
            ]
            existing["identity_match_method"] = _compact(
                raw_link.get("identity_match_method")
            )[:100]

    for org in selected_orgs:
        case = by_org[org]
        has_active = any(
            link["status"] == ACTIVE_LINK for link in case["verified_sale_links"]
        )
        case["status"] = SALE_VERIFIED if has_active else WAITING
        if case["status"] != previous_status[org]:
            _append_change(
                delta,
                change_type="CASE_STATUS_CHANGED",
                case=case,
                now=stamp,
                previous_status=previous_status[org],
                current_status=case["status"],
            )

    watchlist["generated_at"] = _iso(stamp)
    watchlist["cases"] = sorted(
        by_org.values(), key=lambda case: case["organisation_number"]
    )
    watchlist["active_case_count"] = len(watchlist["cases"])
    watchlist["waiting_case_count"] = sum(
        case["status"] == WAITING for case in watchlist["cases"]
    )
    watchlist["verified_sale_case_count"] = sum(
        case["status"] == SALE_VERIFIED for case in watchlist["cases"]
    )
    delta["generated_at"] = _iso(stamp)
    delta["change_count"] = len(delta["changes"])
    new_link_report = deepcopy(dict(link_report))
    new_link_report["captured_at"] = _iso(stamp)
    new_link_report["verified_bankruptcy_sale_links"] = new_links
    new_link_report["verified_bankruptcy_sale_link_count"] = len(new_links)
    new_link_report["watchlist_new_link_filter_applied"] = True
    if not new_links:
        new_link_report["coverage"] = "NO_NEW_VERIFIED_BANKRUPTCY_SALE_LINKS"
    return validate_watchlist(watchlist), delta, new_link_report


def render_arabic(
    watchlist: Mapping[str, Any],
    delta: Mapping[str, Any],
    due_report: Mapping[str, Any] | None = None,
) -> str:
    cases = watchlist.get("cases") or []
    changes = delta.get("changes") or []
    waiting_count = sum(case.get("status") == WAITING for case in cases)
    verified_count = sum(case.get("status") == SALE_VERIFIED for case in cases)
    lines = [
        "متابعة الإفلاسات — النرويج فقط",
        (
            f"حالات نشطة: {len(cases)} | بانتظار رابط بيع: "
            f"{waiting_count} | لديها رابط بيع مثبت: {verified_count}"
        ),
    ]
    if due_report is not None:
        lines.append(
            "مستحقة للفحص: "
            f"{due_report.get('watchlist_due_case_count', 0)} | "
            f"مختارة اليوم: {due_report.get('watchlist_selected_case_count', 0)} | "
            f"مؤجلة بسبب الحد: {due_report.get('watchlist_deferred_due_case_count', 0)}"
        )
    lines.append(f"تغييرات هذا التشغيل فقط: {len(changes)}")
    if not changes:
        lines.append("لا يوجد تغيير جديد؛ الحالات القديمة بقيت محفوظة ولم تُحذف.")
    labels = {
        "OFFICIAL_BANKRUPTCY_ADDED": "إفلاس رسمي جديد أُضيف للمتابعة",
        "OFFICIAL_BANKRUPTCY_DATA_CHANGED": "تغيّرت بيانات الإفلاس الرسمية",
        "NEW_VERIFIED_BANKRUPTCY_SALE_LINK": "ظهر رابط بيع جديد ومثبت",
        "VERIFIED_SALE_LINK_ENDED": "انتهى رابط بيع كان مثبتًا",
        "CASE_STATUS_CHANGED": "تغيّرت حالة المتابعة",
        "CASE_EXPIRED_AFTER_60_DAYS": "انتهت متابعة الحالة بعد 60 يومًا",
    }
    for change in changes:
        change_label = labels.get(
            change.get("change_type"), change.get("change_type")
        )
        lines.extend(
            [
                "",
                f"- {change_label}: "
                f"{change.get('company_name')} ({change.get('organisation_number')})",
            ]
        )
        if change.get("sale_url"):
            lines.append(f"  الرابط: {change['sale_url']}")
    lines.extend(
        [
            "",
            "لا تاجر، لا تصفية عادية، ولا اتصال أو مزايدة أو شراء أو دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_json(path: Path, *, required: bool = True) -> dict[str, Any] | None:
    if not path.is_file():
        if required:
            raise FileNotFoundError(path)
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _prepare_command(args: argparse.Namespace) -> int:
    events = _load_json(args.events)
    previous = _load_json(args.watchlist, required=False)
    assert events is not None
    watchlist, due_report, delta = prepare_watchlist(
        events,
        previous,
        retention_days=args.retention_days,
        recheck_days=args.recheck_days,
        max_due_cases=args.max_due_cases,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "bankruptcy-watchlist.json", watchlist)
    _write_json(args.output_dir / "bankruptcy-watchlist-due-events.json", due_report)
    _write_json(args.output_dir / "bankruptcy-watchlist-delta.json", delta)
    (args.output_dir / "bankruptcy-watchlist-delta-ar.txt").write_text(
        render_arabic(watchlist, delta, due_report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "active_cases": len(watchlist["cases"]),
                "due_cases": due_report["watchlist_due_case_count"],
                "selected_cases": due_report["watchlist_selected_case_count"],
                "changes": delta["change_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _finalize_command(args: argparse.Namespace) -> int:
    watchlist = _load_json(args.watchlist)
    due_events = _load_json(args.due_events)
    links = _load_json(args.link_report)
    delta = _load_json(args.delta)
    assert watchlist is not None and due_events is not None
    assert links is not None and delta is not None
    finalized, final_delta, new_links = finalize_watchlist(
        watchlist,
        due_events,
        links,
        delta,
        recheck_days=args.recheck_days,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "bankruptcy-watchlist.json", finalized)
    _write_json(args.output_dir / "bankruptcy-watchlist-delta.json", final_delta)
    _write_json(args.output_dir / "bankruptcy-new-link-report.json", new_links)
    (args.output_dir / "bankruptcy-watchlist-delta-ar.txt").write_text(
        render_arabic(finalized, final_delta, due_events), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "active_cases": len(finalized["cases"]),
                "changes": final_delta["change_count"],
                "new_verified_sale_links": new_links[
                    "verified_bankruptcy_sale_link_count"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--events", type=Path, required=True)
    prepare.add_argument("--watchlist", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    prepare.add_argument("--recheck-days", type=int, default=DEFAULT_RECHECK_DAYS)
    prepare.add_argument("--max-due-cases", type=int, default=DEFAULT_MAX_DUE_CASES)
    prepare.set_defaults(handler=_prepare_command)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--watchlist", type=Path, required=True)
    finalize.add_argument("--due-events", type=Path, required=True)
    finalize.add_argument("--link-report", type=Path, required=True)
    finalize.add_argument("--delta", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--recheck-days", type=int, default=DEFAULT_RECHECK_DAYS)
    finalize.set_defaults(handler=_finalize_command)
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
