"""Orchestration from generated queries to classified Discovery results."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Iterable

from opportunity_engine.discovery.classifier import classify_candidate, to_canonical_opportunity
from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult
from opportunity_engine.discovery.result_filter import evaluate_candidate
from opportunity_engine.discovery.search_provider import SearchProvider


def run_live_discovery(
    queries: Iterable[str],
    provider: SearchProvider,
    *,
    discovered_at: str | None = None,
    results_per_query: int = 10,
    query_delay_seconds: float = 0.0,
    apply_result_filter: bool = False,
) -> dict:
    """Search, deduplicate, optionally pre-filter, classify, and hand off confirmed sales only."""
    if query_delay_seconds < 0:
        raise ValueError("query_delay_seconds must not be negative")

    timestamp = discovered_at or datetime.now(timezone.utc).isoformat()
    clean_queries = list(dict.fromkeys(" ".join(q.split()) for q in queries if " ".join(q.split())))

    candidates: list[DiscoveryCandidate] = []
    filtered_out: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    errors: list[dict[str, str]] = []
    hits_received = 0

    for index, query in enumerate(clean_queries):
        if index and query_delay_seconds:
            time.sleep(query_delay_seconds)
        try:
            hits = provider.search(query, count=results_per_query)
        except Exception as exc:  # provider failures must not fabricate results
            errors.append({"query": query, "error": str(exc)})
            continue
        for hit in hits:
            hits_received += 1
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            candidate = DiscoveryCandidate(
                title=hit.title,
                url=hit.url,
                source=hit.provider or provider.name,
                discovered_at=timestamp,
                text=hit.description,
            )
            if apply_result_filter:
                decision = evaluate_candidate(candidate)
                if not decision.keep:
                    filtered_out.append({
                        "title": candidate.title,
                        "url": candidate.url,
                        "reason": decision.reason,
                        "score": decision.score,
                    })
                    continue
            candidates.append(candidate)

    classified: list[DiscoveryResult] = [classify_candidate(candidate) for candidate in candidates]
    canonical = [opportunity for result in classified if (opportunity := to_canonical_opportunity(result))]

    return {
        "schema_version": "discovery-1.1",
        "filter_version": "discovery-1.5" if apply_result_filter else None,
        "result_filter_applied": apply_result_filter,
        "provider": provider.name,
        "discovered_at": timestamp,
        "queries_submitted": len(clean_queries),
        "hits_received": hits_received,
        "candidates_received": len(candidates),
        "duplicates_removed": hits_received - len(seen_urls),
        "filtered_out_count": len(filtered_out),
        "filtered_out_results": filtered_out,
        "classified_results": [result.to_dict() for result in classified],
        "confirmed_sales": sum(result.status == "SALE_CONFIRMED" for result in classified),
        "follow_up_leads": sum(result.status == "CONTACT_REQUIRED" for result in classified),
        "rejected_results": sum(result.status == "REJECTED" for result in classified),
        "canonical_opportunities": canonical,
        "errors": errors,
        "automatic_purchase_decision": False,
        "status": "PASS" if not errors else "PARTIAL",
    }
