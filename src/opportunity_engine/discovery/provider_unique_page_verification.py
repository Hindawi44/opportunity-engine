"""Symmetric exact-page verification for search-provider unique discoveries.

This layer exists so Tool Learning compares Exa and Brave on the same evidence
standard. Raw hit counts, snippets, and domain counts are not provider quality.
A provider receives useful credit only when its unique original page is fetched
successfully and proves a CLOTHING_INVENTORY commercial signal under the same
classifier used by Exa shadow verification.

The verifier is shadow-only and cannot activate a provider or perform a
commercial action.
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

SCHEMA_VERSION = "search-provider-unique-page-verification-1.0"
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
        "production_provider_activation": False,
        "promotion_to_live_engine_enabled": False,
        "automatic_provider_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


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
                "evidence": evidence,
            }
        )

    counts = Counter(item["classification"] for item in verified_pages)
    useful_count = counts[EXACT_LOT_CANDIDATE] + counts[ACTIVE_STOCK_SIGNAL]

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
        "out_of_domain_count": counts[OUT_OF_DOMAIN],
        "source_intelligence_only_count": counts[SOURCE_INTELLIGENCE_ONLY],
        "info_or_legal_only_count": counts[INFO_OR_LEGAL_ONLY],
        "unproven_page_count": counts[UNPROVEN_PAGE],
        "fetch_failed_count": counts[FETCH_FAILED],
        "verified_pages": verified_pages,
    }
