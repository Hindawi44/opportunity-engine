"""Restore traceable early commercial events to Discovery Top 5.

This gate runs after raw Clothing Inventory discovery. It keeps source-channel and
other generic-page protections intact while separating Discovery visibility from
Analysis eligibility:

* a specific active sale listing may be eligible for Analysis;
* a traceable bankruptcy, closure, or liquidation event may enter Discovery Top 5;
* an early event lead never becomes Analysis eligible until a sale is confirmed;
* a verified ended item listing leaves the current-opportunity path and is retained
  only as Historical Market Evidence when bounded item content proves the matching
  bulk clothing inventory.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

CONFIRMED_SALE = "CONFIRMED_SALE"
STRONG_LEAD_REQUIRES_VERIFICATION = "STRONG_LEAD_REQUIRES_VERIFICATION"
HISTORICAL_MARKET_EVIDENCE = "HISTORICAL_MARKET_EVIDENCE"
HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW = (
    "HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW"
)
REJECTED_NOISE = "REJECTED_NOISE"

ACTIVE = "ACTIVE"
ENDED = "ENDED"
UNKNOWN = "UNKNOWN"

ITEM_LISTING = "ITEM_LISTING"
EVENT_LEAD = "EVENT_LEAD"
CATEGORY_INDEX = "CATEGORY_INDEX"
SOURCE_CHANNEL = "SOURCE_CHANNEL"
ORDINARY_STORE = "ORDINARY_STORE"
ARTICLE_OR_INFO = "ARTICLE_OR_INFO"
UNRESOLVED_SOURCE = "UNRESOLVED_SOURCE"

_EARLY_EVENT_TERMS: dict[str, tuple[str, ...]] = {
    "COMPANY_BANKRUPTCY": ("konkursbo", "konkurs", "tvangsavvikling"),
    "STORE_CLOSING": ("opphør", "avvikling", "butikk stenger", "butikken stenger"),
    "BRANCH_CLOSURE": ("filial legges ned", "filial stenger", "avdeling stenger"),
    "INVENTORY_LIQUIDATION": ("lager ryddes", "lageravvikling", "likvidasjon"),
}
_EVENT_PRIORITY = {
    "COMPANY_BANKRUPTCY": 25,
    "BRANCH_CLOSURE": 24,
    "STORE_CLOSING": 23,
    "INVENTORY_LIQUIDATION": 22,
}
_APPAREL_TERMS = (
    "klær", "klesbutikk", "kleslager", "sko", "arbeidstøy", "sportsklær",
    "tekstil", "mote", "motebutikk", "bekledning", "klesparti",
)
_BUSINESS_TERMS = (
    "butikk", "klesbutikk", "selskap", "bedrift", "grossist", "importør",
    "forhandler", "filial", "konkursbo",
)
_GENERIC_TITLES = (
    "forside", "om oss", "torget", "vareparti-og-konkursbo", "alle produkter",
    "auksjon - konkursbo", "konkursbo, partivare, restlager",
)
_ENTITY_STOPWORDS = {
    "as", "asa", "butikk", "butikken", "klesbutikk", "klær", "sko", "varelager",
    "konkurs", "konkursbo", "opphør", "avvikling", "selges", "salg", "til", "og",
    "i", "på", "for", "fra", "med", "hele", "lageret", "norge", "stenger",
    "legges", "ned", "restlager", "vareparti", "klesparti", "stort", "samlet",
}
_TRACKING_PARAMETERS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source",
    "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}
_NORWAY_LOCATION_TERMS = (
    "trøndelag", "oslo", "bergen", "trondheim", "stavanger", "tromsø", "namsos",
    "kolvereid", "steinkjer", "mo i rana", "kristiansand", "drammen", "støren",
    "ytre enebakk", "strømmen", "tolvsrød", "stathelle", "lierstranda",
)
_EXCLUDED_VERIFIED_ROLES = {CATEGORY_INDEX, SOURCE_CHANNEL, ORDINARY_STORE}
_GENERIC_ROLES = {
    CATEGORY_INDEX, SOURCE_CHANNEL, ORDINARY_STORE, ARTICLE_OR_INFO, UNRESOLVED_SOURCE,
}
_HISTORICAL_APPAREL_TERMS = (
    "kläder", "klädesplagg", "arbetskläder", "yrkeskläder", "skyddskläder",
    "varselkläder", "arbetsbyxor", "byxor", "jackor", "skinnbyxor",
    "regnoverall", "goretexjacka", "arbetsskor", "skyddsskor", "stövlar",
    "skor", "plagg", "workwear", "clothing", "trousers", "pants", "jackets",
    "boots", "shoes", "klær", "arbeidstøy", "bukser", "jakker",
)
_HISTORICAL_BULK_TERMS = (
    "parti", "restparti", "varulager", "vareparti", "totalt", "sammanlagt",
    "stycken", "plagg", "par", "pall", "pallar", "kartong", "kartonger",
    "lot", "pairs", "pieces", "units",
)
_HISTORICAL_QUANTITY_PATTERN = re.compile(
    r"\b\d{1,7}\s*(?:st|stycken|plagg|artiklar|enheter|delar|byxor|par|pairs|pieces|units)\b",
    re.I,
)


def _normalized_text(*values: object) -> str:
    return " ".join(" ".join(str(value).lower().split()) for value in values if value)


def _normalize_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMETERS
    ))
    return urlunparse(("https", host, path, "", query, ""))


def _scenario_from_text(text: str) -> str | None:
    matches: list[tuple[int, str]] = []
    for scenario, terms in _EARLY_EVENT_TERMS.items():
        if any(term in text for term in terms):
            matches.append((_EVENT_PRIORITY[scenario], scenario))
    return max(matches)[1] if matches else None


def _specific_title_tokens(title: str) -> set[str]:
    normalized = _normalized_text(title)
    if not normalized or any(
        normalized == generic or normalized.startswith(f"{generic} |")
        for generic in _GENERIC_TITLES
    ):
        return set()
    tokens = re.findall(r"[a-zæøå0-9]{2,}", normalized)
    return {token for token in tokens if token not in _ENTITY_STOPWORDS and not token.isdigit()}


def _verification_context(candidate: Mapping[str, Any]) -> str:
    parts: list[object] = [candidate.get("title")]
    parts.extend(candidate.get("evidence_signals") or [])
    for item in candidate.get("verification") or []:
        if not isinstance(item, Mapping):
            continue
        parts.extend((item.get("title"), item.get("text"), item.get("bounded_context")))
    return _normalized_text(*parts)


def _bounded_verification_context(item: Mapping[str, Any]) -> str:
    """Use only bounded page evidence; never use title or search-snippet evidence."""
    return _normalized_text(item.get("bounded_context") or item.get("text"))


def _verification_content_matches_historical_inventory(
    item: Mapping[str, Any],
) -> bool:
    explicit = item.get("verification_content_match")
    if isinstance(explicit, bool):
        return explicit
    context = _bounded_verification_context(item)
    if not context:
        return False
    apparel = any(term in context for term in _HISTORICAL_APPAREL_TERMS)
    bulk = any(term in context for term in _HISTORICAL_BULK_TERMS)
    quantified = _HISTORICAL_QUANTITY_PATTERN.search(context) is not None
    return apparel and (bulk or quantified)


def _verified_ended_item_verifications(
    candidate: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    return [
        item
        for item in candidate.get("verification") or []
        if isinstance(item, Mapping)
        and item.get("verified") is True
        and item.get("page_role") == ITEM_LISTING
        and item.get("listing_status") == ENDED
    ]


def _has_excluded_verified_role(candidate: Mapping[str, Any]) -> bool:
    for item in candidate.get("verification") or []:
        if isinstance(item, Mapping) and item.get("verified") is True:
            if item.get("page_role") in _EXCLUDED_VERIFIED_ROLES:
                return True
    return False


def _historical_identity_gate(candidate: Mapping[str, Any]) -> bool:
    return bool(
        candidate.get("listing_status") == ENDED
        and candidate.get("page_role") == ITEM_LISTING
        and candidate.get("identity_stable") is True
        and candidate.get("source_urls")
    )


def _verified_historical_item_listing(candidate: Mapping[str, Any]) -> bool:
    if not _historical_identity_gate(candidate):
        return False
    return any(
        _verification_content_matches_historical_inventory(item)
        for item in _verified_ended_item_verifications(candidate)
    )


def _historical_item_requires_manual_review(candidate: Mapping[str, Any]) -> bool:
    if not _historical_identity_gate(candidate):
        return False
    verifications = _verified_ended_item_verifications(candidate)
    return bool(verifications) and not any(
        _verification_content_matches_historical_inventory(item)
        for item in verifications
    )


def _annotate_verification_content_match(candidate: dict[str, Any]) -> bool:
    matched = False
    for item in candidate.get("verification") or []:
        if not isinstance(item, dict):
            continue
        if (
            item.get("verified") is True
            and item.get("page_role") == ITEM_LISTING
            and item.get("listing_status") == ENDED
        ):
            item_match = _verification_content_matches_historical_inventory(item)
            item["verification_content_match"] = item_match
            matched = matched or item_match
    candidate["verification_content_match"] = matched
    return matched


def _route_historical_market_evidence(candidate: dict[str, Any]) -> None:
    _annotate_verification_content_match(candidate)
    candidate["opportunity_state"] = HISTORICAL_MARKET_EVIDENCE
    candidate["reason"] = (
        "verified ended listing retained in the Historical Market Evidence path only"
    )
    candidate["top5_eligible"] = False
    candidate["analysis_eligible"] = False
    candidate["historical_market_evidence_eligible"] = True
    candidate["historical_data_fields_trusted"] = True
    candidate["next_verification_step"] = None
    candidate["next_action"] = "Retain as historical market evidence only."

    existing_why = [
        str(item)
        for item in candidate.get("why_opportunity") or []
        if "pending further verification" not in str(item).lower()
        and "active sale confirmed" not in str(item).lower()
    ]
    candidate["why_opportunity"] = list(dict.fromkeys([
        *existing_why,
        "verified ended clothing-inventory listing retained as historical market evidence",
    ]))

    confirmed = [
        str(item)
        for item in candidate.get("confirmed_information") or []
        if not str(item).startswith("discovery state:")
    ]
    confirmed.insert(1, f"discovery state: {HISTORICAL_MARKET_EVIDENCE}")
    candidate["confirmed_information"] = confirmed
    candidate["missing_information"] = [
        item
        for item in candidate.get("missing_information") or []
        if item != "active/ended status"
    ]


def _route_historical_evidence_manual_review(candidate: dict[str, Any]) -> None:
    _annotate_verification_content_match(candidate)
    candidate["opportunity_state"] = HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW
    candidate["reason"] = (
        "verified ended item page does not contain matching bounded bulk clothing-inventory evidence"
    )
    candidate["top5_eligible"] = False
    candidate["analysis_eligible"] = False
    candidate["historical_market_evidence_eligible"] = False
    candidate["historical_data_fields_trusted"] = False
    candidate["next_verification_step"] = None
    candidate["next_action"] = (
        "Review archived item evidence manually before historical market intake."
    )
    candidate["inventory_type"] = None
    candidate["quantity"] = None
    candidate["price_nok"] = None
    candidate["bid_price_nok"] = None

    candidate["why_opportunity"] = [
        item
        for item in candidate.get("why_opportunity") or []
        if "historical market evidence" not in str(item).lower()
        and "pending further verification" not in str(item).lower()
    ]
    candidate["why_opportunity"].append(
        "ended item identity verified, but bounded page content does not prove the advertised clothing lot"
    )
    confirmed = [
        str(item)
        for item in candidate.get("confirmed_information") or []
        if not str(item).startswith("discovery state:")
    ]
    confirmed.insert(
        1,
        f"discovery state: {HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW}",
    )
    candidate["confirmed_information"] = confirmed
    missing = list(candidate.get("missing_information") or [])
    if "matching bounded item description" not in missing:
        missing.append("matching bounded item description")
    candidate["missing_information"] = missing


def _traceable_event(candidate: Mapping[str, Any]) -> tuple[str, str] | None:
    if candidate.get("listing_status") == ENDED:
        return None
    if candidate.get("page_role") == ITEM_LISTING:
        return None
    if candidate.get("page_role") in _EXCLUDED_VERIFIED_ROLES:
        return None
    if _has_excluded_verified_role(candidate):
        return None

    urls = candidate.get("source_urls") or []
    canonical_urls = [_normalize_public_url(str(url)) for url in urls]
    if not canonical_urls or not all(canonical_urls):
        return None
    if all(urlparse(url).path in {"", "/"} for url in canonical_urls):
        return None

    title = str(candidate.get("title") or "")
    title_tokens = _specific_title_tokens(title)
    if len(title_tokens) < 2:
        return None

    context = _verification_context(candidate)
    scenario = _scenario_from_text(context)
    if scenario is None:
        return None
    if not any(term in context for term in _APPAREL_TERMS):
        return None
    if not (
        any(term in context for term in _BUSINESS_TERMS)
        or re.search(r"\b(?:as|asa)\b", context)
    ):
        return None
    entity_anchor = (
        bool(candidate.get("company_name"))
        or bool(re.search(r"\b(?:as|asa)\b", _normalized_text(title)))
        or _extract_location(context) is not None
    )
    if not entity_anchor:
        return None

    identity = f"event-title:{scenario.lower()}:{' '.join(sorted(title_tokens))}"
    return scenario, identity


def _extract_location(context: str) -> str | None:
    for location in _NORWAY_LOCATION_TERMS:
        if re.search(rf"\b{re.escape(location)}\b", context, re.I):
            return location.title()
    return None


def _analysis_eligible(candidate: Mapping[str, Any]) -> bool:
    return bool(
        candidate.get("page_role") == ITEM_LISTING
        and candidate.get("identity_stable") is True
        and candidate.get("listing_status") == ACTIVE
        and candidate.get("opportunity_state") == CONFIRMED_SALE
        and candidate.get("top5_eligible") is True
        and candidate.get("source_urls")
        and all(_normalize_public_url(str(url)) for url in candidate.get("source_urls") or [])
    )


def _restore_event_lead(candidate: dict[str, Any], scenario: str, identity: str) -> None:
    context = _verification_context(candidate)
    candidate["scenario"] = scenario
    candidate["opportunity_state"] = STRONG_LEAD_REQUIRES_VERIFICATION
    candidate["reason"] = (
        "traceable early commercial event retained; inventory availability and sale route require verification"
    )
    candidate["page_role"] = EVENT_LEAD
    candidate["opportunity_identity"] = identity
    candidate["identity_stable"] = True
    candidate["top5_eligible"] = True
    candidate["analysis_eligible"] = False
    candidate["listing_status"] = UNKNOWN
    candidate["price_nok"] = None
    candidate["bid_price_nok"] = None
    candidate["quantity"] = None
    candidate["inventory_type"] = None
    candidate["location"] = candidate.get("location") or _extract_location(context)

    breakdown = dict(candidate.get("score_breakdown") or {})
    breakdown.update({
        "commercial_event_strength": _EVENT_PRIORITY[scenario],
        "clothing_inventory_clarity": max(12, int(breakdown.get("clothing_inventory_clarity") or 0)),
        "sale_signal": 8,
        "source_traceability": 15,
        "location_logistics": 5 if candidate.get("location") else 0,
        "price_or_quantity": 0,
    })
    breakdown.setdefault("freshness", 0)
    candidate["score_breakdown"] = breakdown
    candidate["discovery_score"] = sum(
        int(breakdown.get(key) or 0)
        for key in (
            "commercial_event_strength", "clothing_inventory_clarity", "sale_signal",
            "source_traceability", "freshness", "location_logistics", "price_or_quantity",
        )
    )
    candidate["discovery_band"] = (
        "HIGH" if candidate["discovery_score"] >= 80
        else "REVIEW" if candidate["discovery_score"] >= 55
        else "LOW"
    )

    candidate["why_opportunity"] = [
        f"traceable early commercial event detected: {scenario}",
        "apparel business scope detected",
        "inventory availability remains unconfirmed",
    ]
    confirmed = [
        f"traceable public sources: {len(candidate.get('source_urls') or [])}",
        f"discovery state: {STRONG_LEAD_REQUIRES_VERIFICATION}",
        f"page role: {EVENT_LEAD}",
        f"commercial event: {scenario}",
    ]
    if candidate.get("location"):
        confirmed.append(f"location: {candidate['location']}")
    candidate["confirmed_information"] = confirmed
    candidate["missing_information"] = [
        "inventory availability", "sale route", "price", "quantity", "active sale status",
    ]
    candidate["next_verification_step"] = (
        "Confirm publicly whether Clothing Inventory is available for sale and identify the sale or contact route."
    )


def apply_early_opportunity_gate(result: Mapping[str, Any]) -> dict[str, Any]:
    """Return corrected artifacts with early event leads visible but analysis-blocked."""
    corrected = deepcopy(dict(result))
    candidates = corrected.get("all_discovered_candidates")
    report = corrected.get("search_run_report")
    if not isinstance(candidates, list) or not isinstance(report, dict):
        raise ValueError("invalid Clothing Inventory discovery result")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("all_discovered_candidates must contain objects")
        if _verified_historical_item_listing(candidate):
            _route_historical_market_evidence(candidate)
            continue
        if _historical_item_requires_manual_review(candidate):
            _route_historical_evidence_manual_review(candidate)
            continue
        traceable = _traceable_event(candidate)
        if traceable is not None:
            _restore_event_lead(candidate, *traceable)
        else:
            candidate["analysis_eligible"] = _analysis_eligible(candidate)
            candidate["historical_market_evidence_eligible"] = False
            candidate.setdefault("historical_data_fields_trusted", False)

    eligible = [
        candidate for candidate in candidates
        if candidate.get("top5_eligible") is True and candidate.get("listing_status") != ENDED
    ]
    top5 = sorted(
        eligible,
        key=lambda item: (
            int(item.get("discovery_score") or 0),
            len(item.get("source_urls") or []),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )[:5]
    corrected["discovery_top5"] = deepcopy(top5)

    for candidate in corrected["discovery_top5"]:
        candidate["analysis_eligible"] = _analysis_eligible(candidate)

    confirmed_sales = sum(
        candidate.get("opportunity_state") == CONFIRMED_SALE
        and candidate.get("listing_status") != ENDED
        for candidate in candidates
    )
    strong_leads = sum(
        candidate.get("opportunity_state") == STRONG_LEAD_REQUIRES_VERIFICATION
        and candidate.get("listing_status") != ENDED
        for candidate in candidates
    )
    historical_market_evidence = sum(
        candidate.get("opportunity_state") == HISTORICAL_MARKET_EVIDENCE
        for candidate in candidates
    )
    historical_manual_review = sum(
        candidate.get("opportunity_state")
        == HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW
        for candidate in candidates
    )
    confirmed_top = sum(
        candidate.get("opportunity_state") == CONFIRMED_SALE
        for candidate in corrected["discovery_top5"]
    )
    bands = {"HIGH": 0, "REVIEW": 0, "LOW": 0}
    for candidate in candidates:
        band = candidate.get("discovery_band")
        if band in bands:
            bands[band] += 1

    report.update({
        "schema_version": "clothing-inventory-discovery-search-1.2",
        "recovery_gate_applied": True,
        "historical_market_evidence_gate_applied": True,
        "historical_content_match_gate_applied": True,
        "rejected_results": sum(
            candidate.get("opportunity_state") == REJECTED_NOISE for candidate in candidates
        ),
        "confirmed_sales": confirmed_sales,
        "strong_leads_requiring_verification": strong_leads,
        "historical_market_evidence": historical_market_evidence,
        "historical_evidence_manual_review": historical_manual_review,
        "ended_or_historical": sum(
            candidate.get("listing_status") == ENDED for candidate in candidates
        ),
        "early_event_leads": sum(candidate.get("page_role") == EVENT_LEAD for candidate in candidates),
        "early_event_leads_in_top5": sum(
            candidate.get("page_role") == EVENT_LEAD for candidate in corrected["discovery_top5"]
        ),
        "analysis_eligible_count": sum(
            candidate.get("analysis_eligible") is True for candidate in candidates
        ),
        "discovery_bands": bands,
        "top5_count": len(corrected["discovery_top5"]),
        "top5_eligible_count": len(eligible),
        "generic_pages_excluded": sum(
            candidate.get("page_role") in _GENERIC_ROLES for candidate in candidates
        ),
        "opportunity_quality_status": (
            "NO_VALID_OPPORTUNITIES" if not corrected["discovery_top5"]
            else "PASS" if confirmed_top
            else "REVIEW_REQUIRED"
        ),
        "no_opportunities_found": not corrected["discovery_top5"],
    })
    report["automatic_contact"] = False
    report["automatic_purchase_decision"] = False
    report["financial_ranking_used"] = False
    return corrected
