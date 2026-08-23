"""Symmetric exact-page verification for search-provider unique discoveries.

This layer exists so Tool Learning compares Exa and Brave on the same evidence
standard. Raw hit counts, snippets, broad articles and aggregate stock pages are
not provider quality.

A provider receives positive Tool Learning credit only when its unique original
page is fetched successfully, proves CLOTHING_INVENTORY, and has commercial page
specificity strong enough for the comparison contract:

* EXACT_LOT_CANDIDATE always qualifies;
* ACTIVE_STOCK_SIGNAL qualifies only when the verified URL is item-specific.

Out-of-domain evidence is counted as noise from the domain classifier even when
the page's broader content classification is UNPROVEN_PAGE or another non-sale
class. The verifier remains shadow-only and cannot activate a provider.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
    FETCH_FAILED,
    INFO_OR_LEGAL_ONLY,
    MAX_ALLOWED_PAGE_FETCHES,
    NOT_FETCHED_BUDGET,
    OUT_OF_DOMAIN,
    SOURCE_INTELLIGENCE_ONLY,
    SUPPORTED_MARKETS,
    UNPROVEN_PAGE,
    PageFetcher,
    _classify_page,
    fetch_public_page,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

SCHEMA_VERSION = "search-provider-unique-page-verification-1.1"
SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _base(*, provider: str, max_page_fetches: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "shadow_only": True,
        "max_page_fetches": max_page_fetches,
        "required_project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "automatic_provider_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _tool_learning_useful(classification: str, evidence: dict[str, Any]) -> bool:
    if evidence.get("project_domain") != CLOTHING_INVENTORY:
        return False
    if classification == EXACT_LOT_CANDIDATE:
        return True
    return bool(
        classification == ACTIVE_STOCK_SIGNAL
        and evidence.get("item_specific_url_evidence") is True
    )


def verify_provider_unique_pages(
    benchmark_report: dict[str, Any],
    *,
    provider: str,
    page_fetcher: PageFetcher = fetch_public_page,
    max_page_fetches: int = 18,
) -> dict[str, Any]:
    """Verify URLs unique to one provider against the other provider's results."""
    normalized_provider = _compact(provider).casefold()
    if normalized_provider not in SUPPORTED_PROVIDERS:
        raise ValueError("provider must be exa or brave")
    if not 1 <= max_page_fetches <= MAX_ALLOWED_PAGE_FETCHES:
        raise ValueError(f"max_page_fetches must be between 1 and {MAX_ALLOWED_PAGE_FETCHES}")

    base = _base(provider=normalized_provider, max_page_fetches=max_page_fetches)
    if benchmark_report.get("status") != "SUCCESS":
        return {
            **base,
            "status": "BLOCKED_INPUT",
            "block_reason": "BENCHMARK_NOT_SUCCESSFUL",
            "provider_unique_url_count": 0,
            "verified_pages": [],
        }
    if benchmark_report.get("shadow_only") is not True:
        return {
            **base,
            "status": "BLOCKED_INPUT",
            "block_reason": "INPUT_NOT_SHADOW_ONLY",
            "provider_unique_url_count": 0,
            "verified_pages": [],
        }
    if benchmark_report.get("project_domain_gate_enforced") is not True or _compact(
        benchmark_report.get("project_domain")
    ) != CLOTHING_INVENTORY:
        return {
            **base,
            "status": "BLOCKED_INPUT",
            "block_reason": "BENCHMARK_NOT_CLOTHING_DOMAIN_GATED",
            "provider_unique_url_count": 0,
            "verified_pages": [],
        }

    other_provider = "brave" if normalized_provider == "exa" else "exa"
    candidates: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for market_row in benchmark_report.get("market_results") or []:
        if not isinstance(market_row, dict):
            continue
        market = _compact(market_row.get("market_code")).upper()
        if market not in SUPPORTED_MARKETS:
            continue
        other_results = (market_row.get(other_provider) or {}).get("results") or []
        other_urls = {
            _compact(item.get("url"))
            for item in other_results
            if isinstance(item, dict) and _compact(item.get("url"))
        }
        provider_results = (market_row.get(normalized_provider) or {}).get("results") or []
        for item in provider_results:
            if not isinstance(item, dict):
                continue
            url = _compact(item.get("url"))
            if not url or url in other_urls or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "market_code": market,
                    "query": _compact(market_row.get("query")),
                    "title": _compact(item.get("title")),
                    "url": url,
                    "domain": _compact(item.get("domain")),
                    "provider": normalized_provider,
                }
            )

    verified_pages: list[dict[str, Any]] = []
    attempted = 0
    succeeded = 0
    budget_exhausted = 0

    for candidate in candidates:
        if attempted >= max_page_fetches:
            budget_exhausted += 1
            verified_pages.append(
                {
                    **candidate,
                    "classification": NOT_FETCHED_BUDGET,
                    "fetch_ok": False,
                    "status_code": None,
                    "final_url": candidate["url"],
                    "fetch_error": "PAGE_BUDGET_EXHAUSTED",
                    "tool_learning_useful": False,
                    "evidence": {},
                }
            )
            continue

        attempted += 1
        fetched = page_fetcher(candidate["url"])
        if not fetched.ok:
            verified_pages.append(
                {
                    **candidate,
                    "classification": FETCH_FAILED,
                    "fetch_ok": False,
                    "status_code": fetched.status_code,
                    "final_url": fetched.final_url,
                    "fetch_error": fetched.error,
                    "tool_learning_useful": False,
                    "evidence": {},
                }
            )
            continue

        succeeded += 1
        classification, evidence = _classify_page(
            title=fetched.title or candidate["title"],
            text=fetched.text,
            url=fetched.final_url or candidate["url"],
        )
        verified_pages.append(
            {
                **candidate,
                "classification": classification,
                "fetch_ok": True,
                "status_code": fetched.status_code,
                "final_url": fetched.final_url,
                "fetch_error": None,
                "truncated": fetched.truncated,
                "tool_learning_useful": _tool_learning_useful(classification, evidence),
                "evidence": evidence,
            }
        )

    counts = Counter(item["classification"] for item in verified_pages)
    useful_count = sum(1 for item in verified_pages if item.get("tool_learning_useful") is True)
    out_of_domain_count = sum(
        1
        for item in verified_pages
        if item.get("fetch_ok") is True
        and (item.get("evidence") or {}).get("project_domain") == OUT_OF_DOMAIN
    )
    non_specific_active_filtered = sum(
        1
        for item in verified_pages
        if item.get("classification") == ACTIVE_STOCK_SIGNAL
        and item.get("tool_learning_useful") is not True
    )

    return {
        **base,
        "status": "SUCCESS",
        "block_reason": None,
        "provider_unique_url_count": len(candidates),
        "page_fetches_attempted": attempted,
        "page_fetches_succeeded": succeeded,
        "budget_exhausted_count": budget_exhausted,
        "useful_clothing_signal_count": useful_count,
        "exact_lot_candidate_count": counts[EXACT_LOT_CANDIDATE],
        "active_stock_signal_count": counts[ACTIVE_STOCK_SIGNAL],
        "non_specific_active_filtered_count": non_specific_active_filtered,
        "out_of_domain_count": out_of_domain_count,
        "source_intelligence_only_count": counts[SOURCE_INTELLIGENCE_ONLY],
        "info_or_legal_only_count": counts[INFO_OR_LEGAL_ONLY],
        "unproven_page_count": counts[UNPROVEN_PAGE],
        "fetch_failed_count": counts[FETCH_FAILED],
        "verified_pages": verified_pages,
    }
