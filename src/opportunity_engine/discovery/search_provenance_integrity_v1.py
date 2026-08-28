"""Preserve truthful search/recovery provenance without changing search behavior.

This compatibility layer is read-only with respect to discovery policy. It adds
no searches, page fetches, providers, sources, markets, runtimes, agents, or
qualification evidence. It only preserves evidence already available while the
existing unified Exa runtime executes:

* remembers the original Exa query that first discovered each search-result URL;
* restores that query onto verified pages before Multi-Hop inherits it;
* marks freshly reverified route-memory pages as PROVEN_ROUTE_RECOVERY instead
  of allowing downstream reports to imply a direct current Exa discovery;
* scopes transient provenance memory by market + URL so the same cross-border
  page can never leak query/recovery attribution between fixed markets;
* separates current-search Exact-Lots from freshly reverified recovery lots in
  the source report and unified six-market search runtime;
* preserves provenance in canonical opportunity metadata;
* keeps manual SKIPPED_COST_GUARD truth visible in the six-market ledger;
* prevents Commercial Anchor learning from treating recovery memory as a direct
  query/route success.

The underlying Exact-Lot evidence gate remains unchanged: every accepted page
must still be freshly fetched and prove the existing strict clothing evidence.
"""
from __future__ import annotations

from typing import Any, Mapping

from opportunity_engine.discovery import clothing_inventory_search
from opportunity_engine.discovery import commercial_anchor_outcome_learning
from opportunity_engine.discovery import exa_search
from opportunity_engine.discovery import provider_unique_page_verification as verifier
from opportunity_engine.discovery import unified_opportunity_adapter
from opportunity_engine.discovery import unified_search_runtime_cli_hook as search_runtime
from opportunity_engine.discovery import unified_search_truth_reconciliation_cli_hook as reconciliation
from opportunity_engine.discovery import unified_six_market_runtime_cli_hook as six_market_runtime
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


VERSION = "SEARCH_PROVENANCE_INTEGRITY_V1"
SEARCH_REQUESTS_ADDED = 0
PAGE_FETCHES_ADDED = 0
_INSTALLED = False

# Transient same-process provenance is market-scoped. A cross-border wholesale
# URL may legitimately appear in several market searches, and one market must
# never inherit the query or recovery state observed in another market.
_QUERY_BY_MARKET_URL: dict[tuple[str, str], str] = {}
_RECOVERY_MARKET_URLS: set[tuple[str, str]] = set()

_ORIGINAL_EXA_SEARCH = exa_search.ExaSearchProvider.search
_ORIGINAL_VERIFY = verifier.verify_provider_unique_pages
_ORIGINAL_TOP5_GATE = clothing_inventory_search.apply_post_verification_top5_hard_gate
_ORIGINAL_METADATA = unified_opportunity_adapter._metadata
_ORIGINAL_SIX_MARKET_BUILD = six_market_runtime.build_unified_six_market_pipeline
_ORIGINAL_CLOTHING_RUNTIME = search_runtime._clothing_runtime


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _market(value: object) -> str:
    code = _compact(value).upper()
    return code if code in search_runtime.SIX_MARKETS else ""


def _query_market(query: str) -> str:
    matches = [market for market in search_runtime.SIX_MARKETS if _market_anchored(query, market)]
    return matches[0] if len(matches) == 1 else ""


def _candidate_url(candidate: Mapping[str, Any]) -> str:
    urls = candidate.get("canonical_urls") or candidate.get("source_urls") or []
    if isinstance(urls, list):
        for value in urls:
            url = _compact(value)
            if url:
                return url
    return ""


def _query_preserving_search(self, query: str, *, count: int = 10):  # type: ignore[no-untyped-def]
    hits = _ORIGINAL_EXA_SEARCH(self, query, count=count)
    if classify_project_domain(text=query) == CLOTHING_INVENTORY:
        clean_query = _compact(query)
        market = _query_market(clean_query)
        if market:
            for hit in hits:
                url = _compact(getattr(hit, "url", ""))
                if url:
                    # First discovery wins within one market. A later anchor in
                    # that market cannot steal credit, while another market can
                    # independently discover the same cross-border URL.
                    _QUERY_BY_MARKET_URL.setdefault((market, url), clean_query)
    return hits


def _verify_with_query_and_recovery_provenance(*args, **kwargs):  # type: ignore[no-untyped-def]
    report = _ORIGINAL_VERIFY(*args, **kwargs)
    pages = report.get("verified_pages") or []
    for raw in pages:
        if not isinstance(raw, dict):
            continue
        market = _market(raw.get("market_code"))
        source_url = _compact(raw.get("url"))
        final_url = _compact(raw.get("final_url") or source_url)
        provider = _compact(raw.get("provider")).casefold()
        if provider == verifier.PROVEN_ROUTE_RECOVERY_PROVIDER:
            if market and final_url:
                _RECOVERY_MARKET_URLS.add((market, final_url))
            if market and source_url:
                _RECOVERY_MARKET_URLS.add((market, source_url))
            raw["route_memory_search_context"] = _compact(raw.get("query")) or None
            # Recovery is fresh page verification of remembered navigation. It
            # must not be credited to whichever live query happened to run now.
            raw["query"] = ""
            raw["query_provenance_source"] = "ROUTE_MEMORY_REVERIFICATION"
            raw["retrieval_provenance"] = "PROVEN_ROUTE_RECOVERY"
            raw["route_memory_is_qualification_evidence"] = False
            raw["fresh_page_verification_required"] = True
            continue

        original_query = _QUERY_BY_MARKET_URL.get((market, source_url)) if market else None
        if original_query:
            raw["query"] = original_query
            raw["query_provenance_source"] = "ORIGINAL_EXA_RESULT_QUERY"
            raw["query_provenance_preserved"] = True
        raw["retrieval_provenance"] = "DIRECT_SEARCH_RESULT"
    report["query_provenance_preserved"] = True
    report["provenance_scope"] = "MARKET_PLUS_URL"
    report["recovery_query_credit_blocked"] = True
    report["search_requests_added_by_provenance_integrity"] = SEARCH_REQUESTS_ADDED
    report["page_fetches_added_by_provenance_integrity"] = PAGE_FETCHES_ADDED
    return report


def _provenance_from_candidate(candidate: Mapping[str, Any], *, market: str) -> str:
    url = _candidate_url(candidate)
    if market and url and (market, url) in _RECOVERY_MARKET_URLS:
        return "PROVEN_ROUTE_RECOVERY"
    reason = _compact(candidate.get("reason")).upper()
    if "MULTI_HOP" in reason:
        return "MULTI_HOP"
    if "DIRECT_SEARCH_RESULT" in reason:
        return "DIRECT_SEARCH_RESULT"
    return "STRICT_EXACT_LOT"


def _annotate_candidate(candidate: dict[str, Any], provenance: str) -> None:
    candidate["search_provider"] = "EXA"
    candidate["retrieval_provenance"] = provenance
    candidate["exact_lot_origin"] = provenance
    candidate["route_memory_reverified"] = provenance == "PROVEN_ROUTE_RECOVERY"
    candidate["query_provenance_preserved"] = provenance != "PROVEN_ROUTE_RECOVERY"
    candidate["provenance_scope"] = "MARKET_PLUS_URL"
    for verification in candidate.get("verification") or []:
        if isinstance(verification, dict):
            verification["search_provider"] = "EXA"
            verification["retrieval_provenance"] = provenance
            verification["route_memory_reverified"] = provenance == "PROVEN_ROUTE_RECOVERY"
            verification["provenance_scope"] = "MARKET_PLUS_URL"


def _top5_with_truthful_provenance(result: Mapping[str, Any]) -> dict[str, Any]:
    gated = _ORIGINAL_TOP5_GATE(result)
    report = gated.get("search_run_report")
    market = _market(report.get("market_code")) if isinstance(report, Mapping) else ""
    candidates = gated.get("all_discovered_candidates") or []
    provenance_counts: dict[str, int] = {}
    by_url: dict[str, str] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        provenance = _provenance_from_candidate(candidate, market=market)
        provenance_counts[provenance] = provenance_counts.get(provenance, 0) + 1
        url = _candidate_url(candidate)
        if url:
            by_url[url] = provenance
        _annotate_candidate(candidate, provenance)

    # Preserve the hard gate's exact Top5 selection and ordering. Additive
    # provenance must never promote, demote, reorder, or synthesize a Top5 row.
    for candidate in gated.get("discovery_top5") or []:
        if not isinstance(candidate, dict):
            continue
        provenance = by_url.get(_candidate_url(candidate)) or _provenance_from_candidate(
            candidate, market=market
        )
        _annotate_candidate(candidate, provenance)

    if isinstance(report, dict):
        recovery = int(provenance_counts.get("PROVEN_ROUTE_RECOVERY", 0))
        current = sum(
            count
            for key, count in provenance_counts.items()
            if key != "PROVEN_ROUTE_RECOVERY"
        )
        report["current_exa_discovery_strict_exact_lot_count"] = current
        report["freshly_reverified_recovery_exact_lot_count"] = recovery
        report["strict_exact_lot_count_includes_reverified_recovery"] = recovery > 0
        report["exact_lot_provenance_counts"] = dict(sorted(provenance_counts.items()))
        report["search_provider"] = "EXA"
        report["query_provenance_preserved"] = True
        report["provenance_scope"] = "MARKET_PLUS_URL"
        report["recovery_query_credit_blocked"] = True
        report["search_requests_added_by_provenance_integrity"] = SEARCH_REQUESTS_ADDED
        report["page_fetches_added_by_provenance_integrity"] = PAGE_FETCHES_ADDED
    return gated


def _metadata_with_search_provenance(candidate: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _ORIGINAL_METADATA(candidate)
    metadata.update(
        {
            "search_provider": candidate.get("search_provider"),
            "retrieval_provenance": candidate.get("retrieval_provenance"),
            "exact_lot_origin": candidate.get("exact_lot_origin"),
            "route_memory_reverified": candidate.get("route_memory_reverified") is True,
            "query_provenance_preserved": candidate.get("query_provenance_preserved") is True,
            "provenance_scope": candidate.get("provenance_scope"),
        }
    )
    return metadata


def _six_market_build_with_cost_guard_truth(*args, **kwargs):  # type: ignore[no-untyped-def]
    ledger = _ORIGINAL_SIX_MARKET_BUILD(*args, **kwargs)
    for market in ledger.get("markets") or []:
        if not isinstance(market, dict) or _compact(market.get("market_code")).upper() not in {
            "NO",
            "SE",
            "DE",
        }:
            continue
        stages = {
            _compact(stage.get("stage")): stage
            for stage in market.get("stages") or []
            if isinstance(stage, dict)
        }
        discovery = stages.get("DISCOVERY")
        decision = stages.get("OPPORTUNITY_DECISION")
        if not isinstance(discovery, dict):
            continue
        counts = discovery.get("source_execution_counts") or {}
        if not isinstance(counts, Mapping):
            continue
        skipped = int(counts.get("SKIPPED_COST_GUARD") or 0)
        discovery["cost_guard_skipped_source_count"] = skipped
        if (
            skipped > 0
            and _compact(discovery.get("status")).upper() == "UNKNOWN"
            and int(counts.get("SUCCESS") or 0) == 0
            and int(counts.get("VALID_ZERO_RESULT") or 0) == 0
            and int(counts.get("FAILURE") or 0) == 0
        ):
            discovery["status"] = "SKIPPED_COST_GUARD"
            if isinstance(decision, dict) and _compact(decision.get("status")).upper() == "NOT_READY":
                decision["status"] = "NOT_RUN_COST_GUARD"
    ledger["cost_guard_truth_preserved"] = True
    return ledger


def _clothing_runtime_with_provenance(input_root):  # type: ignore[no-untyped-def]
    runtime = _ORIGINAL_CLOTHING_RUNTIME(input_root)
    for market, row in (runtime.get("markets") or {}).items():
        if not isinstance(row, dict):
            continue
        source_dir = input_root / f"{str(market).casefold()}-exa-exact-lot"
        report = search_runtime._load_json(source_dir / "search-run-report.json")
        total = int(report.get("strict_exact_lot_count") or row.get("strict_exact_lot_count") or 0)
        recovery = int(report.get("freshly_reverified_recovery_exact_lot_count") or 0)
        current = int(
            report.get("current_exa_discovery_strict_exact_lot_count")
            if report.get("current_exa_discovery_strict_exact_lot_count") is not None
            else max(0, total - recovery)
        )
        row["strict_exact_lot_count"] = total
        row["current_exa_discovery_strict_exact_lot_count"] = current
        row["freshly_reverified_recovery_exact_lot_count"] = recovery
        row["strict_exact_lot_count_includes_reverified_recovery"] = recovery > 0
        row["provenance_scope"] = "MARKET_PLUS_URL"
        row["provenance_integrity_version"] = VERSION
    runtime["exact_lot_provenance_separated"] = True
    runtime["provenance_scope"] = "MARKET_PLUS_URL"
    return runtime


def _route_index_with_recovery_truth(resolution: Mapping[str, Any]) -> dict[str, str]:
    routes: dict[str, str] = {}
    verification = resolution.get("verification") or {}
    if isinstance(verification, Mapping):
        for row in verification.get("verified_pages") or []:
            if not isinstance(row, Mapping):
                continue
            url = _compact(row.get("final_url") or row.get("url"))
            if not url:
                continue
            provenance = _compact(row.get("retrieval_provenance")).upper()
            provider = _compact(row.get("provider")).casefold()
            routes[url] = (
                "PROVEN_ROUTE_RECOVERY"
                if provenance == "PROVEN_ROUTE_RECOVERY"
                or provider == verifier.PROVEN_ROUTE_RECOVERY_PROVIDER
                else "DIRECT_SEARCH_RESULT"
            )
    multihop = resolution.get("multihop") or {}
    if isinstance(multihop, Mapping):
        for row in multihop.get("exact_lots") or []:
            if not isinstance(row, Mapping):
                continue
            url = _compact(row.get("final_url") or row.get("url"))
            if url:
                routes[url] = "MULTI_HOP"
    return routes


def _render_search_runtime_with_provenance(ledger: Mapping[str, Any]) -> str:
    runtime = ledger.get("search_runtime") or {}
    clothing = runtime.get(CLOTHING_INVENTORY) or {} if isinstance(runtime, Mapping) else {}
    fabric = runtime.get(FABRIC_PROCUREMENT) or {} if isinstance(runtime, Mapping) else {}
    lines = ["", "حقيقة البحث الموحد"]
    clothing_markets = clothing.get("markets") or {} if isinstance(clothing, Mapping) else {}
    for code in ("NO", "SE", "DE", "FR", "IT", "NL"):
        row = clothing_markets.get(code) or {} if isinstance(clothing_markets, Mapping) else {}
        lines.append(
            f"{code} ملابس: {row.get('status', 'NOT_RUN')} | "
            f"hits={row.get('hits_received', 0)} | "
            f"Exact-Lots={row.get('strict_exact_lot_count', 0)} | "
            f"current={row.get('current_exa_discovery_strict_exact_lot_count', 0)} | "
            f"reverified-recovery={row.get('freshly_reverified_recovery_exact_lot_count', 0)}"
        )
    fabric_markets = fabric.get("markets") or {} if isinstance(fabric, Mapping) else {}
    for code in ("FR", "IT", "NL"):
        row = fabric_markets.get(code) or {} if isinstance(fabric_markets, Mapping) else {}
        lines.append(
            f"{code} أقمشة: {row.get('status', 'NOT_RUN')} | "
            f"hits={row.get('hits_received', 0)} | candidates={row.get('candidate_count', 0)}"
        )
    lines.extend(
        [
            "Exact-Lot الحالي منفصل عن الصفحات المستعادة من الذاكرة والمعاد تحققها.",
            "Provenance مفصول حسب السوق + الرابط لمنع التلوث بين الأسواق.",
            "تطوير البحث: نفس المسار الموحد فقط؛ لا مسارات دول منفصلة.",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def install_search_provenance_integrity_v1() -> bool:
    """Install provenance-only wrappers; no retrieval or qualification policy changes."""
    global _INSTALLED
    if _INSTALLED:
        return False

    exa_search.ExaSearchProvider.search = _query_preserving_search
    verifier.verify_provider_unique_pages = _verify_with_query_and_recovery_provenance
    clothing_inventory_search.apply_post_verification_top5_hard_gate = (
        _top5_with_truthful_provenance
    )
    unified_opportunity_adapter._metadata = _metadata_with_search_provenance
    six_market_runtime.build_unified_six_market_pipeline = (
        _six_market_build_with_cost_guard_truth
    )
    search_runtime._clothing_runtime = _clothing_runtime_with_provenance
    commercial_anchor_outcome_learning._resolution_route_index = (
        _route_index_with_recovery_truth
    )
    reconciliation._render_search_runtime_section = _render_search_runtime_with_provenance

    _INSTALLED = True
    return True
