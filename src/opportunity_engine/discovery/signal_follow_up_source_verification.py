"""Route follow-up web-search leads into existing exact public item verifiers.

This bridge is deliberately conservative: it only fetches URLs that a known
source-specific verifier can prove are exact public item pages. Generic search
hits, catalog pages, seller homepages and unsupported domains remain unverified.
No source-page result can contact a seller, bid, reserve, purchase or pay.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse, urlunparse

from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    fetch_auksjonen_item_page,
    parse_auksjonen_item_page,
)
from opportunity_engine.discovery.germany_venta import UNKNOWN, VentaPublicPage, canonicalize_venta_url
from opportunity_engine.discovery.germany_venta_item_verification import (
    fetch_venta_item_page,
    parse_venta_item_page,
)
from opportunity_engine.discovery.signal_follow_up_engine import (
    DECISION_OWNER,
    OUTPUT_FILENAME as FOLLOW_UP_FILENAME,
    _canonical_url,
    _normalise,
    _significant_tokens,
)

SCHEMA_VERSION = "signal-follow-up-source-verification-1.0"
OUTPUT_FILENAME = "signal-follow-up-source-verification.json"
DEFAULT_MAX_VERIFICATION_PAGES = 4
MAX_VERIFICATION_PAGES = 8

AuksjonenFetcher = Callable[[str], tuple[str, str, int, str]]
VentaFetcher = Callable[[str], VentaPublicPage]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _auksjonen_exact_item_url(url: object) -> str | None:
    canonical = _canonical_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() != "ny.auksjonen.no":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3 or parts[0].casefold() != "auksjon" or not parts[-1].isdigit():
        return None
    return urlunparse(("https", "ny.auksjonen.no", parsed.path, "", "", ""))


def _route(url: object) -> tuple[str, str] | None:
    raw = _compact(url)
    if not raw:
        return None
    venta = canonicalize_venta_url(raw)
    if venta is not None and venta.kind == "ITEM_DETAIL" and venta.object_id:
        return "VENTA_EXACT_ITEM", venta.canonical_url
    auksjonen = _auksjonen_exact_item_url(raw)
    if auksjonen:
        return "AUKSJONEN_EXACT_ITEM", auksjonen
    return None


def _lead_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_case in report.get("cases") or []:
        if not isinstance(raw_case, Mapping):
            continue
        case = dict(raw_case)
        for raw_lead in case.get("leads") or []:
            if not isinstance(raw_lead, Mapping):
                continue
            lead = dict(raw_lead)
            if _compact(lead.get("verification_status")) != "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT":
                continue
            rows.append(
                {
                    "case_id": case.get("case_id"),
                    "case_title": case.get("case_title"),
                    "country": case.get("country"),
                    "target_label": case.get("target_label") or case.get("case_title"),
                    "follow_up_stage": case.get("follow_up_stage"),
                    "lead": lead,
                }
            )
    rows.sort(
        key=lambda row: (
            -int(row["lead"].get("follow_up_relevance_score") or 0),
            int(row["lead"].get("search_rank") or 999),
            _compact(row["lead"].get("source_url")),
        )
    )
    return rows


def _page_text(details: Mapping[str, Any]) -> str:
    return " ".join(
        _compact(details.get(key))
        for key in ("title", "description", "text", "bounded_context")
        if _compact(details.get(key))
    )


def _entity_match(target_label: object, details: Mapping[str, Any]) -> tuple[bool, list[str], list[str]]:
    tokens = _significant_tokens(target_label)
    normalized = _normalise(_page_text(details))
    matched = [token for token in tokens if token in normalized]
    return bool(tokens) and len(matched) == len(tokens), tokens, matched


def _commercial_fact_count(details: Mapping[str, Any]) -> int:
    keys = (
        "quantity",
        "weight_kg",
        "length_cm",
        "width_cm",
        "height_cm",
        "pallet_count",
        "source_start_or_minimum_price_eur",
        "source_displayed_bid_eur",
        "source_start_or_minimum_price_nok",
        "source_displayed_bid_nok",
        "source_buy_now_price_nok",
        "buyer_premium_percent",
        "vat_percent",
        "source_postal_code",
        "source_city",
        "location",
    )
    return sum(details.get(key) not in (None, "", [], {}) for key in keys)


def _base_row(context: Mapping[str, Any], *, source_kind: str | None, canonical_url: str | None) -> dict[str, Any]:
    lead = context["lead"]
    source_url = _compact(lead.get("source_url"))
    stable = _compact(lead.get("lead_id")) or source_url
    return {
        "verification_id": "follow-up-source-verification:"
        + sha256(f"{context.get('case_id')}|{stable}".encode("utf-8")).hexdigest()[:24],
        "lead_id": lead.get("lead_id"),
        "case_id": context.get("case_id"),
        "case_title": context.get("case_title"),
        "country": context.get("country"),
        "target_label": context.get("target_label"),
        "follow_up_stage": context.get("follow_up_stage"),
        "lead_kind": lead.get("lead_kind"),
        "search_result_title": lead.get("title"),
        "source_url": source_url,
        "canonical_source_url": canonical_url,
        "source_kind": source_kind,
        "search_lead_verification_status": "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT",
        "source_page_verification_status": "NOT_ATTEMPTED",
        "source_page_verified": False,
        "entity_link_verified": False,
        "commercial_facts_confirmed": False,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _normalized_facts(details: Mapping[str, Any]) -> dict[str, Any]:
    currency = details.get("currency")
    start_price = details.get("source_start_or_minimum_price_eur")
    bid = details.get("source_displayed_bid_eur")
    buy_now = None
    if start_price is None:
        start_price = details.get("source_start_or_minimum_price_nok")
    if bid is None:
        bid = details.get("source_displayed_bid_nok")
    if buy_now is None:
        buy_now = details.get("source_buy_now_price_nok")
    return {
        "title": details.get("title"),
        "quantity": details.get("quantity"),
        "condition": details.get("condition"),
        "weight_kg": details.get("weight_kg"),
        "length_cm": details.get("length_cm"),
        "width_cm": details.get("width_cm"),
        "height_cm": details.get("height_cm"),
        "pallet_count": details.get("pallet_count"),
        "location": details.get("location"),
        "source_postal_code": details.get("source_postal_code"),
        "source_city": details.get("source_city"),
        "source_start_or_minimum_price": start_price,
        "source_displayed_bid": bid,
        "source_buy_now_price": buy_now,
        "currency": currency,
        "buyer_premium_percent": details.get("buyer_premium_percent"),
        "vat_percent": details.get("vat_percent"),
        "response_sha256": details.get("response_sha256") or details.get("page_sha256"),
        "shipping_details_source": details.get("shipping_details_source"),
    }


def _verify_venta(
    context: Mapping[str, Any],
    canonical_url: str,
    *,
    fetcher: VentaFetcher,
) -> dict[str, Any]:
    row = _base_row(context, source_kind="VENTA_EXACT_ITEM", canonical_url=canonical_url)
    lead = context["lead"]
    page = fetcher(canonical_url)
    details = parse_venta_item_page(
        page,
        fallback_title=_compact(lead.get("title")),
        quantity=None,
        opportunity_identity=_compact(lead.get("lead_id")) or row["verification_id"],
        listing_status=UNKNOWN,
    )
    entity_match, target_tokens, matched_tokens = _entity_match(context.get("target_label"), details)
    facts = _normalized_facts(details)
    fact_count = _commercial_fact_count(details)
    row.update(facts)
    row.update(
        {
            "source_page_verification_status": (
                "SOURCE_PAGE_VERIFIED_ENTITY_MATCH"
                if entity_match
                else "SOURCE_PAGE_VERIFIED_ENTITY_NOT_CONFIRMED"
            ),
            "source_page_verified": True,
            "entity_link_verified": entity_match,
            "target_tokens": target_tokens,
            "source_page_matched_target_tokens": matched_tokens,
            "source_fact_count": fact_count,
            "commercial_facts_confirmed": fact_count > 0,
            "clothing_inventory_evidence": details.get("clothing_inventory_evidence"),
            "sale_evidence": details.get("sale_evidence"),
            "final_sale_price_trusted": False,
            "verifier": "germany_venta_item_verification.parse_venta_item_page",
        }
    )
    return row


def _verify_auksjonen(
    context: Mapping[str, Any],
    canonical_url: str,
    *,
    fetcher: AuksjonenFetcher,
) -> dict[str, Any]:
    row = _base_row(context, source_kind="AUKSJONEN_EXACT_ITEM", canonical_url=canonical_url)
    lead = context["lead"]
    html, final_url, response_bytes, page_sha256 = fetcher(canonical_url)
    details = parse_auksjonen_item_page(html, fallback_title=_compact(lead.get("title")))
    details = {
        **details,
        "page_sha256": page_sha256,
        "shipping_details_source": "Auksjonen.no exact public item page",
    }
    entity_match, target_tokens, matched_tokens = _entity_match(context.get("target_label"), details)
    facts = _normalized_facts(details)
    fact_count = _commercial_fact_count(details)
    row.update(facts)
    row.update(
        {
            "final_url": final_url,
            "response_bytes": response_bytes,
            "source_page_verification_status": (
                "SOURCE_PAGE_VERIFIED_ENTITY_MATCH"
                if entity_match
                else "SOURCE_PAGE_VERIFIED_ENTITY_NOT_CONFIRMED"
            ),
            "source_page_verified": True,
            "entity_link_verified": entity_match,
            "target_tokens": target_tokens,
            "source_page_matched_target_tokens": matched_tokens,
            "source_fact_count": fact_count,
            "commercial_facts_confirmed": fact_count > 0,
            "final_sale_price_trusted": False,
            "verifier": "auksjonen_exact_item_verification.parse_auksjonen_item_page",
        }
    )
    return row


def run_signal_follow_up_source_verification(
    follow_up_report: Mapping[str, Any],
    *,
    observed_at: datetime | None = None,
    max_verification_pages: int = DEFAULT_MAX_VERIFICATION_PAGES,
    auksjonen_fetcher: AuksjonenFetcher | None = None,
    venta_fetcher: VentaFetcher | None = None,
) -> dict[str, Any]:
    """Verify supported exact item URLs while leaving every other lead untouched."""
    bounded = max(0, min(MAX_VERIFICATION_PAGES, int(max_verification_pages)))
    auksjonen = auksjonen_fetcher or fetch_auksjonen_item_page
    venta = venta_fetcher or fetch_venta_item_page
    now = _utc(observed_at)
    input_rows = _lead_rows(follow_up_report)

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    requests = verified = failed = unsupported = budget_skipped = 0

    for context in input_rows:
        lead = context["lead"]
        source_url = _compact(lead.get("source_url"))
        route = _route(source_url)
        dedupe_key = (route[1] if route else _canonical_url(source_url)) or source_url
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if route is None:
            unsupported += 1
            row = _base_row(context, source_kind=None, canonical_url=_canonical_url(source_url))
            row.update(
                {
                    "source_page_verification_status": "UNSUPPORTED_SOURCE_OR_NON_EXACT_ITEM_URL",
                    "reason": "requires a source-specific exact-item verifier; URL was not guessed or expanded",
                }
            )
            results.append(row)
            continue

        source_kind, canonical_url = route
        if requests >= bounded:
            budget_skipped += 1
            row = _base_row(context, source_kind=source_kind, canonical_url=canonical_url)
            row.update(
                {
                    "source_page_verification_status": "SKIPPED_BOUNDED_VERIFICATION_BUDGET",
                    "reason": f"bounded page budget exhausted at {bounded}",
                }
            )
            results.append(row)
            continue

        requests += 1
        try:
            if source_kind == "VENTA_EXACT_ITEM":
                row = _verify_venta(context, canonical_url, fetcher=venta)
            else:
                row = _verify_auksjonen(context, canonical_url, fetcher=auksjonen)
            verified += 1
        except Exception as exc:
            failed += 1
            row = _base_row(context, source_kind=source_kind, canonical_url=canonical_url)
            row.update(
                {
                    "source_page_verification_status": "SOURCE_PAGE_VERIFICATION_FAILED",
                    "error_type": type(exc).__name__,
                    "error": _compact(exc)[:500],
                    "reason": "source failure is retained as evidence; no bypass or guessed facts",
                }
            )
        results.append(row)

    if not input_rows:
        status = "VALID_ZERO_NO_FOLLOW_UP_LEADS"
    elif requests == 0:
        status = "VALID_ZERO_NO_SUPPORTED_EXACT_ITEM_URLS"
    elif failed and verified:
        status = "PARTIAL_SUCCESS"
    elif failed:
        status = "FAILED"
    else:
        status = "SUCCESS"

    with_price = sum(
        row.get("source_start_or_minimum_price") is not None
        or row.get("source_displayed_bid") is not None
        or row.get("source_buy_now_price") is not None
        for row in results
    )
    with_weight = sum(row.get("weight_kg") is not None for row in results)
    with_quantity = sum(row.get("quantity") is not None for row in results)
    with_pallets = sum(row.get("pallet_count") is not None for row in results)
    with_location = sum(bool(row.get("source_postal_code") or row.get("source_city") or row.get("location")) for row in results)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "status": status,
        "purpose": "TURN_SUPPORTED_FOLLOW_UP_SEARCH_LEADS_INTO_SOURCE_BACKED_EXACT_ITEM_FACTS",
        "candidate_lead_count": len(input_rows),
        "deduplicated_lead_count": len(results),
        "supported_exact_item_lead_count": sum(row.get("source_kind") is not None for row in results),
        "verification_request_count": requests,
        "source_page_verified_count": verified,
        "source_page_failed_count": failed,
        "unsupported_or_non_exact_count": unsupported,
        "budget_skipped_count": budget_skipped,
        "verified_with_price_count": with_price,
        "verified_with_weight_count": with_weight,
        "verified_with_quantity_count": with_quantity,
        "verified_with_pallet_count": with_pallets,
        "verified_with_location_count": with_location,
        "verifications": results,
        "supported_verifiers": ["VENTA_EXACT_ITEM", "AUKSJONEN_EXACT_ITEM"],
        "unsupported_urls_are_never_guessed": True,
        "search_hit_is_not_commercial_proof": True,
        "source_page_verification_does_not_prove_entity_link_unless_target_matches_page": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _attach_to_domain_brief(directory: Path, report: Mapping[str, Any]) -> None:
    brief_path = directory / "domain-market-intelligence-brief.json"
    brief = _read_json(brief_path)
    if brief is not None:
        brief["signal_follow_up_source_verification"] = {
            key: report.get(key)
            for key in (
                "schema_version",
                "status",
                "candidate_lead_count",
                "supported_exact_item_lead_count",
                "verification_request_count",
                "source_page_verified_count",
                "source_page_failed_count",
                "verified_with_price_count",
                "verified_with_weight_count",
                "verified_with_quantity_count",
                "verified_with_pallet_count",
                "verified_with_location_count",
                "promotion_to_opportunity_allowed",
                "decision_owner",
            )
        }
        _write_json(brief_path, brief)

    text_path = directory / "domain-market-intelligence-brief.txt"
    if not text_path.exists():
        return
    marker = "SIGNAL FOLLOW-UP SOURCE VERIFICATION V1"
    text = text_path.read_text(encoding="utf-8")
    if marker in text:
        return
    with text_path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\nSIGNAL FOLLOW-UP SOURCE VERIFICATION V1\n"
            f"status: {report.get('status')}\n"
            f"candidate_leads: {report.get('candidate_lead_count', 0)}\n"
            f"exact_item_pages_requested: {report.get('verification_request_count', 0)}\n"
            f"source_pages_verified: {report.get('source_page_verified_count', 0)}\n"
            f"verified_with_price: {report.get('verified_with_price_count', 0)}\n"
            f"verified_with_weight: {report.get('verified_with_weight_count', 0)}\n"
            f"verified_with_quantity: {report.get('verified_with_quantity_count', 0)}\n"
            f"verified_with_pallets: {report.get('verified_with_pallet_count', 0)}\n"
            "promotion_to_opportunity_allowed: false\n"
            "decision_owner: HUMAN_OPERATOR\n"
        )


def write_signal_follow_up_source_verification(
    output_dir: str | Path,
    *,
    follow_up_report: Mapping[str, Any] | None = None,
    observed_at: datetime | None = None,
    max_verification_pages: int = DEFAULT_MAX_VERIFICATION_PAGES,
    auksjonen_fetcher: AuksjonenFetcher | None = None,
    venta_fetcher: VentaFetcher | None = None,
) -> dict[str, Any]:
    directory = Path(output_dir)
    report_input = dict(follow_up_report) if isinstance(follow_up_report, Mapping) else (_read_json(directory / FOLLOW_UP_FILENAME) or {"cases": []})
    report = run_signal_follow_up_source_verification(
        report_input,
        observed_at=observed_at,
        max_verification_pages=max_verification_pages,
        auksjonen_fetcher=auksjonen_fetcher,
        venta_fetcher=venta_fetcher,
    )
    _write_json(directory / OUTPUT_FILENAME, report)
    _attach_to_domain_brief(directory, report)
    return report
