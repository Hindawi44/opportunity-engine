"""Bounded two-stage recall waterfall for the verified QUERY_GAP scout.

The waterfall reuses the original scout's authoritative exact-page verifier,
durable memory merge, cost guard, and safety semantics. It also records bounded
read-only diagnostics for each page that actually consumed verification budget,
so operators can see *why* a page was rejected without relaxing the gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from opportunity_engine.automatic_query_gap_miss_scout import (
    DEFAULT_ACTIVE_QUERY_CONFIG,
    DEFAULT_MAX_PAGES,
    DEFAULT_SEARCH_RESULTS,
    MAX_PAGES,
    MEMORY_RELATIVE_PATH,
    OUTPUT_FILENAME,
    PageFetcher,
    PublicPage,
    _CLOSURE_MARKERS,
    _GAP_TERMS,
    _LIQUIDATION_MARKERS,
    _TEMPORARY_MARKERS,
    _attach_to_brief,
    _canonical,
    _checkpoint_urls,
    _extract_company,
    _merge_memory,
    _query_contains_term,
    _read_object,
    _safe_empty_report,
    _verify_closure_liquidation_page,
    _visible_text,
    _write_object,
    fetch_public_page,
)
from opportunity_engine.cost_guard import manual_paid_brave_block_reason
from opportunity_engine.daily_learning_runtime import load_active_learning_queries
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    load_missed_opportunity_memory,
    save_missed_opportunity_memory,
)

SCHEMA_VERSION = "automatic-query-gap-miss-scout-waterfall-1.1"
MAX_SEARCH_REQUESTS = 2

SCOUT_QUERIES_NO: tuple[str, ...] = (
    (
        '("legger ned" OR "legges ned" OR "stenger for godt" OR "siste åpningsdag") '
        '(butikk OR bedrift OR selskap) (varer OR varelager OR lagerbeholdning)'
    ),
    (
        '("legger ned" OR "legges ned" OR "stenger for godt" OR "stenger dørene" '
        'OR "siste åpningsdag" OR avvikles) '
        '(butikk OR forretning OR bedrift OR selskap)'
    ),
)
SCOUT_QUERY_NO = SCOUT_QUERIES_NO[0]

SearchCallback = Callable[[str], Sequence[SearchHit]]


def diagnose_public_page(page: PublicPage) -> dict[str, Any]:
    """Explain the authoritative verifier result without changing that result."""
    canonical_final = _canonical(page.final_url)
    html_ok = page.status_code == 200 and "text/html" in page.content_type.casefold()
    https_ok = bool(canonical_final and urlparse(canonical_final).scheme == "https")

    text = _visible_text(page.html) if html_ok else ""
    folded = text.casefold()
    temporary = bool(text and any(marker in folded for marker in _TEMPORARY_MARKERS))
    closure_markers = [marker for marker in _CLOSURE_MARKERS if marker in folded]
    sale_terms = [term for term in _GAP_TERMS if term in folded]
    liquidation_markers = [marker for marker in _LIQUIDATION_MARKERS if marker in folded]
    company = _extract_company(text) if text else None

    evidence_flags = {
        "http_status_ok": page.status_code == 200,
        "html_ok": html_ok,
        "https_ok": https_ok,
        "visible_text": bool(text),
        "temporary_closure": temporary,
        "closure_marker": bool(closure_markers),
        "sale_term": bool(sale_terms),
        "liquidation_marker": bool(liquidation_markers),
        "company_identity": bool(company),
    }

    rejection_reasons: list[str] = []
    if page.status_code != 200:
        rejection_reasons.append("HTTP_STATUS_NOT_OK")
    if not html_ok:
        rejection_reasons.append("HTML_REQUIRED")
    if not https_ok:
        rejection_reasons.append("HTTPS_REQUIRED")
    if temporary:
        rejection_reasons.append("TEMPORARY_CLOSURE_SIGNAL")
    if html_ok and not text:
        rejection_reasons.append("EMPTY_VISIBLE_TEXT")
    if not closure_markers:
        rejection_reasons.append("CLOSURE_MARKER_MISSING")
    if not sale_terms:
        rejection_reasons.append("SALE_TERM_MISSING")
    if not liquidation_markers:
        rejection_reasons.append("INVENTORY_LIQUIDATION_MISSING")
    if not company:
        rejection_reasons.append("COMPANY_IDENTITY_MISSING")

    authoritative_proof = _verify_closure_liquidation_page(page)
    if authoritative_proof is not None:
        verifier_status = "VERIFIED"
        rejection_reasons = []
    else:
        verifier_status = "REJECTED"
        if not rejection_reasons:
            rejection_reasons.append("AUTHORITATIVE_VERIFIER_REJECTED")

    return {
        "verifier_status": verifier_status,
        "requested_url": _canonical(page.requested_url) or page.requested_url,
        "final_url": canonical_final or page.final_url,
        "status_code": page.status_code,
        "content_type": page.content_type,
        "company": company,
        "closure_markers": closure_markers,
        "sale_terms": sale_terms,
        "liquidation_markers": liquidation_markers,
        "evidence_flags": evidence_flags,
        "rejection_reasons": rejection_reasons,
    }


def _new_gap_case(
    proof: Mapping[str, Any],
    *,
    observed_at: datetime,
) -> MissedOpportunityCase:
    final_url = str(proof["canonical_url"])
    return MissedOpportunityCase(
        case_id="auto-query-gap:no:" + sha256(final_url.encode("utf-8")).hexdigest()[:24],
        market_code="NO",
        discovered_by="AUTOMATIC_INDEPENDENT_QUERY_GAP_SCOUT",
        observed_at=observed_at,
        opportunity_type="VERIFIED_STORE_CLOSURE_INVENTORY_LIQUIDATION",
        stock_proven=True,
        ground_truth_company=str(proof["company"]),
        ground_truth_url=final_url,
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=str(proof["evidence_text"]),
    ).with_diagnosis()


def discover_query_gap_misses(
    checkpoint: Mapping[str, Any],
    *,
    active_queries: Sequence[str],
    search: SearchCallback,
    fetch_page: PageFetcher,
    observed_at: datetime | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Run the two-stage recall waterfall with one shared verification budget."""
    bounded_pages = max(0, min(MAX_PAGES, int(max_pages)))
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    core_urls = _checkpoint_urls(checkpoint)
    seen_urls: set[str] = set()
    cases: list[MissedOpportunityCase] = []
    metadata: list[dict[str, Any]] = []
    search_stages: list[dict[str, Any]] = []
    verification_attempts: list[dict[str, Any]] = []

    search_requests = 0
    total_hits = 0
    page_requests = 0
    verified_pages = 0
    core_known = 0
    no_new_term = 0

    for stage_index, query in enumerate(SCOUT_QUERIES_NO[:MAX_SEARCH_REQUESTS]):
        if page_requests >= bounded_pages:
            break

        raw_hits = [item for item in search(query) if isinstance(item, SearchHit)]
        search_requests += 1
        total_hits += len(raw_hits)

        stage_pages = 0
        stage_verified = 0
        stage_misses = 0
        stage_unique_hits = 0
        stage_page_budget = (
            min(1, bounded_pages - page_requests)
            if stage_index < len(SCOUT_QUERIES_NO) - 1
            else bounded_pages - page_requests
        )

        for hit in raw_hits:
            if page_requests >= bounded_pages or stage_pages >= stage_page_budget:
                break
            url = _canonical(hit.url)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            stage_unique_hits += 1

            if url in core_urls:
                core_known += 1
                continue

            page_requests += 1
            stage_pages += 1
            base_diagnostic = {
                "stage": stage_index + 1,
                "requested_url": url,
                "search_hit_title": str(hit.title or "")[:500],
                "search_hit_description": str(hit.description or "")[:1000],
                "search_hit_provider": str(hit.provider or ""),
                "search_hit_alone_is_ground_truth": False,
                "automatic_query_activation": False,
            }
            try:
                page: PublicPage = fetch_page(url)
            except Exception as exc:
                verification_attempts.append(
                    {
                        **base_diagnostic,
                        "final_url": None,
                        "status_code": None,
                        "content_type": None,
                        "verifier_status": "FETCH_FAILED",
                        "rejection_reasons": ["PAGE_FETCH_FAILED"],
                        "evidence_flags": {},
                        "error_type": type(exc).__name__,
                        "error": " ".join(str(exc).split())[:500],
                    }
                )
                continue

            diagnostic = {**base_diagnostic, **diagnose_public_page(page)}
            verification_attempts.append(diagnostic)

            proof = _verify_closure_liquidation_page(page)
            if proof is None:
                continue
            verified_pages += 1
            stage_verified += 1

            available_terms = [
                term
                for term in proof["query_gap_terms"]
                if all(term.casefold() not in item.casefold() for item in SCOUT_QUERIES_NO)
                and not _query_contains_term(active_queries, term)
            ]
            if not available_terms:
                no_new_term += 1
                continue

            term = available_terms[0]
            final_url = str(proof["canonical_url"])
            if final_url in core_urls:
                core_known += 1
                continue

            case = _new_gap_case(proof, observed_at=now)
            cases.append(case)
            stage_misses += 1
            metadata.append(
                {
                    "case_id": case.case_id,
                    "canonical_url": final_url,
                    "company": case.ground_truth_company,
                    "query_gap_term": term,
                    "source_page_verified": True,
                    "closure_verified": True,
                    "inventory_liquidation_verified": True,
                    "closure_markers": list(proof["closure_markers"]),
                    "liquidation_markers": list(proof["liquidation_markers"]),
                    "search_hit_alone_is_ground_truth": False,
                    "scout_query_contains_gap_term": False,
                    "waterfall_stage": stage_index + 1,
                }
            )
            break

        search_stages.append(
            {
                "stage": stage_index + 1,
                "query": query,
                "hit_count": len(raw_hits),
                "unique_hit_count": stage_unique_hits,
                "page_request_count": stage_pages,
                "verified_page_count": stage_verified,
                "detected_miss_count": stage_misses,
            }
        )
        if cases:
            break

    if cases:
        stopped_reason = "FIRST_VERIFIED_MISS"
    elif page_requests >= bounded_pages:
        stopped_reason = "PAGE_BUDGET_EXHAUSTED"
    else:
        stopped_reason = "ALL_STAGES_EXHAUSTED"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if cases else "VALID_ZERO",
        "market_code": "NO",
        "scout_query": SCOUT_QUERY_NO,
        "scout_queries": list(SCOUT_QUERIES_NO),
        "waterfall_enabled": True,
        "waterfall_stopped_reason": stopped_reason,
        "max_search_requests": MAX_SEARCH_REQUESTS,
        "search_request_count": search_requests,
        "search_hit_count": total_hits,
        "search_stages": search_stages,
        "page_request_count": page_requests,
        "verification_attempts": verification_attempts,
        "verified_page_count": verified_pages,
        "detected_miss_count": len(cases),
        "core_already_knew_count": core_known,
        "no_new_query_term_count": no_new_term,
        "cases": cases,
        "cases_metadata": metadata,
        "search_hit_alone_is_never_ground_truth": True,
        "source_page_verification_required": True,
        "verification_diagnostics_are_read_only": True,
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _safe_waterfall_report(status: str, **extra: Any) -> dict[str, Any]:
    report = _safe_empty_report(status, **extra)
    report.update(
        {
            "schema_version": SCHEMA_VERSION,
            "waterfall_enabled": True,
            "max_search_requests": MAX_SEARCH_REQUESTS,
            "scout_queries": list(SCOUT_QUERIES_NO),
            "search_stages": [],
            "verification_attempts": [],
            "verification_diagnostics_are_read_only": True,
        }
    )
    return report


def write_automatic_query_gap_miss_scout(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    active_query_config: str | Path = DEFAULT_ACTIVE_QUERY_CONFIG,
    environment: Mapping[str, str] | None = None,
    search_override: SearchCallback | None = None,
    page_fetcher: PageFetcher | None = None,
    observed_at: datetime | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Run the bounded waterfall and merge verified QUERY_GAP cases into memory."""
    env = environment if environment is not None else os.environ
    output = Path(output_dir)
    root = Path(input_root)
    report_path = output / OUTPUT_FILENAME

    cost_block = manual_paid_brave_block_reason(env)
    if cost_block:
        report = _safe_waterfall_report(
            "SKIPPED_COST_GUARD",
            cost_guard_reason=cost_block,
        )
        _write_object(report_path, report)
        _attach_to_brief(output, report)
        return report

    api_key = str(env.get("BRAVE_SEARCH_API_KEY") or env.get("BRAVE_API_KEY") or "").strip()
    if search_override is None and not api_key:
        report = _safe_waterfall_report("SKIPPED_NO_API_KEY")
        _write_object(report_path, report)
        _attach_to_brief(output, report)
        return report

    if search_override is None:
        provider = BraveSearchProvider(
            api_key,
            country="NO",
            freshness="pm",
            extra_snippets=True,
        )

        def search(query: str) -> Sequence[SearchHit]:
            return provider.search(query, count=DEFAULT_SEARCH_RESULTS)
    else:
        search = search_override

    checkpoint = _read_object(output / "multi-market-daily-checkpoint.json")
    active_queries = load_active_learning_queries(active_query_config)
    outcome = discover_query_gap_misses(
        checkpoint,
        active_queries=active_queries,
        search=search,
        fetch_page=page_fetcher or fetch_public_page,
        observed_at=observed_at,
        max_pages=max_pages,
    )
    detected = list(outcome.pop("cases"))

    memory_path = root / MEMORY_RELATIVE_PATH
    existing = load_missed_opportunity_memory(memory_path)
    merged, new_count, repeat_count = _merge_memory(existing, detected)
    save_missed_opportunity_memory(memory_path, merged)

    report = {
        **outcome,
        "status": "SUCCESS" if detected else outcome.get("status", "VALID_ZERO"),
        "new_case_count": new_count,
        "repeat_miss_count_this_run": repeat_count,
        "known_case_count_after": len(merged),
        "detected_cases": [case.to_dict() for case in detected],
        "memory_path": memory_path.as_posix(),
        "max_pages": max(0, min(MAX_PAGES, int(max_pages))),
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_object(report_path, report)
    _attach_to_brief(output, report)
    return report
