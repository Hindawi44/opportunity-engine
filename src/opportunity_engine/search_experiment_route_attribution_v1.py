"""Page-native commercial-route attribution for Search Experiment results.

A search query may ask for an auction, insolvency liquidation, wholesale stock,
or direct inventory, but query intent is not proof of the route that actually
produced a strict Exact-Lot.  This gate re-reads only already-verified result
pages and attributes each page from its own public content.

The gate is intentionally conservative and review-only:
- no additional search-provider requests;
- no source/domain pinning;
- no query text used as attribution evidence;
- no automatic source/query/provider activation;
- no production or commercial mutation.
"""
from __future__ import annotations

from collections import Counter
import html
import re
import unicodedata
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from opportunity_engine.discovery.keyword_shadow_verification import (
    PageFetchResult,
    fetch_public_page,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


SCHEMA_VERSION = "search-experiment-route-attribution-1.0"
MAX_ROUTE_ATTRIBUTION_PAGE_FETCHES = 18

_COMMERCIAL_CLOTHING_SLOTS = frozenset(
    {"AUCTION", "DIRECT_INVENTORY", "LIQUIDATION_BANKRUPTCY", "WHOLESALE_STOCK_LOTS"}
)

# Strong page-local sale-mechanism terms.  A judicial auction is attributed to
# AUCTION (the sale mechanism) rather than also counting as a second liquidation
# family.  That precedence prevents one page from proving two route families.
_AUCTION_MARKERS = (
    "vente aux enchères",
    "vente aux encheres",
    "vente judiciaire",
    "lot judiciaire",
    "adjudication",
    "judicial auction",
    "online auction",
    "auction",
    "auksjon",
    "nettauksjon",
    "auktion",
    "auktionen",
    "versteigerung",
    "zwangsversteigerung",
    "veiling",
    "executieveiling",
    "asta giudiziaria",
    "vendita all'asta",
    "vendita all’asta",
    "asta online",
)

_LIQUIDATION_MARKERS = (
    "liquidation judiciaire",
    "redressement judiciaire",
    "procédure collective",
    "procedure collective",
    "cessation des paiements",
    "mandataire judiciaire",
    "liquidation totale",
    "insolvency",
    "insolvent",
    "bankruptcy",
    "bankrupt",
    "liquidation sale",
    "konkurs",
    "konkursbo",
    "konkursboet",
    "tvangsavvikling",
    "insolvenz",
    "insolvenzverfahren",
    "insolvenzmasse",
    "faillissement",
    "failliet",
    "curator",
    "fallimento",
    "liquidazione giudiziale",
    "procedura concorsuale",
)

_WHOLESALE_MARKERS = (
    "wholesale",
    "b2b",
    "grossist",
    "grossister",
    "engros",
    "großhandel",
    "grosshandel",
    "grossiste",
    "grossistes",
    "groothandel",
    "ingrosso",
    "stocklot",
    "stock lot",
    "lot de gros",
    "vente en gros",
)

PageFetcher = Callable[[str], PageFetchResult]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalise(value: object) -> str:
    decoded = html.unescape(_text(value))
    return unicodedata.normalize("NFKC", decoded).casefold()


def _term_present(normalised_text: str, term: str) -> bool:
    needle = _normalise(term)
    if not needle:
        return False
    return re.search(
        rf"(?<!\w){re.escape(needle)}(?!\w)",
        normalised_text,
        flags=re.UNICODE,
    ) is not None


def _matched(normalised_text: str, terms: tuple[str, ...]) -> list[str]:
    return sorted({term for term in terms if _term_present(normalised_text, term)})


def _domain(url: object) -> str:
    try:
        return (urlsplit(_text(url)).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _page_route_family(*, title: object, text: object) -> tuple[str, dict[str, list[str]]]:
    """Classify one fetched Exact-Lot page without looking at the search query."""
    page_text = _normalise(f"{_text(title)} {_text(text)}")
    matches = {
        "AUCTION": _matched(page_text, _AUCTION_MARKERS),
        "LIQUIDATION_BANKRUPTCY": _matched(page_text, _LIQUIDATION_MARKERS),
        "WHOLESALE_STOCK_LOTS": _matched(page_text, _WHOLESALE_MARKERS),
    }
    if matches["AUCTION"]:
        family = "AUCTION"
    elif matches["LIQUIDATION_BANKRUPTCY"]:
        family = "LIQUIDATION_BANKRUPTCY"
    elif matches["WHOLESALE_STOCK_LOTS"]:
        family = "WHOLESALE_STOCK_LOTS"
    else:
        family = "DIRECT_INVENTORY"
    return family, matches


def apply_route_attribution_gate(
    result: Mapping[str, Any],
    *,
    page_fetcher: PageFetcher = fetch_public_page,
    max_page_fetches: int = MAX_ROUTE_ATTRIBUTION_PAGE_FETCHES,
) -> dict[str, Any]:
    """Filter a clothing Search Experiment success to its page-proven route family.

    Strict Exact-Lot qualification remains owned by the existing Search ->
    Verification -> Multi-Hop pipeline.  This function answers only the later
    attribution question: did those already-qualified pages actually prove the
    commercial route family requested by the teaching slot?
    """
    report = dict(result)
    spec = _mapping(report.get("spec"))
    domain = _upper(spec.get("project_domain"))
    slot_id = _upper(spec.get("slot_id"))

    if not 1 <= int(max_page_fetches) <= MAX_ROUTE_ATTRIBUTION_PAGE_FETCHES:
        raise ValueError(
            f"max_page_fetches must be between 1 and {MAX_ROUTE_ATTRIBUTION_PAGE_FETCHES}"
        )

    # Fabric and SEARCH_PROVIDER_ROUTE have their own evidence contracts and are
    # deliberately untouched by the commercial clothing-family gate.
    if domain != CLOTHING_INVENTORY or slot_id not in _COMMERCIAL_CLOTHING_SLOTS:
        report.update(
            {
                "route_attribution_schema_version": SCHEMA_VERSION,
                "route_attribution_gate_enforced": False,
                "route_attribution_gate_status": "NOT_REQUIRED",
                "route_attribution_slot_id": slot_id or None,
                "route_attribution_page_fetches_attempted": 0,
                "route_attribution_page_fetches_succeeded": 0,
                "route_attribution_rejected_count": 0,
                "route_attribution_audit": [],
                "route_attribution_query_is_evidence": False,
                "search_requests_added_by_route_attribution": 0,
            }
        )
        return report

    original_urls = []
    seen_original: set[str] = set()
    for raw in report.get("verified_result_urls") or []:
        url = _text(raw)
        if not url or url in seen_original:
            continue
        seen_original.add(url)
        original_urls.append(url)

    accepted_urls: list[str] = []
    accepted_domains: set[str] = set()
    audit: list[dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()
    fetch_attempts = 0
    fetch_successes = 0

    for index, url in enumerate(original_urls):
        if fetch_attempts >= max_page_fetches:
            reason = "ATTRIBUTION_FETCH_CAP_REACHED"
            rejection_reasons[reason] += 1
            audit.append(
                {
                    "url": url,
                    "fetch_ok": False,
                    "detected_route_family": None,
                    "verification_decision": "REJECT",
                    "rejection_reason": reason,
                    "route_query_used_as_evidence": False,
                }
            )
            continue

        fetch_attempts += 1
        fetched = page_fetcher(url)
        final_url = _text(fetched.final_url or url)
        if not fetched.ok:
            reason = "FETCH_FAILED"
            rejection_reasons[reason] += 1
            audit.append(
                {
                    "url": url,
                    "final_url": final_url,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "fetch_error": _text(fetched.error) or None,
                    "detected_route_family": None,
                    "verification_decision": "REJECT",
                    "rejection_reason": reason,
                    "route_query_used_as_evidence": False,
                }
            )
            continue

        fetch_successes += 1
        family, marker_matches = _page_route_family(
            title=fetched.title,
            text=fetched.text,
        )
        accepted = family == slot_id
        reason = None if accepted else f"ROUTE_FAMILY_MISMATCH:{family}"
        if reason:
            rejection_reasons[reason] += 1
        if accepted and final_url not in accepted_urls:
            accepted_urls.append(final_url)
            host = _domain(final_url)
            if host:
                accepted_domains.add(host)

        audit.append(
            {
                "url": url,
                "final_url": final_url,
                "title": _text(fetched.title)[:500] or None,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "detected_route_family": family,
                "route_marker_matches": marker_matches,
                "verification_decision": "ACCEPT" if accepted else "REJECT",
                "rejection_reason": reason,
                "route_query_used_as_evidence": False,
            }
        )

    successful = bool(accepted_urls)
    report.update(
        {
            "outcome": "VERIFIED_ROUTE_SUCCESS" if successful else "NO_VERIFIED_ROUTE",
            "successful_route": successful,
            "pre_attribution_successful_result_count": int(
                report.get("successful_result_count") or len(original_urls)
            ),
            "successful_result_count": len(accepted_urls),
            "verified_result_urls": accepted_urls,
            "verified_result_domains": sorted(accepted_domains),
            "route_attribution_schema_version": SCHEMA_VERSION,
            "route_attribution_gate_enforced": True,
            "route_attribution_gate_status": "PASS" if successful else "VALID_ZERO_NO_PAGE_PROVEN_ROUTE",
            "route_attribution_slot_id": slot_id,
            "route_attribution_page_evidence_required": True,
            "route_attribution_page_fetch_cap": max_page_fetches,
            "route_attribution_page_fetches_attempted": fetch_attempts,
            "route_attribution_page_fetches_succeeded": fetch_successes,
            "route_attribution_rejected_count": sum(rejection_reasons.values()),
            "route_attribution_rejection_reason_counts": dict(sorted(rejection_reasons.items())),
            "route_attribution_audit": audit,
            "route_attribution_query_is_evidence": False,
            "route_attribution_source_or_domain_pinning": False,
            "search_requests_added_by_route_attribution": 0,
        }
    )
    return report
