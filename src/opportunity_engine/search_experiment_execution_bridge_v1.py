"""Execute bounded MIND FORGE search experiments and preserve truth diagnostics.

V1 remains deliberately bounded: one Exa query and at most five hits.  The bridge
is shadow-only, but every fetched fabric result now carries an explicit
ACCEPT/REJECT decision and a deterministic rejection reason so failures can be
remembered and reviewed instead of disappearing as a false zero.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.discovery.exact_lot_multihop_resolution import resolve_exact_lot_multihop
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult, fetch_public_page
from opportunity_engine.discovery.provider_unique_page_verification import verify_provider_unique_pages
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)
from opportunity_engine.provider_route_success_learning import build_provider_route_success_observation
from opportunity_engine.unified_memory_v2 import build_unified_memory_v2

SCHEMA_VERSION = "search-experiment-execution-bridge-1.1"
SPEC_SCHEMA_VERSION = "search-experiment-spec-1.1"
SPINE_SCHEMA_VERSION = "unified-learning-spine-1.0"

SUPPORTED_MARKETS = frozenset({"NO", "SE", "DE", "FR", "NL", "IT"})
SUPPORTED_DOMAINS = frozenset({CLOTHING_INVENTORY, FABRIC_PROCUREMENT})
SUPPORTED_PROVIDER = "exa"
MAX_RESULTS = 5
MAX_EXECUTIONS_PER_FINGERPRINT = 3

_EXECUTABLE_TASK_KINDS = frozenset(
    {"DISCOVER_NEW_ROUTE", "TURN_TRACKED_TARGET_INTO_ROUTE", "RESOLVE_OBSERVATION_TO_ROUTE", "RESOLVE_ROUTE_GAP"}
)
_MARKET_ANCHORS: dict[str, tuple[str, ...]] = {
    "NO": ("norge", "norway", "norsk"),
    "SE": ("sverige", "sweden", "svensk"),
    "DE": ("deutschland", "germany", "deutsch"),
    "FR": ("france", "français", "francais"),
    "NL": ("nederland", "netherlands", "dutch"),
    "IT": ("italia", "italy", "italiano", "italiana"),
}
_STRUCTURED_LINE_RE = re.compile(
    r'^\s*SEARCH_TEST_V1\s+provider=(?P<provider>[a-z0-9_-]+)\s*;\s*'
    r'query=(?P<quote>["\'])(?P<query>.+?)(?P=quote)\s*$',
    re.IGNORECASE,
)
_INTERNAL_QUERY_LABEL_REPLACEMENTS = {
    FABRIC_PROCUREMENT: "fabric textile",
    CLOTHING_INVENTORY: "clothing apparel",
}

# Inventory language must describe available stock/lot/rolls, not merely fabric.
# Dutch terms below come from the NL Search Truth benchmark and are vocabulary,
# not hard-coded sources or domains.
_FABRIC_INVENTORY_MARKERS = (
    "deadstock", "stock", "surplus", "clearance", "restpost", "restlager", "lager",
    "magazzino", "scorte", "rotoli", "rolls", "roll", "lotto", "lotti",
    "déstockage", "destockage", "fine pezza", "fine serie",
    "restpartij", "restpartijen", "restant", "restanten", "voorraad",
    "partijgoed", "partijgoederen", "overschot", "opruiming", "stofrol", "stofrollen",
)
_FABRIC_TRADE_MARKERS = (
    "wholesale", "grossiste", "ingrosso", "b2b", "bulk", "moq", "minimum order",
    "minimum quantity", "metri", "meters", "metres", "meterware", "rouleaux",
    "price", "prix", "prezzo", "eur", "€", "nok", "sek", "gbp", "£", "usd", "$",
    "per meter", "al metro", "groothandel", "per rol", "per rollen",
)
_SLOT_ROUTE = {
    "AUCTION": "SEARCH_EXPERIMENT_AUCTION",
    "DIRECT_INVENTORY": "SEARCH_EXPERIMENT_DIRECT_INVENTORY",
    "LIQUIDATION_BANKRUPTCY": "SEARCH_EXPERIMENT_LIQUIDATION_BANKRUPTCY",
    "WHOLESALE_STOCK_LOTS": "SEARCH_EXPERIMENT_WHOLESALE_STOCK_LOTS",
    "FABRIC_PROCUREMENT": "SEARCH_TO_FABRIC_COMMERCIAL_PAGE",
    "SEARCH_PROVIDER_ROUTE": "SEARCH_PROVIDER_EXACT_LOT",
}

ProviderFactory = Callable[[str], Any]
PageFetcher = Callable[[str], PageFetchResult]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _domain(url: object) -> str:
    try:
        host = (urlsplit(_text(url)).hostname or "").casefold()
    except ValueError:
        return ""
    return host.removeprefix("www.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(prefix: str, material: str) -> str:
    return f"{prefix}:{sha256(material.encode('utf-8')).hexdigest()[:24]}"


def _safety() -> dict[str, bool]:
    return {
        "project_domain_gate_enforced": True,
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


def _market_anchored(query: str, market: str) -> bool:
    folded = query.casefold()
    return any(anchor in folded for anchor in _MARKET_ANCHORS.get(market, ()))


def _route_for_slot(slot_id: str) -> str:
    route = _SLOT_ROUTE.get(slot_id)
    if not route:
        raise ValueError(f"unsupported route slot for search experiment: {slot_id}")
    return route


def _source_identity_for_slot(slot_id: str) -> str:
    return f"search-experiment:{slot_id.casefold()}"


def _route_pattern_key(spec: Mapping[str, Any]) -> str:
    return "|".join((
        "ROUTE_SUCCESS", _upper(spec.get("market_code")), _upper(spec.get("project_domain")),
        _text(spec.get("provider")).casefold(), _upper(spec.get("route")),
        _text(spec.get("route_source_identity")).casefold(),
    ))


def _task_is_search_route_task(task: Mapping[str, Any]) -> bool:
    return (
        _upper(task.get("execution_mode")) == "AI_TEACHING"
        and _upper(task.get("task_kind")) in _EXECUTABLE_TASK_KINDS
        and bool(_text(_mapping(task.get("context")).get("slot_id")))
    )


def _idea_map(creative_result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {_text(row.get("idea_id")): row for row in _rows(creative_result.get("ideas")) if _text(row.get("idea_id"))}


def _parse_structured_core(core_mechanism: object) -> tuple[str, str] | None:
    first_line = str(core_mechanism or "").splitlines()[0].strip()
    match = _STRUCTURED_LINE_RE.match(first_line)
    if not match:
        return None
    return match.group("provider").casefold(), _text(match.group("query"))


def _sanitize_public_query(query: str, domain: str) -> tuple[str, list[str]]:
    """Remove internal enum labels from public search text without changing scope."""
    clean = _text(query)
    removed: list[str] = []
    for label, replacement in _INTERNAL_QUERY_LABEL_REPLACEMENTS.items():
        pattern = re.compile(rf"(?<!\w){re.escape(label)}(?!\w)", re.IGNORECASE)
        if pattern.search(clean):
            removed.append(label)
            clean = pattern.sub(replacement if label == domain else " ", clean)
    return _text(clean), removed


def select_search_experiment_spec(*, teaching_task: Mapping[str, Any], creative_result: Mapping[str, Any], final_rank: Mapping[str, Any]) -> dict[str, Any]:
    task = _mapping(teaching_task)
    if not _task_is_search_route_task(task):
        return {"schema_version": SPEC_SCHEMA_VERSION, "status": "NO_EXECUTABLE_SEARCH_TASK", "reason": "TEACHING_TASK_IS_NOT_A_ROUTE_SEARCH_TASK", **_safety()}

    context = _mapping(task.get("context"))
    market = _upper(context.get("market_code"))
    domain = _upper(context.get("project_domain"))
    slot_id = _upper(context.get("slot_id"))
    if market not in SUPPORTED_MARKETS:
        raise ValueError(f"unsupported experiment market: {market}")
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(f"search experiment escaped project domain: {domain}")
    route = _route_for_slot(slot_id)
    ideas = _idea_map(creative_result)

    rejected: list[dict[str, str]] = []
    for rank, ranking in enumerate(_rows(final_rank.get("ranking")), start=1):
        idea_id = _text(ranking.get("idea_id"))
        idea = ideas.get(idea_id)
        if not idea:
            continue
        parsed = _parse_structured_core(idea.get("core_mechanism"))
        if parsed is None:
            rejected.append({"idea_id": idea_id, "reason": "MISSING_SEARCH_TEST_V1"})
            continue
        provider, raw_query = parsed
        if provider != SUPPORTED_PROVIDER:
            rejected.append({"idea_id": idea_id, "reason": "UNSUPPORTED_PROVIDER"})
            continue
        query, removed_labels = _sanitize_public_query(raw_query, domain)
        if not _market_anchored(query, market):
            rejected.append({"idea_id": idea_id, "reason": "QUERY_NOT_MARKET_ANCHORED"})
            continue
        query_domain = classify_project_domain(text=query)
        if query_domain != domain:
            rejected.append({"idea_id": idea_id, "reason": f"QUERY_DOMAIN_MISMATCH:{query_domain}"})
            continue

        task_id = _text(task.get("task_id"))
        fingerprint = _hash("search-experiment", "|".join((task_id, market, domain, slot_id, provider, query.casefold())))
        return {
            "schema_version": SPEC_SCHEMA_VERSION,
            "status": "READY",
            "experiment_fingerprint": fingerprint,
            "teaching_task_id": task_id,
            "teaching_task_kind": _upper(task.get("task_kind")),
            "selected_idea_id": idea_id,
            "selected_idea_rank": rank,
            "selected_idea_title": _text(idea.get("title")) or None,
            "market_code": market,
            "project_domain": domain,
            "slot_id": slot_id,
            "provider": provider,
            "query": query,
            "raw_query": raw_query,
            "query_internal_labels_removed": removed_labels,
            "route": route,
            "route_source_identity": _source_identity_for_slot(slot_id),
            "max_search_requests": 1,
            "max_results": MAX_RESULTS,
            "max_independent_executions": MAX_EXECUTIONS_PER_FINGERPRINT,
            "rejected_higher_or_other_ideas": rejected,
            "shadow_only": True,
            **_safety(),
        }

    return {
        "schema_version": SPEC_SCHEMA_VERSION,
        "status": "NO_EXECUTABLE_SEARCH_IDEA",
        "reason": "NO_RANKED_IDEA_SATISFIED_SEARCH_TEST_V1_CONTRACT",
        "market_code": market,
        "project_domain": domain,
        "slot_id": slot_id,
        "rejected_ideas": rejected,
        **_safety(),
    }


def _hit_row(hit: SearchHit) -> dict[str, Any]:
    return {"title": _text(hit.title)[:1000], "url": _text(hit.url), "domain": _domain(hit.url), "description": _text(hit.description)[:1000], "provider": _text(hit.provider)}


def _custom_benchmark(*, market: str, query: str, hits: Sequence[SearchHit], project_domain: str) -> dict[str, Any]:
    exa_rows = [_hit_row(hit) for hit in hits]
    unique_domains = len({row["domain"] for row in exa_rows if row["domain"]})
    return {
        "schema_version": "search-experiment-benchmark-1.0",
        "generated_at": _now(), "status": "SUCCESS", "shadow_only": True,
        "provider_mode": "exa", "query_mode": "exact_lot", "query_set": {market: query},
        "project_domain": project_domain, "project_domain_gate_enforced": True,
        "markets": [market], "results_per_query": MAX_RESULTS, "exa_request_count": 1, "brave_request_count": 0,
        "market_results": [{
            "market_code": market, "query": query,
            "exa": {"result_count": len(exa_rows), "unique_domain_count": unique_domains, "results": exa_rows},
            "brave": {"result_count": 0, "unique_domain_count": 0, "results": []},
            "comparison": {"shared_url_count": 0, "exa_unique_url_count": len({row["url"] for row in exa_rows}), "brave_unique_url_count": 0, "shared_domain_count": 0, "exa_unique_domain_count": unique_domains, "brave_unique_domain_count": 0},
        }],
        **_safety(),
    }


def _default_provider_factory(api_key: str) -> ExaSearchProvider:
    return ExaSearchProvider(api_key)


def _fabric_rejection_reason(*, fetch_ok: bool, domain: str | None, inventory: bool, trade: bool) -> str | None:
    if not fetch_ok:
        return "FETCH_FAILED"
    if domain != FABRIC_PROCUREMENT:
        return "OUT_OF_PROJECT_DOMAIN"
    if not inventory:
        return "MISSING_INVENTORY_SIGNAL"
    if not trade:
        return "MISSING_TRADE_OR_PRICE_SIGNAL"
    return None


def _fabric_page_candidate(hit: SearchHit, *, page_fetcher: PageFetcher) -> dict[str, Any]:
    fetched = page_fetcher(hit.url)
    base = {
        "url": _text(hit.url),
        "final_url": _text(fetched.final_url or hit.url),
        "title": _text(fetched.title or hit.title)[:1000],
        "fetch_ok": bool(fetched.ok),
        "status_code": fetched.status_code,
        "fetch_error": fetched.error,
        "result_domain": _domain(fetched.final_url or hit.url),
    }
    if not fetched.ok:
        reason = _fabric_rejection_reason(fetch_ok=False, domain=None, inventory=False, trade=False)
        return {**base, "project_domain": None, "inventory_signal": False, "trade_or_price_signal": False, "commercial_fabric_page": False, "verification_decision": "REJECT", "rejection_reason": reason}

    combined = _text(f"{fetched.title} {fetched.text}")
    domain = classify_project_domain(text=combined)
    folded = combined.casefold()
    inventory = any(marker in folded for marker in _FABRIC_INVENTORY_MARKERS)
    trade = any(marker in folded for marker in _FABRIC_TRADE_MARKERS)
    reason = _fabric_rejection_reason(fetch_ok=True, domain=domain, inventory=inventory, trade=trade)
    accepted = reason is None
    return {
        **base,
        "project_domain": domain,
        "inventory_signal": inventory,
        "trade_or_price_signal": trade,
        "commercial_fabric_page": accepted,
        "verification_decision": "ACCEPT" if accepted else "REJECT",
        "rejection_reason": reason,
    }


def _execute_clothing(*, spec: Mapping[str, Any], hits: Sequence[SearchHit], run_id: str) -> dict[str, Any]:
    benchmark = _custom_benchmark(market=_upper(spec.get("market_code")), query=_text(spec.get("query")), hits=hits, project_domain=CLOTHING_INVENTORY)
    verification = verify_provider_unique_pages(benchmark, provider="exa", max_page_fetches=MAX_RESULTS)
    multihop = resolve_exact_lot_multihop(verification, max_root_parents=3, max_navigation_depth=3, max_links_per_page=12, max_navigation_page_fetches=18)
    observation = build_provider_route_success_observation(run_id=run_id, provider="exa", benchmark=benchmark, provider_verification=verification, multihop_resolution=multihop)
    urls: set[str] = set()
    domains: set[str] = set()
    for route in _rows(observation.get("successful_routes")):
        for url in route.get("exact_lot_urls") or []:
            clean = _text(url)
            if clean:
                urls.add(clean)
                if _domain(clean):
                    domains.add(_domain(clean))
    return {
        "search_hit_count": len(hits), "verified_page_count": int(verification.get("page_fetches_succeeded") or 0),
        "successful_result_count": len(urls), "verified_result_urls": sorted(urls), "verified_result_domains": sorted(domains),
        "verification_summary": {"exact_lot_candidate_count": int(verification.get("exact_lot_candidate_count") or 0), "multihop_exact_lot_count": int(multihop.get("exact_lot_candidate_count") or 0)},
    }


def _execute_fabric(*, hits: Sequence[SearchHit], page_fetcher: PageFetcher) -> dict[str, Any]:
    rows = [_fabric_page_candidate(hit, page_fetcher=page_fetcher) for hit in list(hits)[:MAX_RESULTS]]
    accepted = [row for row in rows if row.get("commercial_fabric_page") is True]
    rejected = [row for row in rows if row.get("commercial_fabric_page") is not True]
    urls = sorted({_text(row.get("final_url") or row.get("url")) for row in accepted if _text(row.get("final_url") or row.get("url"))})
    domains = sorted({_domain(url) for url in urls if _domain(url)})
    reasons = Counter(_text(row.get("rejection_reason")) or "UNDIAGNOSED" for row in rejected)
    return {
        "search_hit_count": len(hits),
        "verified_page_count": sum(row.get("fetch_ok") is True for row in rows),
        "successful_result_count": len(urls),
        "verified_result_urls": urls,
        "verified_result_domains": domains,
        "rejected_result_count": len(rejected),
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "search_hit_audit": rows,
        "verification_summary": {
            "commercial_fabric_page_count": len(urls),
            "rejected_fabric_page_count": len(rejected),
            "out_of_domain_page_count": sum(row.get("rejection_reason") == "OUT_OF_PROJECT_DOMAIN" for row in rows),
        },
        "verified_pages": rows,
    }


def execute_search_experiment_spec(spec: Mapping[str, Any], *, exa_api_key: str, run_id: str, provider_factory: ProviderFactory = _default_provider_factory, page_fetcher: PageFetcher = fetch_public_page) -> dict[str, Any]:
    ready = _mapping(spec)
    if _upper(ready.get("status")) != "READY":
        raise ValueError("search experiment spec must be READY")
    market = _upper(ready.get("market_code"))
    domain = _upper(ready.get("project_domain"))
    provider = _text(ready.get("provider")).casefold()
    query = _text(ready.get("query"))
    if market not in SUPPORTED_MARKETS or domain not in SUPPORTED_DOMAINS:
        raise ValueError("search experiment spec escaped supported market/domain")
    if provider != SUPPORTED_PROVIDER:
        raise ValueError("Search Experiment V1 supports Exa only")
    if not _market_anchored(query, market) or classify_project_domain(text=query) != domain:
        raise ValueError("search experiment query failed market/domain gate")
    key = _text(exa_api_key)
    if not key:
        raise ValueError("EXA_API_KEY is required for search experiment execution")
    origin_run = _text(run_id)
    if not origin_run:
        raise ValueError("run_id is required")

    provider_client = provider_factory(key)
    hits = provider_client.search(query, count=MAX_RESULTS)
    details = _execute_clothing(spec=ready, hits=hits, run_id=origin_run) if domain == CLOTHING_INVENTORY else _execute_fabric(hits=hits, page_fetcher=page_fetcher)
    success_count = int(details.get("successful_result_count") or 0)
    return {
        "schema_version": SCHEMA_VERSION, "status": "SUCCESS", "shadow_only": True,
        "origin_experiment_run_id": origin_run, "observed_at": _now(),
        "experiment_fingerprint": _text(ready.get("experiment_fingerprint")), "spec": dict(ready),
        "outcome": "VERIFIED_ROUTE_SUCCESS" if success_count else "NO_VERIFIED_ROUTE",
        "successful_route": success_count > 0,
        **details,
        **_safety(),
    }


def _record(*, evidence_kind: str, identity: str, market: str, domain: str, source_name: str, provider: str, query: str, result_type: str, outcome: str, route: str, source_identity: str, observed_at: str, supporting_run_ids: list[str], metadata: Mapping[str, Any], url: str | None = None, miss_reason: str | None = None) -> dict[str, Any]:
    return {
        "learning_evidence_id": _hash("learning-evidence", f"{evidence_kind}|{identity}"),
        "evidence_kind": evidence_kind, "market_code": market, "project_domain": domain,
        "source_name": source_name, "provider": provider, "query": query, "url": url,
        "result_type": result_type, "outcome": outcome, "miss_reason": miss_reason,
        "route": route, "source_identity": source_identity, "observed_at": observed_at,
        "supporting_run_ids": supporting_run_ids, "metadata": dict(metadata),
    }


def build_experiment_spine(result: Mapping[str, Any]) -> dict[str, Any]:
    report = _mapping(result)
    if _upper(report.get("status")) != "SUCCESS":
        raise ValueError("search experiment result must be SUCCESS")
    spec = _mapping(report.get("spec"))
    market = _upper(spec.get("market_code"))
    domain = _upper(spec.get("project_domain"))
    provider = _text(spec.get("provider")).casefold()
    query = _text(spec.get("query"))
    route = _upper(spec.get("route"))
    source_identity = _text(spec.get("route_source_identity"))
    origin_run = _text(report.get("origin_experiment_run_id"))
    fingerprint = _text(report.get("experiment_fingerprint"))
    observed_at = _text(report.get("observed_at")) or _now()
    if market not in SUPPORTED_MARKETS or domain not in SUPPORTED_DOMAINS:
        raise ValueError("experiment result escaped market/domain gate")
    if not origin_run or not fingerprint or not query or not route or not source_identity:
        raise ValueError("experiment result is missing required identity fields")

    audit = [dict(row) for row in _rows(report.get("search_hit_audit"))]
    metadata = {
        "experiment_fingerprint": fingerprint,
        "origin_experiment_run_id": origin_run,
        "slot_id": _upper(spec.get("slot_id")),
        "search_hit_count": int(report.get("search_hit_count") or 0),
        "verified_page_count": int(report.get("verified_page_count") or 0),
        "successful_result_count": int(report.get("successful_result_count") or 0),
        "rejected_result_count": int(report.get("rejected_result_count") or 0),
        "rejection_reason_counts": dict(_mapping(report.get("rejection_reason_counts"))),
        "search_hit_audit": audit,
        "verified_result_urls": [_text(url) for url in report.get("verified_result_urls") or [] if _text(url)],
        "verified_result_domains": [_text(item) for item in report.get("verified_result_domains") or [] if _text(item)],
        "query_internal_labels_removed": [_text(item) for item in spec.get("query_internal_labels_removed") or [] if _text(item)],
        "shadow_only": True,
        "single_use_experiment_origin": True,
    }
    records = [_record(
        evidence_kind="MARKET_OBSERVATION", identity=f"{fingerprint}|{origin_run}|summary",
        market=market, domain=domain, source_name="SEARCH_EXPERIMENT_BRIDGE", provider=provider,
        query=query, result_type="SEARCH_EXPERIMENT", outcome=_upper(report.get("outcome")),
        route=route, source_identity=fingerprint, observed_at=observed_at,
        supporting_run_ids=[origin_run], metadata=metadata,
    )]

    for index, row in enumerate(audit):
        if _upper(row.get("verification_decision")) != "REJECT":
            continue
        url = _text(row.get("final_url") or row.get("url")) or None
        reason = _upper(row.get("rejection_reason")) or "UNDIAGNOSED"
        records.append(_record(
            evidence_kind="MARKET_OBSERVATION",
            identity=f"{fingerprint}|{origin_run}|rejection|{index}|{url or reason}",
            market=market, domain=domain, source_name="SEARCH_EXPERIMENT_BRIDGE", provider=provider,
            query=query, url=url, result_type="SEARCH_RESULT_REJECTION", outcome="REJECTED",
            miss_reason=reason, route=route, source_identity=url or f"{fingerprint}:rejection:{index}",
            observed_at=observed_at, supporting_run_ids=[origin_run],
            metadata={"experiment_fingerprint": fingerprint, "origin_experiment_run_id": origin_run, "verification_decision": "REJECT", "rejection_reason": reason, "fetch_ok": row.get("fetch_ok"), "status_code": row.get("status_code"), "result_domain": _text(row.get("result_domain")) or None, "project_domain": _text(row.get("project_domain")) or None, "inventory_signal": row.get("inventory_signal"), "trade_or_price_signal": row.get("trade_or_price_signal"), "shadow_only": True},
        ))

    urls = metadata["verified_result_urls"]
    if report.get("successful_route") is True and urls:
        records.append(_record(
            evidence_kind="SEARCH_ROUTE_SUCCESS", identity=f"{fingerprint}|{origin_run}|route",
            market=market, domain=domain, source_name="SEARCH_EXPERIMENT_BRIDGE", provider=provider,
            query=query, url=urls[0], result_type="SEARCH_ROUTE", outcome="CANDIDATE", route=route,
            source_identity=source_identity, observed_at=observed_at, supporting_run_ids=[origin_run],
            metadata={**metadata, "verified_exact_lot_urls": urls, "verified_exact_lot_url_count": len(urls), "independent_run_count": 0, "automatic_activation": False, "production_query_mutation": False},
        ))

    kind_counts = Counter(_upper(row.get("evidence_kind")) for row in records)
    return {
        "schema_version": SPINE_SCHEMA_VERSION, "status": "SUCCESS", "generated_at": observed_at,
        "input_presence": {"search_experiment_execution_bridge": True},
        "evidence_record_count": len(records), "market_counts": {market: len(records)},
        "domain_counts": {domain: len(records)}, "evidence_kind_counts": dict(sorted(kind_counts.items())),
        "out_of_domain_excluded_count": 0, "out_of_domain_excluded_ids": [], "records": records,
        "learning_contract": "MIND FORGE -> bounded Search Experiment -> explicit accept/reject evidence -> Unified Memory V2. No production mutation.",
        **_safety(),
    }


def _origin_seen(memory: Mapping[str, Any], *, fingerprint: str, origin_run_id: str) -> bool:
    return any(_text(_mapping(row.get("latest_metadata")).get("experiment_fingerprint")) == fingerprint and _text(_mapping(row.get("latest_metadata")).get("origin_experiment_run_id")) == origin_run_id for row in _rows(memory.get("evidence_memory")))


def _fingerprint_execution_count(memory: Mapping[str, Any], *, fingerprint: str) -> int:
    return len({_text(_mapping(row.get("latest_metadata")).get("origin_experiment_run_id")) for row in _rows(memory.get("evidence_memory")) if _text(_mapping(row.get("latest_metadata")).get("experiment_fingerprint")) == fingerprint and _text(_mapping(row.get("latest_metadata")).get("origin_experiment_run_id"))})


def _matching_route_status(memory: Mapping[str, Any], *, pattern_key: str) -> str:
    for row in _rows(memory.get("patterns")):
        if _text(row.get("pattern_key")) == pattern_key:
            return "FIXED_RULE_ACTIVE" if row.get("converted_to_rule") is True else _upper(row.get("pattern_status"))
    return ""


def merge_experiment_result_into_memory(*, existing_memory: Mapping[str, Any] | None, result: Mapping[str, Any], checkpoint_run_id: str, rule_registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    memory = dict(existing_memory or {})
    fingerprint = _text(result.get("experiment_fingerprint"))
    origin_run = _text(result.get("origin_experiment_run_id"))
    if not fingerprint or not origin_run:
        raise ValueError("experiment result identity is required")
    if _origin_seen(memory, fingerprint=fingerprint, origin_run_id=origin_run):
        return memory
    return build_unified_memory_v2(existing_memory=memory, unified_learning_spine=build_experiment_spine(result), run_id=_text(checkpoint_run_id), rule_registry=rule_registry or {})


def replay_or_ingest_pending_experiment(*, pending_result: Mapping[str, Any], existing_memory: Mapping[str, Any] | None, checkpoint_run_id: str, exa_api_key: str, rule_registry: Mapping[str, Any] | None = None, provider_factory: ProviderFactory = _default_provider_factory, page_fetcher: PageFetcher = fetch_public_page) -> dict[str, Any]:
    pending = _mapping(pending_result)
    memory = dict(existing_memory or {})
    fingerprint = _text(pending.get("experiment_fingerprint"))
    origin_run = _text(pending.get("origin_experiment_run_id"))
    if not fingerprint or not origin_run:
        raise ValueError("pending search experiment has no stable identity")
    spec = _mapping(pending.get("spec"))
    pattern_key = _route_pattern_key(spec)

    if not _origin_seen(memory, fingerprint=fingerprint, origin_run_id=origin_run):
        merged = merge_experiment_result_into_memory(existing_memory=memory, result=pending, checkpoint_run_id=checkpoint_run_id, rule_registry=rule_registry)
        return {"schema_version": SCHEMA_VERSION, "status": "INGESTED_PENDING_ORIGIN", "network_search_executed": False, "experiment_fingerprint": fingerprint, "origin_experiment_run_id": origin_run, "memory": merged, **_safety()}

    status = _matching_route_status(memory, pattern_key=pattern_key)
    if status in {"PROVEN", "FIXED_RULE_ACTIVE"}:
        return {"schema_version": SCHEMA_VERSION, "status": "SKIPPED_ALREADY_PROVEN", "network_search_executed": False, "experiment_fingerprint": fingerprint, "route_pattern_status": status, "memory": memory, **_safety()}

    count = _fingerprint_execution_count(memory, fingerprint=fingerprint)
    max_exec = min(MAX_EXECUTIONS_PER_FINGERPRINT, max(1, int(spec.get("max_independent_executions") or MAX_EXECUTIONS_PER_FINGERPRINT)))
    if count >= max_exec:
        return {"schema_version": SCHEMA_VERSION, "status": "SKIPPED_EXECUTION_CAP_REACHED", "network_search_executed": False, "experiment_fingerprint": fingerprint, "execution_count": count, "execution_cap": max_exec, "memory": memory, **_safety()}

    rerun = execute_search_experiment_spec(spec, exa_api_key=exa_api_key, run_id=checkpoint_run_id, provider_factory=provider_factory, page_fetcher=page_fetcher)
    merged = merge_experiment_result_into_memory(existing_memory=memory, result=rerun, checkpoint_run_id=checkpoint_run_id, rule_registry=rule_registry)
    return {"schema_version": SCHEMA_VERSION, "status": "REEXECUTED_AND_INGESTED", "network_search_executed": True, "experiment_fingerprint": fingerprint, "execution_count": count + 1, "execution_cap": max_exec, "rerun_result": rerun, "memory": merged, **_safety()}


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
