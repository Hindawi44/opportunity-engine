"""Scheduled direct discovery driven only by explicitly promoted learned queries.

This module closes the learning loop for the canonical daily operator. A term
may reach this collector only through the active runtime overlay, which itself is
produced by the explicit promotion gate. Search results are not opportunities:
each candidate public page must independently prove a concrete company closure
and inventory liquidation before a canonical REQUIRES_VERIFICATION record is
written for the pre-checkpoint source set.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.automatic_query_gap_miss_scout import (
    PublicPage,
    _verify_closure_liquidation_page,
    fetch_public_page,
)
from opportunity_engine.cost_guard import manual_paid_brave_block_reason
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learned_query_overlay import load_learned_query_overlay
from opportunity_engine.unified_models import (
    EvaluationStatus,
    Evidence,
    ListingStatus,
    MarketSignal,
    MissingInformation,
    OpportunityRecord,
    WorkflowStatus,
)

SCHEMA_VERSION = "promoted-learned-core-discovery-1.0"
SOURCE_NAME = "Promoted learned Core discovery"
MARKET_CODE = "NO"
DEFAULT_RESULTS_PER_QUERY = 10
MAX_RESULTS_PER_QUERY = 10
# The paid Brave budget remains one request per promoted term. Exact-page GETs
# are a separate verification budget and may inspect the complete returned hit
# window so duplicate/noisy early ranks cannot hide independently verifiable
# liquidation pages at later ranks.
DEFAULT_MAX_PAGES = 10
MAX_PAGES = 10
DEFAULT_MAX_TERMS = 1
MAX_TERMS = 2
_OVERLAY_ENV = "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH"
_DEFAULT_OVERLAY_PATH = Path("learning") / "active-keyword-overlay.json"

SearchCallback = Callable[[str], Sequence[SearchHit]]
PageFetcher = Callable[[str], PublicPage]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: object) -> str:
    return " ".join(str(value or "").casefold().split()).strip()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _overlay_path(environment: Mapping[str, str]) -> Path:
    configured = _compact(environment.get(_OVERLAY_ENV))
    return Path(configured) if configured else _DEFAULT_OVERLAY_PATH


def _promoted_terms(
    path: Path,
    *,
    market_code: str = MARKET_CODE,
) -> tuple[list[str], str | None]:
    if not path.exists():
        return [], None
    try:
        overlay = load_learned_query_overlay(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [], f"{type(exc).__name__}: {exc}"

    if (
        overlay.get("promotion_gate_enforced") is not True
        or overlay.get("automatic_query_activation") is not False
    ):
        return [], "UNSAFE_ACTIVE_OVERLAY_METADATA"
    markets = overlay.get("markets")
    if not isinstance(markets, Mapping):
        return [], "UNSAFE_ACTIVE_OVERLAY_MARKETS"
    rows = markets.get(market_code.upper())
    if not isinstance(rows, list):
        return [], None

    terms: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("source_verdict") or "").strip().upper() != "PROVEN":
            continue
        if str(raw.get("promotion_status") or "").strip().upper() != "PROMOTED":
            continue
        if (
            str(raw.get("activation_source") or "").strip().upper()
            != "EXPLICIT_PROMOTION"
        ):
            continue
        term = _fold(raw.get("term"))
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
    return terms, None


def _exact_query(term: str) -> str:
    safe = _compact(term).replace('"', "")
    return f'"{safe}"' if safe else ""


def _default_search(api_key: str, *, results_per_query: int) -> SearchCallback:
    provider = BraveSearchProvider(
        api_key,
        country=MARKET_CODE,
        freshness=None,
        extra_snippets=True,
        operators=True,
    )

    def search(query: str) -> Sequence[SearchHit]:
        return provider.search(query, count=results_per_query)

    return search


def _record_from_verified_page(
    *,
    hit: SearchHit,
    proof: Mapping[str, Any],
    term: str,
    query: str,
    rank: int,
    observed_at: datetime,
) -> OpportunityRecord:
    canonical_url = _compact(proof.get("canonical_url"))
    company = _compact(proof.get("company"))
    digest = sha256(canonical_url.encode("utf-8")).hexdigest()[:24]
    opportunity_id = f"learned-core:no:{digest}"
    title = _compact(hit.title) or f"{company} inventory liquidation"
    evidence_text = _compact(proof.get("evidence_text"))
    closure_markers = list(proof.get("closure_markers") or [])
    liquidation_markers = list(proof.get("liquidation_markers") or [])

    return OpportunityRecord(
        opportunity_id=opportunity_id,
        market_code=MARKET_CODE,
        domain="GENERAL_COMMERCIAL_LIQUIDATION",
        category="BUSINESS_STOCK_LIQUIDATION",
        title=title[:1000],
        source_provider=SOURCE_NAME,
        source_url=canonical_url,
        listing_status=ListingStatus.UNKNOWN,
        evaluation_status=EvaluationStatus.REQUIRES_VERIFICATION,
        workflow_status=WorkflowStatus.REQUIRES_VERIFICATION,
        scenario="STOCK_LIQUIDATION",
        company_name=company or None,
        inventory_type="BUSINESS_INVENTORY",
        currency="NOK",
        discovered_at=observed_at,
        identity_stable=True,
        verified=True,
        analysis_eligible=False,
        top5_eligible=False,
        market_signals=[
            MarketSignal(
                signal_type="BUSINESS_CLOSURE",
                value=f"Verified closure markers: {', '.join(closure_markers)}"[:500],
                source=SOURCE_NAME,
                observed_at=observed_at,
                confidence=0.90,
            ),
            MarketSignal(
                signal_type="WAREHOUSE_SURPLUS",
                value=(
                    f"Verified inventory-liquidation markers: {', '.join(liquidation_markers)}"
                )[:500],
                source=SOURCE_NAME,
                observed_at=observed_at,
                confidence=0.90,
            ),
        ],
        evidence=[
            Evidence(
                evidence_type="PROMOTED_LEARNED_QUERY_SEARCH_HIT",
                value=(f"{_compact(hit.title)} {_compact(hit.description)}")[:4000],
                source_url=canonical_url,
                captured_at=observed_at,
                verified=False,
                metadata={
                    "query": query,
                    "learned_term": term,
                    "source_rank": rank,
                    "provider": _compact(hit.provider) or "Brave Search",
                },
            ),
            Evidence(
                evidence_type="VERIFIED_PUBLIC_CLOSURE_LIQUIDATION_PAGE",
                value=evidence_text or title,
                source_url=canonical_url,
                captured_at=observed_at,
                verified=True,
                metadata={
                    "learned_term": term,
                    "closure_markers": closure_markers,
                    "liquidation_markers": liquidation_markers,
                    "source_page_verified": True,
                    "closure_verified": True,
                    "inventory_liquidation_verified": True,
                },
            ),
        ],
        missing_information=[
            MissingInformation(
                field_name="current_sale_status",
                reason="Exact page proves closure and inventory liquidation, but current sale availability still needs human confirmation.",
                required_for="commercial decision",
            ),
            MissingInformation(
                field_name="quantity",
                reason="Exact sellable quantity is not proven by the verified page.",
                required_for="commercial analysis",
            ),
            MissingInformation(
                field_name="price",
                reason="Final payable stock price is not proven by the verified page.",
                required_for="commercial analysis",
            ),
            MissingInformation(
                field_name="logistics",
                reason="Pickup, freight, and delivery basis are not yet proven.",
                required_for="commercial analysis",
            ),
        ],
        metadata={
            "lifecycle_reason_code": "PROMOTED_LEARNED_QUERY_VERIFIED_CLOSURE_STOCK_REQUIRES_COMMERCIAL_DETAILS",
            "learned_term": term,
            "promotion_status": "PROMOTED",
            "activation_source": "EXPLICIT_PROMOTION",
            "discovery_query": query,
            "source_rank": rank,
            "source_page_verified": True,
            "closure_verified": True,
            "inventory_liquidation_verified": True,
            "closure_markers": closure_markers,
            "liquidation_markers": liquidation_markers,
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        },
    )


def _write_source_artifacts(
    output_dir: Path,
    *,
    records: Sequence[OpportunityRecord],
    report: Mapping[str, Any],
    generated_at: datetime,
) -> None:
    rows = [record.model_dump(mode="json") for record in records]
    _write_json(output_dir / "search-run-report.json", dict(report))
    _write_json(output_dir / "all-discovered-candidates.json", rows)
    _write_json(output_dir / "discovery-top5.json", [])
    _write_json(
        output_dir / "unified-opportunity-report.json",
        {
            "schema_version": "1.1",
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "market_code": MARKET_CODE,
            "currency": "NOK",
            "record_count": len(rows),
            "records": rows,
            "conversion_error_count": 0,
            "conversion_errors": [],
        },
    )


def collect_promoted_learned_core_opportunities(
    output_dir: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    search_override: SearchCallback | None = None,
    fetch_page: PageFetcher = fetch_public_page,
    observed_at: datetime | None = None,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_terms: int = DEFAULT_MAX_TERMS,
) -> dict[str, Any]:
    """Run a bounded promoted-query source and write canonical source artifacts."""
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError("results_per_query must be between 1 and 10")
    if not 0 <= max_pages <= MAX_PAGES:
        raise ValueError(f"max_pages must be between 0 and {MAX_PAGES}")
    if not 1 <= max_terms <= MAX_TERMS:
        raise ValueError(f"max_terms must be between 1 and {MAX_TERMS}")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ
    destination = Path(output_dir)
    overlay_path = _overlay_path(env)
    terms, overlay_error = _promoted_terms(overlay_path)
    selected_terms = terms[:max_terms]
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY")) or _compact(env.get("BRAVE_API_KEY"))
    cost_block = manual_paid_brave_block_reason(env)

    request_count = 0
    page_request_count = 0
    raw_hit_count = 0
    records_by_url: dict[str, OpportunityRecord] = {}
    errors: list[dict[str, str]] = []
    applied_terms: list[str] = []

    if selected_terms and cost_block and search_override is None:
        status = "SKIPPED_COST_GUARD"
    elif selected_terms and not api_key and search_override is None:
        status = "BLOCKED_CONFIGURATION"
    else:
        status = "SUCCESS"
        search = search_override or _default_search(
            api_key,
            results_per_query=results_per_query,
        )
        for term in selected_terms:
            query = _exact_query(term)
            if not query:
                continue
            applied_terms.append(term)
            request_count += 1
            try:
                hits = list(search(query))[:results_per_query]
            except Exception as exc:
                errors.append(
                    {
                        "term": term,
                        "error_type": type(exc).__name__,
                        "error": _compact(exc)[:500],
                    }
                )
                continue
            raw_hit_count += len(hits)
            for rank, hit in enumerate(hits, start=1):
                if not isinstance(hit, SearchHit) or page_request_count >= max_pages:
                    continue
                page_request_count += 1
                try:
                    page = fetch_page(hit.url)
                    proof = _verify_closure_liquidation_page(page)
                except Exception as exc:
                    errors.append(
                        {
                            "term": term,
                            "error_type": type(exc).__name__,
                            "error": _compact(exc)[:500],
                        }
                    )
                    continue
                if proof is None:
                    continue
                proof_terms = {_fold(item) for item in proof.get("query_gap_terms") or []}
                if _fold(term) not in proof_terms:
                    continue
                canonical_url = _compact(proof.get("canonical_url"))
                if not canonical_url:
                    continue
                records_by_url[canonical_url] = _record_from_verified_page(
                    hit=hit,
                    proof=proof,
                    term=term,
                    query=query,
                    rank=rank,
                    observed_at=now,
                )
        if errors and not records_by_url and request_count:
            status = "PARTIAL_RETRIEVAL"

    records = [records_by_url[key] for key in sorted(records_by_url)]
    if not selected_terms and not overlay_error:
        status = "VALID_ZERO"
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": now.isoformat(),
        "source_name": SOURCE_NAME,
        "market_code": MARKET_CODE,
        "overlay_path": overlay_path.as_posix(),
        "overlay_error": overlay_error,
        "active_terms": terms,
        "applied_terms": applied_terms,
        "max_terms": max_terms,
        "results_per_query": results_per_query,
        "request_count": request_count,
        "raw_hit_count": raw_hit_count,
        "page_request_count": page_request_count,
        "verified_opportunity_count": len(records),
        "errors": errors,
        "cost_guard_reason": cost_block,
        "currency_conversion_performed": False,
        "promotion_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_source_artifacts(
        destination,
        records=records,
        report=report,
        generated_at=now,
    )
    return report
