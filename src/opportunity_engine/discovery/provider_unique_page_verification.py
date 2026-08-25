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

When a previous checkpoint SQLite database is available, Exa may also use spare
capacity under the existing global 30-page verification ceiling to re-fetch a
previously verified Exact-Lot URL, but only when today's Exa result set contains
the same web host. This is navigation/recovery evidence only: the old database
row never qualifies a lot, every recovery URL is fetched and classified again,
and recovery rows are excluded from Tool Learning provider credit.
"""
from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlsplit

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
    _looks_item_specific_url,
    fetch_public_page,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

SCHEMA_VERSION = "search-provider-unique-page-verification-1.1"
SUPPORTED_PROVIDERS = frozenset({"exa", "brave"})
PROVEN_ROUTE_RECOVERY_PROVIDER = "proven_route_recovery"
MAX_PROVEN_ROUTE_RECOVERY_FETCHES = 12

# B2B role words alone are not sale proof. They may upgrade one already-proven
# clothing inventory page to ACTIVE_STOCK_SIGNAL only when the fetched page also
# contains a concrete price or quantity signal. Exact-Lot requirements remain
# unchanged and still require an item-specific page with strict evidence.
_B2B_WHOLESALE_MARKERS = (
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
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalized_host(url: object) -> str:
    try:
        host = (urlsplit(_compact(url)).hostname or "").casefold()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _restored_exact_lot_database(market: str) -> Path | None:
    input_root = _compact(os.environ.get("INPUT_ROOT"))
    if not input_root:
        return None
    path = Path(input_root) / f"{market.casefold()}-exa-exact-lot" / "opportunity_engine.db"
    return path if path.is_file() else None


def _load_proven_route_recovery_candidates(
    *,
    market: str,
    current_hosts: set[str],
    current_urls: set[str],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    """Load prior strict URLs only for a host Exa independently rediscovered today.

    SQLite is route memory, never qualification evidence. Returned URLs are only
    candidates for a fresh public-page fetch and must pass the normal verifier
    again before downstream Exact-Lot acceptance.
    """
    if limit <= 0 or not current_hosts:
        return []
    database = _restored_exact_lot_database(market)
    if database is None:
        return []

    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                """
                SELECT source_url, title
                FROM unified_opportunities
                WHERE market_code = ?
                  AND domain = ?
                  AND UPPER(source_provider) = 'EXA'
                  AND verified = 1
                  AND identity_stable = 1
                  AND top5_eligible = 1
                ORDER BY last_seen_at DESC, id DESC
                """,
                (market, CLOTHING_INVENTORY),
            ).fetchall()
        finally:
            connection.close()
    except (sqlite3.Error, OSError):
        return []

    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_url, raw_title in rows:
        url = _compact(raw_url)
        if not url or url in current_urls or url in seen:
            continue
        if _normalized_host(url) not in current_hosts:
            continue
        if not _looks_item_specific_url(url):
            continue
        seen.add(url)
        output.append(
            {
                "market_code": market,
                "query": query,
                "title": _compact(raw_title),
                "url": url,
                "domain": _normalized_host(url),
                "provider": PROVEN_ROUTE_RECOVERY_PROVIDER,
                "proven_route_recovery": "true",
            }
        )
        if len(output) >= limit:
            break
    return output


def _base(*, provider: str, max_page_fetches: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "shadow_only": True,
        "max_page_fetches": max_page_fetches,
        "total_page_fetch_cap": MAX_ALLOWED_PAGE_FETCHES,
        "proven_route_recovery_enabled": provider == "exa",
        "proven_route_recovery_current_exa_host_required": True,
        "proven_route_memory_is_qualification_evidence": False,
        "proven_route_recovery_tool_learning_credit": False,
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


def _qualified_b2b_active_stock(
    *,
    classification: str,
    evidence: dict[str, Any],
    title: str,
    text: str,
) -> tuple[str, dict[str, Any]]:
    """Conservatively recognize B2B stock-sale pages missed by literal sale verbs.

    A wholesale role is never enough on its own. The page must already prove
    CLOTHING_INVENTORY + inventory evidence and also expose price or quantity.
    Buyer/source pages and info/legal pages remain excluded. This may create an
    aggregate ACTIVE_STOCK_SIGNAL for bounded navigation, never an Exact-Lot.
    """
    updated = dict(evidence)
    combined = _compact(f"{title} {text}").casefold()
    has_b2b_role = any(marker in combined for marker in _B2B_WHOLESALE_MARKERS)
    qualifies = bool(
        classification == UNPROVEN_PAGE
        and updated.get("project_domain") == CLOTHING_INVENTORY
        and updated.get("inventory_evidence") is True
        and has_b2b_role
        and (
            updated.get("price_evidence") is True
            or updated.get("quantity_evidence") is True
        )
        and updated.get("buyer_or_source_evidence") is not True
        and updated.get("info_or_legal_evidence") is not True
    )
    updated["b2b_wholesale_evidence"] = has_b2b_role
    updated["qualified_b2b_sale_evidence"] = qualifies
    if not qualifies:
        return classification, updated
    updated["direct_sale_evidence"] = True
    return ACTIVE_STOCK_SIGNAL, updated


def _verify_fetched_candidate(
    candidate: dict[str, str],
    *,
    page_fetcher: PageFetcher,
    allow_tool_learning_credit: bool,
) -> tuple[dict[str, Any], bool]:
    fetched = page_fetcher(candidate["url"])
    if not fetched.ok:
        return (
            {
                **candidate,
                "classification": FETCH_FAILED,
                "fetch_ok": False,
                "status_code": fetched.status_code,
                "final_url": fetched.final_url,
                "fetch_error": fetched.error,
                "tool_learning_useful": False,
                "evidence": {},
            },
            False,
        )

    page_title = fetched.title or candidate["title"]
    classification, evidence = _classify_page(
        title=page_title,
        text=fetched.text,
        url=fetched.final_url or candidate["url"],
    )
    classification, evidence = _qualified_b2b_active_stock(
        classification=classification,
        evidence=evidence,
        title=page_title,
        text=fetched.text,
    )
    return (
        {
            **candidate,
            "classification": classification,
            "fetch_ok": True,
            "status_code": fetched.status_code,
            "final_url": fetched.final_url,
            "fetch_error": None,
            "truncated": fetched.truncated,
            "tool_learning_useful": bool(
                allow_tool_learning_credit and _tool_learning_useful(classification, evidence)
            ),
            "evidence": evidence,
        },
        True,
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
        row, ok = _verify_fetched_candidate(
            candidate,
            page_fetcher=page_fetcher,
            allow_tool_learning_credit=True,
        )
        verified_pages.append(row)
        if ok:
            succeeded += 1

    recovery_candidates: list[dict[str, str]] = []
    recovery_attempted = 0
    recovery_succeeded = 0
    if normalized_provider == "exa":
        spare_global_capacity = max(0, MAX_ALLOWED_PAGE_FETCHES - attempted)
        recovery_limit = min(MAX_PROVEN_ROUTE_RECOVERY_FETCHES, spare_global_capacity)
        if recovery_limit:
            current_hosts_by_market: dict[str, set[str]] = {}
            current_query_by_market: dict[str, str] = {}
            for candidate in candidates:
                market = candidate["market_code"]
                host = _normalized_host(candidate["url"])
                if host:
                    current_hosts_by_market.setdefault(market, set()).add(host)
                current_query_by_market.setdefault(market, candidate["query"])

            remaining = recovery_limit
            for market in sorted(current_hosts_by_market):
                if remaining <= 0:
                    break
                rows = _load_proven_route_recovery_candidates(
                    market=market,
                    current_hosts=current_hosts_by_market[market],
                    current_urls=seen_urls,
                    query=current_query_by_market.get(market, ""),
                    limit=remaining,
                )
                recovery_candidates.extend(rows)
                remaining -= len(rows)

        for candidate in recovery_candidates:
            recovery_attempted += 1
            row, ok = _verify_fetched_candidate(
                candidate,
                page_fetcher=page_fetcher,
                allow_tool_learning_credit=False,
            )
            row["proven_route_recovery"] = True
            row["proven_route_memory_is_qualification_evidence"] = False
            row["fresh_page_verification_required"] = True
            verified_pages.append(row)
            if ok:
                recovery_succeeded += 1

    primary_pages = [
        item for item in verified_pages if item.get("provider") != PROVEN_ROUTE_RECOVERY_PROVIDER
    ]
    recovery_pages = [
        item for item in verified_pages if item.get("provider") == PROVEN_ROUTE_RECOVERY_PROVIDER
    ]
    primary_counts = Counter(item["classification"] for item in primary_pages)
    recovery_counts = Counter(item["classification"] for item in recovery_pages)
    useful_count = sum(1 for item in primary_pages if item.get("tool_learning_useful") is True)
    out_of_domain_count = sum(
        1
        for item in primary_pages
        if item.get("fetch_ok") is True
        and (item.get("evidence") or {}).get("project_domain") == OUT_OF_DOMAIN
    )
    non_specific_active_filtered = sum(
        1
        for item in primary_pages
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
        "total_page_fetches_attempted": attempted + recovery_attempted,
        "total_page_fetches_succeeded": succeeded + recovery_succeeded,
        "budget_exhausted_count": budget_exhausted,
        "proven_route_recovery_candidate_count": len(recovery_candidates),
        "proven_route_recovery_page_fetches_attempted": recovery_attempted,
        "proven_route_recovery_page_fetches_succeeded": recovery_succeeded,
        "proven_route_recovery_exact_lot_candidate_count": recovery_counts[EXACT_LOT_CANDIDATE],
        "proven_route_recovery_uses_only_spare_global_capacity": True,
        "useful_clothing_signal_count": useful_count,
        "provider_exact_lot_candidate_count": primary_counts[EXACT_LOT_CANDIDATE],
        "exact_lot_candidate_count": (
            primary_counts[EXACT_LOT_CANDIDATE] + recovery_counts[EXACT_LOT_CANDIDATE]
        ),
        "active_stock_signal_count": primary_counts[ACTIVE_STOCK_SIGNAL],
        "non_specific_active_filtered_count": non_specific_active_filtered,
        "out_of_domain_count": out_of_domain_count,
        "source_intelligence_only_count": primary_counts[SOURCE_INTELLIGENCE_ONLY],
        "info_or_legal_only_count": primary_counts[INFO_OR_LEGAL_ONLY],
        "unproven_page_count": primary_counts[UNPROVEN_PAGE],
        "fetch_failed_count": primary_counts[FETCH_FAILED],
        "verified_pages": verified_pages,
    }
