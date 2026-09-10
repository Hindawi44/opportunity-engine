#!/usr/bin/env python3
"""Run the unified verified Exact-Lot + Multi-Hop route as a checkpoint source.

All six clothing markets stay on the same Search -> Verification -> Multi-Hop ->
Exact-Lot path. Generic recall and bounded commercial-anchor expansion remain
query stages inside the same runtime. Exa is primary; one source-neutral Brave
query is available only when final fresh verified coverage remains weak. Recovery
memory may assist navigation, but it must never make weak fresh search coverage
look sufficient. Commercial anchors are discovery hints only; they are never
qualification evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    CONFIRMED_SALE,
    ITEM_LISTING,
    apply_post_verification_top5_hard_gate,
    write_discovery_artifacts,
)
from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    build_commercial_anchor_queries,
)
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.exa_exact_lot_shadow_hunt import MARKET_EXACT_LOT_QUERIES
from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    EXACT_LOT_CANDIDATE,
)
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.discovery.search_provider_role_policy import (
    BRAVE,
    VERIFIED_EXACT_LOT_FALLBACK,
    require_provider_for_intent,
)
from opportunity_engine.discovery.unified_opportunity_report import write_unified_opportunity_report
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.discovery.source_native_value_normalization import normalize_source_native_values
from opportunity_engine.search_experiment_execution_bridge_v1 import _custom_benchmark, _market_anchored
from opportunity_engine.search_policy_query_challenge_v1 import (
    build_market_query_plan,
)


RESULTS_PER_QUERY = 5
COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD = 3
COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS = 8
COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS_BY_MARKET = {"DE": 6}
FRESH_RECALL_MIN_CURRENT_EXACT_LOTS = 3
FRESH_RECALL_MIN_CURRENT_ROUTE_HOSTS = 2
BRAVE_FALLBACK_MAX_QUERIES_PER_MARKET = 1
BRAVE_FALLBACK_MAX_OUTBOUND_ATTEMPTS_PER_MARKET = 1
BRAVE_FALLBACK_RESULTS_PER_QUERY = 5
BRAVE_FALLBACK_MAX_PAGE_FETCHES = 5
BRAVE_FALLBACK_MAX_ROOT_PARENTS = 2
BRAVE_FALLBACK_MAX_NAVIGATION_FETCHES = 12
EXA_SOURCE_MODE = "EXA_EXACT_LOT_MULTIHOP"
HYBRID_SOURCE_MODE = "EXA_PRIMARY_BRAVE_FALLBACK_MULTIHOP"
EXA_ENGINE_VERSION = "UNIFIED_EXA_EXACT_LOT_MULTIHOP_V1"
HYBRID_ENGINE_VERSION = "UNIFIED_EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK_V1"
DIRECT_STRICT_EVIDENCE_RESCUE = "QUALIFIED_B2B_STRICT_EVIDENCE_V1"
MARKET_CURRENCIES = {
    "NO": "NOK",
    "SE": "SEK",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "NL": "EUR",
}
MARKET_EXACT_LOT_QUERY_PACKS: dict[str, tuple[str, ...]] = {
    "NO": (
        "Norge klær vareparti nettauksjon konkursbo lager pris antall stk",
        "Norge arbeidsklær overskuddsvarer auksjon høyeste bud stk",
    ),
    "SE": (
        "Sverige restparti kläder grossist lager",
        "Sverige överskottslager kläder till salu parti",
        "Sverige kläder varulager auktion parti pris antal plagg",
    ),
    "DE": (
        "Deutschland Restposten Bekleidung Großhandel Lager",
        "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück",
    ),
    "FR": (MARKET_EXACT_LOT_QUERIES["FR"],),
    "IT": (MARKET_EXACT_LOT_QUERIES["IT"],),
    "NL": (MARKET_EXACT_LOT_QUERIES["NL"],),
}

# Generic, source-neutral recall. It runs after a true zero yield and also when
# recovered route memory would otherwise hide weak fresh-search coverage.
MARKET_ZERO_YIELD_RECALL_QUERIES: dict[str, tuple[str, ...]] = {
    "SE": ("Sverige restpartier kläder grossist säljes parti",),
    "FR": ("France déstockage vêtements grossiste stock lot",),
    "IT": ("Italia liquidazione stock abbigliamento ingrosso",),
    "NL": ("Nederland kledingvoorraad restpartij groothandel",),
}

# A single source-neutral, local-language fallback query is available in every
# market. It is spent only after the complete Exa route (primary, eligible
# recall and bounded commercial-anchor expansion) still has weak *fresh*
# verified Exact-Lot coverage. One Brave request per weak market is a hard cap.
MARKET_BRAVE_FALLBACK_QUERIES: dict[str, str] = {
    "NO": "Norge klær vareparti konkursbo restlager selges samlet pris stk",
    "SE": "Sverige kläder restparti konkurslager säljes auktion pris antal",
    "DE": "Deutschland Bekleidung Restposten Insolvenz Lagerverkauf Preis Menge Stück",
    "FR": "France vêtements lot stock liquidation à vendre prix quantité pièces",
    "IT": "Italia abbigliamento lotto stock liquidazione in vendita prezzo quantità pezzi",
    "NL": "Nederland kleding restpartij voorraad liquidatie te koop prijs aantal stuks",
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _exact_lot_identity_key(value: object) -> str:
    """Normalize cosmetic URL variants without collapsing distinct listing queries."""
    raw = _compact(value)
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").casefold().removeprefix("www.")
        if not host:
            return raw
        port = parsed.port
    except ValueError:
        return raw

    scheme = (parsed.scheme or "https").casefold()
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = (parsed.path or "/").rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{scheme}://{netloc}{path}{query}"


def _exact_lot_identity_set(rows: list[Mapping[str, Any]]) -> set[str]:
    identities: set[str] = set()
    for row in rows:
        identity = _exact_lot_identity_key(row.get("final_url") or row.get("url"))
        if identity:
            identities.add(identity)
    return identities


def _is_recovery_exact_lot(row: Mapping[str, Any]) -> bool:
    """Return True only for a freshly reverified route-memory Exact-Lot.

    Search provenance integrity annotates recovery rows before this runner makes
    its adaptive query decision. Provider fallback is retained for compatibility
    with direct verifier tests. Memory remains navigation evidence only.
    """
    return bool(
        _compact(row.get("retrieval_provenance")).upper() == "PROVEN_ROUTE_RECOVERY"
        or _compact(row.get("provider")).casefold() == "proven_route_recovery"
        or row.get("route_memory_reverified") is True
    )


def _fresh_current_exact_lots(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if not _is_recovery_exact_lot(row)]


def _exact_lot_route_hosts(rows: list[Mapping[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for row in rows:
        url = _compact(row.get("final_url") or row.get("url"))
        if not url:
            continue
        try:
            host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        except ValueError:
            host = ""
        if host:
            hosts.add(host)
    return hosts


def _fresh_coverage_snapshot(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    fresh = _fresh_current_exact_lots(rows)
    recovery_count = max(0, len(rows) - len(fresh))
    route_hosts = _exact_lot_route_hosts(fresh)
    return {
        "total_strict_exact_lot_count": len(rows),
        "fresh_current_strict_exact_lot_count": len(fresh),
        "reverified_recovery_strict_exact_lot_count": recovery_count,
        "fresh_current_route_host_count": len(route_hosts),
        "fresh_current_route_hosts": sorted(route_hosts),
    }


def _brave_fallback_reasons(
    snapshot: Mapping[str, Any], *, exa_search_error_count: int = 0
) -> list[str]:
    """Explain the bounded fallback using verified fresh coverage, never raw hits."""
    reasons: list[str] = []
    if int(snapshot.get("fresh_current_strict_exact_lot_count") or 0) < (
        FRESH_RECALL_MIN_CURRENT_EXACT_LOTS
    ):
        reasons.append("FRESH_EXACT_LOT_COUNT_BELOW_THRESHOLD")
    if int(snapshot.get("fresh_current_route_host_count") or 0) < (
        FRESH_RECALL_MIN_CURRENT_ROUTE_HOSTS
    ):
        reasons.append("FRESH_ROUTE_HOST_COUNT_BELOW_THRESHOLD")
    if reasons and exa_search_error_count > 0:
        reasons.append("EXA_SEARCH_ERROR")
    return reasons


def _hit_benchmark_row(hit: object) -> dict[str, Any]:
    url = _compact(getattr(hit, "url", ""))
    try:
        domain = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        domain = ""
    return {
        "title": _compact(getattr(hit, "title", ""))[:1000],
        "url": url,
        "domain": domain,
        "description": _compact(getattr(hit, "description", ""))[:1000],
        "provider": _compact(getattr(hit, "provider", "")),
    }


def _hybrid_provider_benchmark(
    *,
    market: str,
    query: str,
    exa_hits: list[object],
    brave_hits: list[object],
) -> dict[str, Any]:
    """Build the verifier's symmetric input without mixing provider provenance."""
    exa_rows = [_hit_benchmark_row(hit) for hit in exa_hits]
    brave_rows = [_hit_benchmark_row(hit) for hit in brave_hits]
    exa_urls = {row["url"] for row in exa_rows if row["url"]}
    brave_urls = {row["url"] for row in brave_rows if row["url"]}
    exa_domains = {row["domain"] for row in exa_rows if row["domain"]}
    brave_domains = {row["domain"] for row in brave_rows if row["domain"]}
    return {
        "schema_version": "search-experiment-benchmark-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
        "shadow_only": True,
        "provider_mode": "exa-primary-brave-fallback",
        "query_mode": "exact_lot",
        "query_set": {market: query},
        "project_domain": CLOTHING_INVENTORY,
        "project_domain_gate_enforced": True,
        "markets": [market],
        "results_per_query": BRAVE_FALLBACK_RESULTS_PER_QUERY,
        "exa_request_count": 0,
        "brave_request_count": 1,
        "market_results": [
            {
                "market_code": market,
                "query": query,
                "exa": {
                    "result_count": len(exa_rows),
                    "unique_domain_count": len(exa_domains),
                    "results": exa_rows,
                },
                "brave": {
                    "result_count": len(brave_rows),
                    "unique_domain_count": len(brave_domains),
                    "results": brave_rows,
                },
                "comparison": {
                    "shared_url_count": len(exa_urls & brave_urls),
                    "exa_unique_url_count": len(exa_urls - brave_urls),
                    "brave_unique_url_count": len(brave_urls - exa_urls),
                    "shared_domain_count": len(exa_domains & brave_domains),
                    "exa_unique_domain_count": len(exa_domains - brave_domains),
                    "brave_unique_domain_count": len(brave_domains - exa_domains),
                },
            }
        ],
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _merge_exact_lots(
    primary: list[Mapping[str, Any]], fallback: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Merge only already-verified rows; Exa/current rows win identity ties."""
    merged: list[dict[str, Any]] = []
    indexes: dict[str, int] = {}
    for raw in [*primary, *fallback]:
        row = dict(raw)
        identity = _exact_lot_identity_key(row.get("final_url") or row.get("url"))
        if not identity:
            continue
        existing_index = indexes.get(identity)
        if existing_index is None:
            indexes[identity] = len(merged)
            merged.append(row)
            continue
        existing = merged[existing_index]
        if _is_recovery_exact_lot(existing) and not _is_recovery_exact_lot(row):
            merged[existing_index] = row
    return merged


def _fallback_failure_status(error: object) -> str:
    folded = _compact(error).upper()
    if any(
        marker in folded
        for marker in (
            "PAID_BRAVE_BLOCKED",
            "BRAVE_MANUAL_INCREMENTAL_BUDGET",
            "COST_GUARD",
        )
    ):
        return "SKIPPED_COST_GUARD"
    if "HTTP 402" in folded or "USAGE LIMIT" in folded:
        return "SKIPPED_PROVIDER_LIMIT"
    return "FAILURE"


def _live_page_validation_summary(
    verification: Mapping[str, Any],
    multihop: Mapping[str, Any],
    *,
    fallback_verification: Mapping[str, Any] | None = None,
    fallback_multihop: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    verification_rows = [verification]
    multihop_rows = [multihop]
    if fallback_verification:
        verification_rows.append(fallback_verification)
    if fallback_multihop:
        multihop_rows.append(fallback_multihop)
    direct_attempted = sum(
        int(
            row.get("total_page_fetches_attempted")
            or row.get("page_fetches_attempted")
            or 0
        )
        for row in verification_rows
    )
    direct_succeeded = sum(
        int(
            row.get("total_page_fetches_succeeded")
            or row.get("page_fetches_succeeded")
            or 0
        )
        for row in verification_rows
    )
    navigation_attempted = sum(
        int(row.get("navigation_page_fetches_attempted") or 0)
        for row in multihop_rows
    )
    navigation_succeeded = sum(
        int(row.get("navigation_page_fetches_succeeded") or 0)
        for row in multihop_rows
    )
    return {
        "required_before_exact_lot_counting": True,
        "search_snippets_are_qualification_evidence": False,
        "direct_page_fetches_attempted": direct_attempted,
        "direct_page_fetches_succeeded": direct_succeeded,
        "navigation_page_fetches_attempted": navigation_attempted,
        "navigation_page_fetches_succeeded": navigation_succeeded,
        "fetch_failed_page_count": sum(
            int(row.get("fetch_failed_count") or 0) for row in verification_rows
        ),
        "unproven_page_count": sum(
            int(row.get("unproven_page_count") or 0) for row in verification_rows
        ),
    }


def _recovery_masks_fresh_coverage(snapshot: Mapping[str, Any]) -> bool:
    """Recovery must not be allowed to satisfy the fresh-search stopping rule."""
    recovery = int(snapshot.get("reverified_recovery_strict_exact_lot_count") or 0)
    fresh = int(snapshot.get("fresh_current_strict_exact_lot_count") or 0)
    routes = int(snapshot.get("fresh_current_route_host_count") or 0)
    return bool(
        recovery > 0
        and (
            fresh < FRESH_RECALL_MIN_CURRENT_EXACT_LOTS
            or routes < FRESH_RECALL_MIN_CURRENT_ROUTE_HOSTS
        )
    )


def _commercial_anchor_outcome_evidence(
    *,
    market: str,
    query_rows: list[Mapping[str, Any]],
    pre_anchor_exact_lots: list[Mapping[str, Any]],
    final_exact_lots: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Attribute only newly added strict Exact-Lots to the anchor query that found them.

    The outcome is evidence for later review-only learning. Anchor identity never
    contributes to qualification. If query provenance is missing, the new lot is
    left unattributed instead of granting credit to a brand/company by inference.
    Cosmetic URL variants must not manufacture a false post-anchor addition.
    """
    pre_identities = _exact_lot_identity_set(pre_anchor_exact_lots)
    final_by_identity: dict[str, Mapping[str, Any]] = {}
    for row in final_exact_lots:
        url = _compact(row.get("final_url") or row.get("url"))
        identity = _exact_lot_identity_key(url)
        if identity:
            final_by_identity[identity] = row

    added_identities = set(final_by_identity) - pre_identities
    outcomes: list[dict[str, Any]] = []
    attributed_identities: set[str] = set()

    for raw_query in query_rows:
        if _compact(raw_query.get("query_stage")) != "COMMERCIAL_ANCHOR":
            continue
        query = _compact(raw_query.get("query"))
        anchor = raw_query.get("commercial_anchor") or {}
        if not isinstance(anchor, Mapping):
            anchor = {}
        matched_identities = sorted(
            identity
            for identity in added_identities
            if _compact(final_by_identity[identity].get("query")) == query
        )
        matched_urls = sorted(
            _compact(
                final_by_identity[identity].get("final_url")
                or final_by_identity[identity].get("url")
            )
            for identity in matched_identities
        )
        attributed_identities.update(matched_identities)
        outcomes.append(
            {
                "market_code": market,
                "project_domain": CLOTHING_INVENTORY,
                "provider": "exa",
                "anchor_type": _compact(anchor.get("type")),
                "anchor_value": _compact(anchor.get("value")),
                "anchor_origin": _compact(anchor.get("origin")),
                "query": query,
                "outcome": (
                    "STRICT_EXACT_LOT_SUCCESS"
                    if matched_urls
                    else "NO_NEW_STRICT_EXACT_LOT"
                ),
                "strict_exact_lot_added_count": len(matched_urls),
                "strict_exact_lot_urls": matched_urls,
                "anchor_is_qualification_evidence": False,
                "learning_evidence_only": True,
                "automatic_query_activation": False,
                "automatic_source_promotion": False,
                "production_query_mutation": False,
                "production_mutation": False,
            }
        )

    unattributed_identities = sorted(added_identities - attributed_identities)
    unattributed_urls = sorted(
        _compact(
            final_by_identity[identity].get("final_url")
            or final_by_identity[identity].get("url")
        )
        for identity in unattributed_identities
    )
    return {
        "schema_version": "commercial-anchor-outcome-evidence-1.0",
        "status": "SUCCESS" if outcomes else "VALID_ZERO",
        "market_code": market,
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "outcome_count": len(outcomes),
        "successful_outcome_count": sum(
            row["outcome"] == "STRICT_EXACT_LOT_SUCCESS" for row in outcomes
        ),
        "pre_anchor_strict_exact_lot_count": len(pre_identities),
        "post_anchor_strict_exact_lot_count": len(final_by_identity),
        "added_strict_exact_lot_count": len(added_identities),
        "attributed_added_strict_exact_lot_count": len(attributed_identities),
        "unattributed_added_strict_exact_lot_count": len(unattributed_identities),
        "unattributed_added_strict_exact_lot_urls": unattributed_urls,
        "attribution_complete": not unattributed_identities,
        "outcomes": outcomes,
        "anchor_is_qualification_evidence": False,
        "learning_evidence_only": True,
        "automatic_query_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }


def _commercial_anchor_min_unique_discovery_hits(market: str) -> int:
    """Return the narrow per-market anchor gate without changing global defaults.

    Germany gets a lower gate only because a live, evidence-backed wholesaler
    anchor (Salzmann Restwaren) has already recovered strict Exact-Lots when the
    primary discovery route was thin. All other markets retain the global gate.
    """
    return COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS_BY_MARKET.get(
        market.upper(), COMMERCIAL_ANCHOR_MIN_UNIQUE_DISCOVERY_HITS
    )


def _title_from_url(url: str) -> str:
    path = unquote(urlsplit(url).path or "").strip("/")
    token = path.rsplit("/", 1)[-1] if path else ""
    token = token.replace("_", " ").replace("-", " ")
    title = _compact(token)
    if title and not title.isdigit():
        return title[:500]
    if title:
        return f"Clothing Exact-Lot {title}"
    return "Verified clothing Exact-Lot"


def _subject_domain(title: str, url: str) -> str:
    path_words = (
        unquote(urlsplit(url).path or "")
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
    )
    return classify_project_domain(text=_compact(f"{title} {path_words}"))


def _strict_exact_evidence(*, row: Mapping[str, Any], require_subject_evidence: bool) -> bool:
    evidence = row.get("evidence") or {}
    if not isinstance(evidence, Mapping):
        return False
    url = _compact(row.get("final_url") or row.get("url"))
    title = _compact(row.get("title")) or _title_from_url(url)
    subject_ok = evidence.get("page_subject_domain") == CLOTHING_INVENTORY
    if not require_subject_evidence:
        subject_ok = _subject_domain(title, url) == CLOTHING_INVENTORY
    return bool(
        url
        and evidence.get("project_domain") == CLOTHING_INVENTORY
        and subject_ok
        and evidence.get("item_specific_url_evidence") is True
        and evidence.get("inventory_evidence") is True
        and evidence.get("direct_sale_evidence") is True
        and evidence.get("price_evidence") is True
        and evidence.get("quantity_evidence") is True
    )


def _direct_row_is_rescuable_strict_exact(raw: Mapping[str, Any]) -> bool:
    """Rescue only a qualified B2B direct page whose strict Exact-Lot proof is complete.

    This does not treat ACTIVE_STOCK_SIGNAL generally as an Exact-Lot. The narrow
    rescue exists for the verifier path that proves B2B sale evidence after the
    base classifier has already assigned ACTIVE_STOCK_SIGNAL. Brand or anchor
    presence is irrelevant and never qualification evidence.
    """
    evidence = raw.get("evidence") or {}
    return bool(
        raw.get("classification") == ACTIVE_STOCK_SIGNAL
        and isinstance(evidence, Mapping)
        and evidence.get("qualified_b2b_sale_evidence") is True
        and _strict_exact_evidence(row=raw, require_subject_evidence=False)
    )


def _exact_lot_rows(
    verification: Mapping[str, Any], multihop: Mapping[str, Any]
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    accepted_by_identity: dict[str, int] = {}

    def accept_preferred(row: dict[str, Any], identity_key: str) -> None:
        existing_index = accepted_by_identity.get(identity_key)
        if existing_index is None:
            accepted_by_identity[identity_key] = len(accepted)
            accepted.append(row)
            return

        existing = accepted[existing_index]
        if _is_recovery_exact_lot(existing) and not _is_recovery_exact_lot(row):
            accepted[existing_index] = row

    for raw in verification.get("verified_pages") or []:
        if not isinstance(raw, Mapping):
            continue
        classification = raw.get("classification")
        rescued = _direct_row_is_rescuable_strict_exact(raw)
        if classification != EXACT_LOT_CANDIDATE and not rescued:
            continue
        if not _strict_exact_evidence(row=raw, require_subject_evidence=False):
            continue
        row = dict(raw)
        url = _compact(row.get("final_url") or row.get("url"))
        identity_key = _exact_lot_identity_key(url)
        if not url or not identity_key:
            continue
        row["url"] = url
        row["final_url"] = url
        row["exact_lot_origin"] = "DIRECT_SEARCH_RESULT"
        if rescued:
            row["direct_strict_evidence_rescue"] = DIRECT_STRICT_EVIDENCE_RESCUE
        accept_preferred(row, identity_key)

    for raw in multihop.get("exact_lots") or []:
        if not isinstance(raw, Mapping):
            continue
        if not _strict_exact_evidence(row=raw, require_subject_evidence=True):
            continue
        row = dict(raw)
        url = _compact(row.get("final_url") or row.get("url"))
        identity_key = _exact_lot_identity_key(url)
        if not url or not identity_key:
            continue
        row["url"] = url
        row["final_url"] = url
        row["exact_lot_origin"] = "MULTI_HOP"
        accept_preferred(row, identity_key)

    return accepted


def _candidate_from_exact_lot(row: Mapping[str, Any], *, market: str) -> dict[str, Any]:
    url = _compact(row.get("final_url") or row.get("url"))
    title = _compact(row.get("title")) or _title_from_url(url)
    origin = _compact(row.get("exact_lot_origin")) or "STRICT_EXACT_LOT"
    row_provider = _compact(row.get("provider")).casefold()
    search_provider = "BRAVE" if "brave" in row_provider else "EXA"
    provider_label = "Brave" if search_provider == "BRAVE" else "Exa"
    evidence = row.get("evidence") or {}
    resalg_listing = evidence.get("resalg_listing") or {}
    if not isinstance(resalg_listing, Mapping):
        resalg_listing = {}
    resalg_current_bid = resalg_listing.get("current_bid") or {}
    if not isinstance(resalg_current_bid, Mapping):
        resalg_current_bid = {}
    resalg_lot_container = resalg_listing.get("lot_container_quantity") or {}
    if not isinstance(resalg_lot_container, Mapping):
        resalg_lot_container = {}
    price_detected = evidence.get("price_evidence") is True
    quantity_detected = evidence.get("quantity_evidence") is True
    raw_price_candidates = evidence.get("source_native_price_candidates") or []
    raw_price_basis_candidates = evidence.get("source_native_price_basis_candidates") or []
    raw_quantity_candidates = evidence.get("source_native_quantity_candidates") or []
    price_candidates = (
        [_compact(value) for value in raw_price_candidates if _compact(value)][:12]
        if isinstance(raw_price_candidates, (list, tuple))
        else []
    )
    quantity_candidates = (
        [_compact(value) for value in raw_quantity_candidates if _compact(value)][:12]
        if isinstance(raw_quantity_candidates, (list, tuple))
        else []
    )
    price_basis_candidates = (
        [_compact(value) for value in raw_price_basis_candidates if _compact(value)][:12]
        if isinstance(raw_price_basis_candidates, (list, tuple))
        else []
    )
    value_capture_version = _compact(evidence.get("source_native_value_capture_version"))
    commercial_terms_capture_version = _compact(
        evidence.get("source_native_commercial_terms_capture_version")
    )
    raw_condition_candidates = evidence.get("source_native_condition_candidates") or []
    raw_seller_identity_candidates = evidence.get("source_native_seller_identity_candidates") or []
    raw_fulfilment_candidates = evidence.get("source_native_fulfilment_candidates") or []
    condition_candidates = (
        [_compact(value) for value in raw_condition_candidates if _compact(value)][:8]
        if isinstance(raw_condition_candidates, (list, tuple))
        else []
    )
    seller_identity_candidates = (
        [_compact(value) for value in raw_seller_identity_candidates if _compact(value)][:8]
        if isinstance(raw_seller_identity_candidates, (list, tuple))
        else []
    )
    fulfilment_candidates = (
        [_compact(value) for value in raw_fulfilment_candidates if _compact(value)][:8]
        if isinstance(raw_fulfilment_candidates, (list, tuple))
        else []
    )
    normalization = normalize_source_native_values(
        market=market,
        url=url,
        price_candidates=price_candidates,
        quantity_candidates=quantity_candidates,
        price_basis_candidates=price_basis_candidates,
    )
    values_normalized = normalization.get("status") == "NORMALIZED"
    bounded_context = (
        "Strict Exact-Lot evidence: CLOTHING_INVENTORY subject, item-specific URL, inventory, "
        "direct sale, and source-native numeric price and quantity patterns were verified on the "
        "exact public page. The single unambiguous source price/quantity pair and explicit "
        "total-or-per-item basis were normalized without currency conversion, tax, customs or "
        "logistics calculation."
        if values_normalized
        else
        "Strict Exact-Lot evidence: CLOTHING_INVENTORY subject, item-specific URL, inventory, "
        "direct sale, and source-native numeric price and quantity patterns were verified on the "
        "exact public page. Source values or the total-versus-per-item price basis remain "
        "ambiguous or unsupported for normalization."
    )
    missing_information = [
        "condition",
        "seller or company identity",
        "pickup or shipping terms",
    ]
    if normalization.get("status") == "AMBIGUOUS_PRICE_BASIS":
        missing_information.insert(
            0, "explicit source price basis (total lot price versus per-item price)"
        )
    elif not values_normalized:
        missing_information[:0] = [
            "normalized source-native price value for financial analysis",
            "normalized source-native quantity value for financial analysis",
        ]
    confirmed_information = [
        "clothing domain",
        "item-specific page",
        "inventory evidence",
        "direct-sale evidence",
        "source-native numeric price evidence" if price_detected else "price evidence",
        "source-native numeric quantity evidence" if quantity_detected else "quantity evidence",
    ]
    if values_normalized:
        confirmed_information.append("normalized source-native price and quantity values")
    if resalg_current_bid:
        confirmed_information.append("ReSalg current bid bound to listing Produkt-ID")
    if resalg_listing.get("ends_at"):
        confirmed_information.append("ReSalg auction deadline bound to listing Produkt-ID")
    return {
        "title": title,
        "scenario": "LARGE_LOT_SALE",
        "opportunity_state": CONFIRMED_SALE,
        "reason": f"{provider_label} {origin} passed the strict clothing Exact-Lot gate.",
        "page_role": ITEM_LISTING,
        "source_urls": [url],
        "canonical_urls": [url],
        "found_by_queries": [_compact(row.get("query"))] if _compact(row.get("query")) else [],
        "source_providers": [search_provider],
        "search_provider": search_provider,
        "evidence_signals": [
            "CLOTHING_INVENTORY",
            "ITEM_SPECIFIC_URL",
            "INVENTORY_PRESENT",
            "DIRECT_SALE_PRESENT",
            "PRICE_PRESENT",
            "QUANTITY_PRESENT",
        ],
        "descriptions": [],
        "inventory_type": "BULK_CLOTHING_LOT",
        "listing_status": resalg_listing.get("listing_status") or ACTIVE,
        "opportunity_identity": url,
        "identity_stable": True,
        "source_native_price_evidence_detected": price_detected,
        "source_native_quantity_evidence_detected": quantity_detected,
        "source_native_value_capture_version": value_capture_version or None,
        "source_native_price_candidates": price_candidates,
        "source_native_price_basis_candidates": price_basis_candidates,
        "source_native_quantity_candidates": quantity_candidates,
        "source_native_commercial_terms_capture_version": commercial_terms_capture_version or None,
        "source_native_condition_candidates": condition_candidates,
        "source_native_seller_identity_candidates": seller_identity_candidates,
        "source_native_fulfilment_candidates": fulfilment_candidates,
        "source_native_commercial_terms_capture_is_qualification_evidence": False,
        "source_specific_enrichment": dict(resalg_listing) if resalg_listing else None,
        "sale_mode": "AUCTION" if resalg_listing else None,
        "current_bid": resalg_current_bid.get("amount"),
        "currency": resalg_current_bid.get("currency"),
        "auction_end_text": resalg_listing.get("ends_at"),
        "lot_units": resalg_lot_container.get("amount"),
        "lot_unit_type": resalg_lot_container.get("unit"),
        "stock_location": resalg_listing.get("pickup_location"),
        "source_value_normalization_required": not values_normalized,
        "source_value_normalization": normalization,
        "verification": [
            {
                "url": url,
                "title": title,
                "listing_status": ACTIVE,
                "page_role": ITEM_LISTING,
                "opportunity_identity": url,
                "identity_stable": True,
                "clothing_inventory_evidence": evidence.get("project_domain") == CLOTHING_INVENTORY,
                "sale_evidence": evidence.get("direct_sale_evidence") is True,
                "price_evidence": price_detected,
                "quantity_evidence": quantity_detected,
                "source_native_price_basis_candidates": price_basis_candidates,
                "source_value_normalization_required": not values_normalized,
                "source_value_normalization": normalization,
                "source_native_commercial_terms_capture_version": commercial_terms_capture_version or None,
                "source_native_condition_candidates": condition_candidates,
                "source_native_seller_identity_candidates": seller_identity_candidates,
                "source_native_fulfilment_candidates": fulfilment_candidates,
                "source_native_commercial_terms_capture_is_qualification_evidence": False,
                "source_specific_enrichment": (
                    dict(resalg_listing) if resalg_listing else None
                ),
                "current_bid": resalg_current_bid.get("amount"),
                "currency": resalg_current_bid.get("currency"),
                "auction_end_text": resalg_listing.get("ends_at"),
                "lot_units": resalg_lot_container.get("amount"),
                "lot_unit_type": resalg_lot_container.get("unit"),
                "stock_location": resalg_listing.get("pickup_location"),
                "verification_content_match": True,
                "bounded_context": bounded_context,
                "verified": True,
            }
        ],
        "verification_succeeded": True,
        "false_positive_guard_triggered": False,
        "discovery_score": 80,
        "discovery_band": "HIGH",
        "score_breakdown": {"strict_exact_lot_gate": 80},
        "why_opportunity": [
            "Exact public item/lot page was fetched successfully.",
            "Clothing domain, direct sale, and source-native numeric price and quantity evidence are present.",
        ],
        "confirmed_information": confirmed_information,
        "missing_information": missing_information,
        "next_verification_step": (
            "Confirm condition, seller identity and pickup/shipping terms before financial analysis."
            if values_normalized
            else
            "Resolve source price/quantity ambiguity or unsupported formatting, then confirm "
            "condition, seller identity and pickup/shipping terms before financial analysis."
        ),
        "top5_eligible": True,
        "analysis_eligible": False,
        "textile_category": "CLOTHING_INVENTORY",
        "market_code": market,
    }


def build_checkpoint_result_from_exact_lots(
    exact_lots: list[Mapping[str, Any]],
    *,
    market: str,
    query_count: int,
    hit_count: int,
    verification: Mapping[str, Any],
    multihop: Mapping[str, Any],
    source_mode: str = EXA_SOURCE_MODE,
    engine_version: str = EXA_ENGINE_VERSION,
) -> dict[str, Any]:
    candidates = [_candidate_from_exact_lot(row, market=market) for row in exact_lots]
    direct_rescue_count = sum(
        1 for row in exact_lots if row.get("direct_strict_evidence_rescue") == DIRECT_STRICT_EVIDENCE_RESCUE
    )
    report = {
        "schema_version": "exa-exact-lot-checkpoint-bridge-1.9",
        "status": "SUCCESS",
        "execution_status": "PASS",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "domain": CLOTHING_INVENTORY,
        "market_code": market,
        "currency": MARKET_CURRENCIES[market],
        "source_mode": source_mode,
        "engine_version": engine_version,
        "provider_strategy": "EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK",
        "query_pack": "SIX_MARKET_EXACT_LOT_CONTROLLED_COMMERCIAL_ANCHORS_V1",
        "queries_submitted": query_count,
        "hits_received": hit_count,
        "merged_candidates": len(candidates),
        "confirmed_sales": len(candidates),
        "strong_leads_requiring_verification": 0,
        "rejected_results": 0,
        "generic_pages_excluded": int(multihop.get("gateway_page_count") or 0),
        "direct_exact_lot_count": int(verification.get("exact_lot_candidate_count") or 0),
        "direct_strict_evidence_rescue_count": direct_rescue_count,
        "multihop_exact_lot_count": int(multihop.get("exact_lot_candidate_count") or 0),
        "strict_exact_lot_count": len(candidates),
        "source_native_value_evidence_count": sum(
            1
            for candidate in candidates
            if candidate.get("source_native_price_evidence_detected") is True
            and candidate.get("source_native_quantity_evidence_detected") is True
        ),
        "source_value_normalized_count": sum(
            1
            for candidate in candidates
            if (candidate.get("source_value_normalization") or {}).get("status") == "NORMALIZED"
        ),
        "source_value_normalization_required_count": sum(
            1 for candidate in candidates if candidate.get("source_value_normalization_required") is True
        ),
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    result = {
        "search_run_report": report,
        "all_discovered_candidates": candidates,
        "discovery_top5": candidates[:5],
    }
    return apply_post_verification_top5_hard_gate(result)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_market(
    *,
    market: str,
    exa_api_key: str,
    output_dir: Path,
    results_per_query: int,
    search_policy_memory: Mapping[str, Any] | None = None,
    brave_api_key: str = "",
) -> dict[str, Any]:
    primary_query_plan, search_policy_challenge = build_market_query_plan(
        market=market,
        base_queries=MARKET_EXACT_LOT_QUERY_PACKS[market],
        memory=search_policy_memory,
    )
    primary_queries = tuple(row["query"] for row in primary_query_plan)
    recall_queries = MARKET_ZERO_YIELD_RECALL_QUERIES.get(market, ())
    anchor_queries = build_commercial_anchor_queries(
        market=market,
        project_domain=CLOTHING_INVENTORY,
        max_queries=MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    )
    exa_provider = ExaSearchProvider(exa_api_key)
    all_hits = []
    seen_urls: set[str] = set()
    query_rows: list[dict[str, Any]] = []
    exa_search_errors: list[dict[str, str]] = []

    def collect(
        query: str,
        *,
        stage: str,
        anchor_type: str = "",
        anchor_value: str = "",
        anchor_origin: str = "",
        trial_id: str = "",
    ) -> None:
        if not _market_anchored(query, market):
            raise RuntimeError(f"query not market anchored: {market}: {query}")
        if classify_project_domain(text=query) != CLOTHING_INVENTORY:
            raise RuntimeError(f"query escaped clothing domain: {market}: {query}")
        if "site:" in query.casefold():
            raise RuntimeError(f"source-specific query is forbidden: {market}: {query}")
        search_error = ""
        try:
            hits = list(exa_provider.search(query, count=results_per_query))[:results_per_query]
        except RuntimeError as exc:
            hits = []
            search_error = _compact(exc)[:500]
            exa_search_errors.append(
                {
                    "query": query,
                    "query_stage": stage,
                    "error_type": type(exc).__name__,
                    "error": search_error,
                }
            )
        row = {
            "query": query,
            "query_stage": stage,
            "provider": "exa",
            "status": "FAILURE" if search_error else "SUCCESS",
            "hits": [
                {"title": hit.title, "url": hit.url, "description": hit.description}
                for hit in hits
            ],
        }
        if search_error:
            row["error"] = search_error
        if stage == "COMMERCIAL_ANCHOR":
            row["commercial_anchor"] = {
                "type": _compact(anchor_type),
                "value": _compact(anchor_value),
                "origin": _compact(anchor_origin),
                "qualification_evidence": False,
            }
        if trial_id:
            row["search_policy_challenge"] = {
                "trial_id": trial_id,
                "query_stage": stage,
                "request_slots_added": 0,
                "budget_change": 0,
                "provider": "exa",
            }
        query_rows.append(row)
        for hit in hits:
            identity_key = _exact_lot_identity_key(hit.url)
            if not identity_key or identity_key in seen_urls:
                continue
            seen_urls.add(identity_key)
            all_hits.append(hit)

    def evaluate() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        benchmark = _custom_benchmark(
            market=market,
            query=" | ".join(row["query"] for row in query_rows),
            hits=all_hits,
            project_domain=CLOTHING_INVENTORY,
        )
        verification = verify_provider_unique_pages(
            benchmark,
            provider="exa",
            max_page_fetches=min(30, max(1, len(all_hits))),
        )
        multihop = resolve_exact_lot_multihop(
            verification,
            max_root_parents=6,
            max_navigation_depth=3,
            max_links_per_page=12,
            max_navigation_page_fetches=30,
        )
        return verification, multihop, _exact_lot_rows(verification, multihop)

    for query_plan_row in primary_query_plan:
        collect(
            query_plan_row["query"],
            stage=query_plan_row["query_stage"],
            trial_id=query_plan_row.get("trial_id") or "",
        )

    verification, multihop, exact_lots = evaluate()
    primary_snapshot = _fresh_coverage_snapshot(exact_lots)
    primary_strict_exact_lot_count = len(exact_lots)
    primary_fresh_current_strict_exact_lot_count = int(
        primary_snapshot["fresh_current_strict_exact_lot_count"]
    )
    primary_recovery_strict_exact_lot_count = int(
        primary_snapshot["reverified_recovery_strict_exact_lot_count"]
    )
    zero_yield_recall_triggered = not exact_lots and bool(recall_queries)
    recovery_masked_fresh_recall_triggered = bool(
        recall_queries and _recovery_masks_fresh_coverage(primary_snapshot)
    )
    fresh_recall_triggered = bool(
        recall_queries
        and (zero_yield_recall_triggered or recovery_masked_fresh_recall_triggered)
    )

    if fresh_recall_triggered:
        recall_stage = "ZERO_YIELD_RECALL" if zero_yield_recall_triggered else "FRESH_RECALL"
        for query in recall_queries:
            collect(query, stage=recall_stage)
        verification, multihop, exact_lots = evaluate()

    post_recall_snapshot = _fresh_coverage_snapshot(exact_lots)
    post_recall_strict_exact_lot_count = len(exact_lots)
    post_recall_fresh_current_strict_exact_lot_count = int(
        post_recall_snapshot["fresh_current_strict_exact_lot_count"]
    )
    anchor_pre_count = post_recall_strict_exact_lot_count
    anchor_pre_fresh_count = post_recall_fresh_current_strict_exact_lot_count
    pre_anchor_exact_lots = [dict(row) for row in exact_lots]
    anchor_pre_unique_hit_count = len(all_hits)
    anchor_min_unique_hit_count = _commercial_anchor_min_unique_discovery_hits(market)
    anchor_fresh_coverage_gap = bool(
        anchor_pre_count < COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD
        or _recovery_masks_fresh_coverage(post_recall_snapshot)
    )
    anchor_expansion_triggered = bool(
        anchor_queries
        and anchor_fresh_coverage_gap
        and anchor_pre_unique_hit_count >= anchor_min_unique_hit_count
    )

    if anchor_expansion_triggered:
        for anchor in anchor_queries:
            collect(
                anchor["query"],
                stage="COMMERCIAL_ANCHOR",
                anchor_type=anchor["anchor_type"],
                anchor_value=anchor["anchor_value"],
                anchor_origin=anchor.get("anchor_origin", ""),
            )
        verification, multihop, exact_lots = evaluate()

    exa_final_exact_lots = [dict(row) for row in exact_lots]
    exa_final_snapshot = _fresh_coverage_snapshot(exa_final_exact_lots)
    anchor_outcome_evidence = _commercial_anchor_outcome_evidence(
        market=market,
        query_rows=query_rows,
        pre_anchor_exact_lots=pre_anchor_exact_lots,
        final_exact_lots=exa_final_exact_lots,
    )

    fallback_reasons = _brave_fallback_reasons(
        exa_final_snapshot,
        exa_search_error_count=len(exa_search_errors),
    )
    fallback_required = bool(fallback_reasons)
    fallback_triggered = False
    fallback_status = "NOT_REQUIRED"
    fallback_error = ""
    fallback_query = MARKET_BRAVE_FALLBACK_QUERIES[market]
    brave_hits: list[Any] = []
    brave_raw_hit_count = 0
    brave_verification: dict[str, Any] = {}
    brave_multihop: dict[str, Any] = {}
    brave_exact_lots: list[dict[str, Any]] = []
    brave_logical_query_count = 0

    if fallback_required and not _compact(brave_api_key):
        fallback_status = "SKIPPED_NO_API_KEY"
    elif fallback_required:
        if not _market_anchored(fallback_query, market):
            raise RuntimeError(f"fallback query not market anchored: {market}: {fallback_query}")
        if classify_project_domain(text=fallback_query) != CLOTHING_INVENTORY:
            raise RuntimeError(f"fallback query escaped clothing domain: {market}: {fallback_query}")
        if "site:" in fallback_query.casefold():
            raise RuntimeError(f"source-specific fallback query is forbidden: {market}: {fallback_query}")

        fallback_triggered = True
        brave_logical_query_count = 1
        try:
            require_provider_for_intent(BRAVE, VERIFIED_EXACT_LOT_FALLBACK)
            brave_provider = BraveSearchProvider(
                brave_api_key,
                country=market,
                extra_snippets=True,
                max_retries=0,
            )
            raw_brave_hits = list(
                brave_provider.search(
                    fallback_query,
                    count=min(results_per_query, BRAVE_FALLBACK_RESULTS_PER_QUERY),
                )
            )[:BRAVE_FALLBACK_RESULTS_PER_QUERY]
            brave_raw_hit_count = len(raw_brave_hits)
            for hit in raw_brave_hits:
                identity = _exact_lot_identity_key(getattr(hit, "url", ""))
                if not identity or identity in seen_urls:
                    continue
                seen_urls.add(identity)
                brave_hits.append(hit)
            fallback_status = "SUCCESS" if brave_hits else "VALID_ZERO_RESULT"
        except RuntimeError as exc:
            fallback_error = _compact(exc)[:500]
            fallback_status = _fallback_failure_status(exc)

        brave_query_row: dict[str, Any] = {
            "query": fallback_query,
            "query_stage": "BRAVE_VERIFIED_FALLBACK",
            "provider": "brave",
            "status": fallback_status,
            "hits": [
                {"title": hit.title, "url": hit.url, "description": hit.description}
                for hit in brave_hits
            ],
        }
        if fallback_error:
            brave_query_row["error"] = fallback_error
        query_rows.append(brave_query_row)

        if fallback_status in {"SUCCESS", "VALID_ZERO_RESULT"}:
            brave_benchmark = _hybrid_provider_benchmark(
                market=market,
                query=fallback_query,
                exa_hits=list(all_hits),
                brave_hits=brave_hits,
            )
            brave_verification = verify_provider_unique_pages(
                brave_benchmark,
                provider="brave",
                max_page_fetches=min(
                    BRAVE_FALLBACK_MAX_PAGE_FETCHES,
                    max(1, len(brave_hits)),
                ),
            )
            brave_multihop = resolve_exact_lot_multihop(
                brave_verification,
                max_root_parents=BRAVE_FALLBACK_MAX_ROOT_PARENTS,
                max_navigation_depth=3,
                max_links_per_page=12,
                max_navigation_page_fetches=BRAVE_FALLBACK_MAX_NAVIGATION_FETCHES,
            )
            brave_exact_lots = _exact_lot_rows(brave_verification, brave_multihop)
            for row in brave_exact_lots:
                row["provider"] = "brave"
                row.setdefault("retrieval_provenance", "DIRECT_SEARCH_RESULT")

    exact_lots = _merge_exact_lots(exa_final_exact_lots, brave_exact_lots)
    final_snapshot = _fresh_coverage_snapshot(exact_lots)
    hybrid_used = fallback_status in {"SUCCESS", "VALID_ZERO_RESULT"}
    source_mode = HYBRID_SOURCE_MODE if hybrid_used else EXA_SOURCE_MODE
    engine_version = HYBRID_ENGINE_VERSION if hybrid_used else EXA_ENGINE_VERSION
    combined_verification = dict(verification)
    combined_verification["exact_lot_candidate_count"] = int(
        verification.get("exact_lot_candidate_count") or 0
    ) + int(brave_verification.get("exact_lot_candidate_count") or 0)
    combined_multihop = dict(multihop)
    combined_multihop["exact_lot_candidate_count"] = int(
        multihop.get("exact_lot_candidate_count") or 0
    ) + int(brave_multihop.get("exact_lot_candidate_count") or 0)
    combined_multihop["gateway_page_count"] = int(
        multihop.get("gateway_page_count") or 0
    ) + int(brave_multihop.get("gateway_page_count") or 0)

    result = build_checkpoint_result_from_exact_lots(
        exact_lots,
        market=market,
        query_count=len(query_rows),
        hit_count=sum(len(row["hits"]) for row in query_rows),
        verification=combined_verification,
        multihop=combined_multihop,
        source_mode=source_mode,
        engine_version=engine_version,
    )
    report = result["search_run_report"]
    successful_query_statuses = {"SUCCESS", "VALID_ZERO_RESULT"}
    successful_query_count = sum(
        _compact(row.get("status")).upper() in successful_query_statuses
        for row in query_rows
    )
    failed_or_skipped_query_count = len(query_rows) - successful_query_count
    if successful_query_count == 0:
        report["status"] = "FAILURE"
        report["execution_status"] = "FAIL"
        retrieval_status = "FAILURE"
    elif failed_or_skipped_query_count:
        retrieval_status = "PARTIAL_SUCCESS"
    else:
        retrieval_status = "SUCCESS"
    report["retrieval_status"] = retrieval_status
    report["successful_query_count"] = successful_query_count
    report["failed_or_skipped_query_count"] = failed_or_skipped_query_count
    report["fresh_recall_trigger_version"] = "FRESH_RECALL_TRIGGER_V1"
    report["fresh_recall_min_current_exact_lots"] = FRESH_RECALL_MIN_CURRENT_EXACT_LOTS
    report["fresh_recall_min_current_route_hosts"] = FRESH_RECALL_MIN_CURRENT_ROUTE_HOSTS
    report["primary_query_count"] = len(primary_queries)
    report["search_policy_query_challenge"] = search_policy_challenge
    report["provider_strategy"] = "EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK"
    report["primary_search_provider"] = "EXA"
    report["providers_supported"] = ["EXA", "BRAVE"]
    report["providers_available"] = ["EXA"] + (
        ["BRAVE"] if _compact(brave_api_key) else []
    )
    report["providers_used"] = ["EXA"] + (["BRAVE"] if hybrid_used else [])
    report["exa_query_count"] = sum(
        row.get("provider") == "exa" for row in query_rows
    )
    report["exa_search_error_count"] = len(exa_search_errors)
    report["exa_search_errors"] = exa_search_errors
    report["brave_fallback_required"] = fallback_required
    report["brave_fallback_available"] = bool(_compact(brave_api_key))
    report["brave_fallback_triggered"] = fallback_triggered
    report["brave_fallback_status"] = fallback_status
    report["brave_fallback_trigger_reasons"] = fallback_reasons
    report["brave_fallback_max_queries_per_market"] = (
        BRAVE_FALLBACK_MAX_QUERIES_PER_MARKET
    )
    report["brave_fallback_max_outbound_attempts_per_market"] = (
        BRAVE_FALLBACK_MAX_OUTBOUND_ATTEMPTS_PER_MARKET
    )
    report["brave_fallback_query_count"] = brave_logical_query_count
    report["brave_fallback_raw_hits_received"] = brave_raw_hit_count
    report["brave_fallback_hits_received"] = len(brave_hits)
    report["brave_fallback_duplicate_hits_excluded"] = max(
        0, brave_raw_hit_count - len(brave_hits)
    )
    report["exa_strict_exact_lot_count"] = len(exa_final_exact_lots)
    report["brave_fallback_verified_exact_lot_count"] = len(brave_exact_lots)
    report["brave_fallback_added_strict_exact_lot_count"] = max(
        0, len(exact_lots) - len(exa_final_exact_lots)
    )
    report["brave_fallback_error"] = fallback_error or None
    report["exact_lots_counted_only_after_live_page_verification"] = True
    report["live_page_validation"] = _live_page_validation_summary(
        verification,
        multihop,
        fallback_verification=brave_verification,
        fallback_multihop=brave_multihop,
    )
    report["direct_source_adapters_remain_checkpoint_inputs"] = True
    report["country_specific_search_bypass_created"] = False
    report["primary_strict_exact_lot_count"] = primary_strict_exact_lot_count
    report["primary_fresh_current_strict_exact_lot_count"] = (
        primary_fresh_current_strict_exact_lot_count
    )
    report["primary_reverified_recovery_strict_exact_lot_count"] = (
        primary_recovery_strict_exact_lot_count
    )
    report["primary_fresh_current_route_host_count"] = int(
        primary_snapshot["fresh_current_route_host_count"]
    )
    report["zero_yield_recall_available"] = bool(recall_queries)
    report["zero_yield_recall_triggered"] = zero_yield_recall_triggered
    report["zero_yield_recall_query_count"] = (
        len(recall_queries) if zero_yield_recall_triggered else 0
    )
    report["zero_yield_recall_added_exact_lot_count"] = (
        max(0, post_recall_strict_exact_lot_count - primary_strict_exact_lot_count)
        if zero_yield_recall_triggered
        else 0
    )
    report["fresh_recall_triggered"] = fresh_recall_triggered
    report["fresh_recall_recovery_mask_triggered"] = recovery_masked_fresh_recall_triggered
    report["fresh_recall_query_count"] = len(recall_queries) if fresh_recall_triggered else 0
    report["fresh_recall_added_exact_lot_count"] = max(
        0, post_recall_strict_exact_lot_count - primary_strict_exact_lot_count
    )
    report["fresh_recall_added_fresh_current_exact_lot_count"] = max(
        0,
        post_recall_fresh_current_strict_exact_lot_count
        - primary_fresh_current_strict_exact_lot_count,
    )
    report["post_recall_fresh_current_route_host_count"] = int(
        post_recall_snapshot["fresh_current_route_host_count"]
    )
    report["commercial_anchor_expansion_available"] = bool(anchor_queries)
    report["commercial_anchor_expansion_triggered"] = anchor_expansion_triggered
    report["commercial_anchor_trigger_threshold"] = COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD
    report["commercial_anchor_fresh_coverage_gap"] = anchor_fresh_coverage_gap
    report["commercial_anchor_min_unique_discovery_hits"] = anchor_min_unique_hit_count
    report["commercial_anchor_pre_unique_discovery_hit_count"] = anchor_pre_unique_hit_count
    report["commercial_anchor_query_count"] = len(anchor_queries) if anchor_expansion_triggered else 0
    report["commercial_anchor_pre_strict_exact_lot_count"] = anchor_pre_count
    report["commercial_anchor_pre_fresh_current_strict_exact_lot_count"] = anchor_pre_fresh_count
    report["commercial_anchor_pre_fresh_current_route_host_count"] = int(
        post_recall_snapshot["fresh_current_route_host_count"]
    )
    report["commercial_anchor_added_exact_lot_count"] = max(
        0, len(exa_final_exact_lots) - anchor_pre_count
    )
    report["commercial_anchor_outcome_count"] = anchor_outcome_evidence["outcome_count"]
    report["commercial_anchor_successful_outcome_count"] = anchor_outcome_evidence[
        "successful_outcome_count"
    ]
    report["commercial_anchor_unattributed_added_exact_lot_count"] = anchor_outcome_evidence[
        "unattributed_added_strict_exact_lot_count"
    ]
    report["commercial_anchor_is_qualification_evidence"] = False
    report["commercial_anchor_max_queries_per_market"] = MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET
    report["exa_final_fresh_current_strict_exact_lot_count"] = int(
        exa_final_snapshot["fresh_current_strict_exact_lot_count"]
    )
    report["exa_final_fresh_current_route_host_count"] = int(
        exa_final_snapshot["fresh_current_route_host_count"]
    )
    report["final_fresh_current_strict_exact_lot_count"] = int(
        final_snapshot["fresh_current_strict_exact_lot_count"]
    )
    report["final_reverified_recovery_strict_exact_lot_count"] = int(
        final_snapshot["reverified_recovery_strict_exact_lot_count"]
    )
    report["final_fresh_current_route_host_count"] = int(
        final_snapshot["fresh_current_route_host_count"]
    )

    direct_rescue_urls = [
        row.get("url")
        for row in exact_lots
        if row.get("direct_strict_evidence_rescue") == DIRECT_STRICT_EVIDENCE_RESCUE
    ]
    _write_json(
        output_dir / "exa-exact-lot-resolution.json",
        {
            "schema_version": "exa-exact-lot-checkpoint-resolution-1.9",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market": market,
            "project_domain": CLOTHING_INVENTORY,
            "provider": "exa-primary-brave-fallback" if hybrid_used else "exa",
            "provider_strategy": "EXA_PRIMARY_BRAVE_VERIFIED_FALLBACK",
            "providers_used": report["providers_used"],
            "source_mode": source_mode,
            "engine_version": engine_version,
            "queries": query_rows,
            "search_policy_query_challenge": search_policy_challenge,
            "adaptive_zero_yield_recall": {
                "available": bool(recall_queries),
                "triggered": zero_yield_recall_triggered,
                "primary_strict_exact_lot_count": primary_strict_exact_lot_count,
                "recall_query_count": len(recall_queries) if zero_yield_recall_triggered else 0,
                "post_recall_strict_exact_lot_count": post_recall_strict_exact_lot_count,
            },
            "adaptive_fresh_recall": {
                "version": "FRESH_RECALL_TRIGGER_V1",
                "available": bool(recall_queries),
                "triggered": fresh_recall_triggered,
                "recovery_mask_triggered": recovery_masked_fresh_recall_triggered,
                "min_current_exact_lots": FRESH_RECALL_MIN_CURRENT_EXACT_LOTS,
                "min_current_route_hosts": FRESH_RECALL_MIN_CURRENT_ROUTE_HOSTS,
                "primary": primary_snapshot,
                "post_recall": post_recall_snapshot,
                "recovery_is_stopping_evidence": False,
            },
            "controlled_commercial_anchor_expansion": {
                "available": bool(anchor_queries),
                "triggered": anchor_expansion_triggered,
                "threshold": COMMERCIAL_ANCHOR_THIN_YIELD_THRESHOLD,
                "fresh_coverage_gap": anchor_fresh_coverage_gap,
                "min_unique_discovery_hits": anchor_min_unique_hit_count,
                "pre_anchor_unique_discovery_hit_count": anchor_pre_unique_hit_count,
                "pre_anchor_fresh_current_exact_lot_count": anchor_pre_fresh_count,
                "pre_anchor_fresh_current_route_host_count": int(
                    post_recall_snapshot["fresh_current_route_host_count"]
                ),
                "max_queries_per_market": MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
                "query_count": len(anchor_queries) if anchor_expansion_triggered else 0,
                "pre_anchor_strict_exact_lot_count": anchor_pre_count,
                "added_exact_lot_count": max(
                    0, len(exa_final_exact_lots) - anchor_pre_count
                ),
                "final_strict_exact_lot_count": len(exa_final_exact_lots),
                "final_fresh_current_exact_lot_count": int(
                    exa_final_snapshot["fresh_current_strict_exact_lot_count"]
                ),
                "final_fresh_current_route_host_count": int(
                    exa_final_snapshot["fresh_current_route_host_count"]
                ),
                "anchor_is_qualification_evidence": False,
            },
            "commercial_anchor_outcome_evidence": anchor_outcome_evidence,
            "brave_verified_fallback": {
                "required": fallback_required,
                "available": bool(_compact(brave_api_key)),
                "triggered": fallback_triggered,
                "status": fallback_status,
                "trigger_reasons": fallback_reasons,
                "query": fallback_query if fallback_required else None,
                "max_queries_per_market": BRAVE_FALLBACK_MAX_QUERIES_PER_MARKET,
                "max_outbound_attempts_per_market": (
                    BRAVE_FALLBACK_MAX_OUTBOUND_ATTEMPTS_PER_MARKET
                ),
                "query_count": brave_logical_query_count,
                "raw_hits_received": brave_raw_hit_count,
                "hits_received": len(brave_hits),
                "duplicate_hits_excluded": max(
                    0, brave_raw_hit_count - len(brave_hits)
                ),
                "verified_exact_lot_count": len(brave_exact_lots),
                "added_strict_exact_lot_count": report[
                    "brave_fallback_added_strict_exact_lot_count"
                ],
                "error": fallback_error or None,
                "verification": brave_verification,
                "multihop": brave_multihop,
            },
            "live_page_validation": report["live_page_validation"],
            "direct_strict_evidence_rescue": {
                "rule": DIRECT_STRICT_EVIDENCE_RESCUE,
                "count": len(direct_rescue_urls),
                "urls": direct_rescue_urls,
                "brand_or_anchor_is_qualification_evidence": False,
            },
            "verification": verification,
            "multihop": multihop,
            "strict_exact_lot_count": len(exact_lots),
            "strict_exact_lot_urls": [row.get("url") for row in exact_lots],
            "source_native_value_evidence_count": report["source_native_value_evidence_count"],
            "source_value_normalization_required_count": report[
                "source_value_normalization_required_count"
            ],
            "production_mutation": False,
            "automatic_provider_activation": False,
            "country_specific_search_bypass_created": False,
        },
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=tuple(MARKET_EXACT_LOT_QUERY_PACKS), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--results-per-query", type=int, default=RESULTS_PER_QUERY)
    parser.add_argument("--persist-unified", action="store_true")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--alembic-config", default="alembic.ini")
    parser.add_argument(
        "--search-policy-memory",
        default="",
        help=(
            "Optional Unified Memory V2 path used only to count the approved "
            "three-day DE/NO query challenge."
        ),
    )
    args = parser.parse_args()

    if not 1 <= args.results_per_query <= RESULTS_PER_QUERY:
        raise SystemExit(f"--results-per-query must be between 1 and {RESULTS_PER_QUERY}")
    if args.persist_unified and not _compact(args.database_url):
        raise SystemExit("--database-url is required with --persist-unified")
    exa_api_key = _compact(os.environ.get("EXA_API_KEY"))
    brave_api_key = _compact(os.environ.get("BRAVE_SEARCH_API_KEY"))
    if not exa_api_key:
        raise SystemExit("EXA_API_KEY is required")

    market = args.market.upper()
    output_dir = Path(args.output_dir)
    search_policy_memory = None
    if _compact(args.search_policy_memory):
        memory_path = Path(args.search_policy_memory)
        if memory_path.exists():
            loaded_memory = json.loads(memory_path.read_text(encoding="utf-8"))
            if not isinstance(loaded_memory, Mapping):
                raise SystemExit("--search-policy-memory must contain a JSON object")
            search_policy_memory = loaded_memory
    result = run_market(
        market=market,
        exa_api_key=exa_api_key,
        output_dir=output_dir,
        results_per_query=args.results_per_query,
        search_policy_memory=search_policy_memory,
        brave_api_key=brave_api_key,
    )
    paths = write_discovery_artifacts(result, output_dir)
    unified_path = write_unified_opportunity_report(
        result,
        output_dir,
        market_code=market,
        currency=MARKET_CURRENCIES[market],
        domain=CLOTHING_INVENTORY,
    )
    paths["unified_opportunity_report"] = unified_path

    if args.persist_unified:
        from opportunity_engine.persistence.live_unified_persistence import (
            persist_unified_report_with_artifacts,
        )

        _, persistence_summary_path = persist_unified_report_with_artifacts(
            unified_path,
            output_dir,
            database_url=args.database_url,
            config_path=args.alembic_config,
        )
        paths["unified_persistence_summary"] = persistence_summary_path

    report = result["search_run_report"]
    print(f"Status: {report['status']}")
    print(f"Market: {market}")
    print(f"Source: {report['source_mode']}")
    print(f"Queries: {report['queries_submitted']}")
    print(f"Hits: {report['hits_received']}")
    print(f"Strict Exact-Lots: {report['strict_exact_lot_count']}")
    print(
        "Search Policy challenge: "
        f"{(report.get('search_policy_query_challenge') or {}).get('status', 'NOT_APPLICABLE')}"
    )
    print(f"Top opportunities: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
