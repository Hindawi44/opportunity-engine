"""Adaptive follow-up for verified SOURCE_GAP misses.

A source gap means a downstream exact-page verifier proved a real bulk-clothing
opportunity that the canonical source collector failed to surface.  On later
runs this wrapper reserves the front of the *existing* signal-follow-up case
budget for a source-domain-bound query using the known company identity.  It
then gives the remaining case budget to the established entity-memory/current-
signal follow-up engine.

The wrapper does not create an additional case budget, does not treat search
hits as proof, and does not re-add the already-known ground-truth URL as a new
lead.  Any new exact-item lead still flows through the existing source-specific
verification stage after this report is written.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.signal_follow_up_continuity import (
    ProviderFactory,
    _compact,
    _run_memory_plan,
    _top_lead,
    _write_json,
    run_signal_follow_up_engine_with_continuity,
    write_signal_follow_up_engine_with_continuity,
)
from opportunity_engine.discovery.signal_follow_up_engine import (
    DECISION_OWNER,
    DEFAULT_MAX_CASES,
    DEFAULT_RESULTS_PER_CASE,
    MAX_CASES,
    OUTPUT_FILENAME,
    _attach_to_domain_brief,
)
from opportunity_engine.missed_opportunity_learning import (
    MissedOpportunityCase,
    load_missed_opportunity_memory,
)

SCHEMA_VERSION = "source-gap-adaptive-followup-1.0"
MEMORY_RELATIVE_PATH = Path("learning/missed-opportunities.json")
_SITE_RE = re.compile(r"(?:^|\s)site:(?P<domain>[^\s()]+)", re.I)

_MARKET_QUERY_TERMS = {
    "NO": "(varelager OR restlager OR vareparti OR lagersalg OR avviklingssalg OR auksjon)",
    "SE": "(varulager OR restlager OR lagerparti OR utförsäljning OR konkursauktion OR auktion)",
    "DE": "(Warenbestand OR Lagerbestand OR Warenposten OR Lagerauflösung OR Versteigerung OR Insolvenzauktion)",
}


def _active_source_gap_cases(
    cases: Sequence[MissedOpportunityCase],
) -> list[MissedOpportunityCase]:
    active: list[MissedOpportunityCase] = []
    for case in cases:
        diagnosed = case if case.root_cause else case.with_diagnosis()
        if diagnosed.root_cause != "SOURCE_GAP":
            continue
        if diagnosed.learning_status == "RECOVERED" and not diagnosed.repeat_miss:
            continue
        if not diagnosed.stock_proven:
            continue
        active.append(diagnosed)
    active.sort(
        key=lambda case: (
            not case.repeat_miss,
            case.observed_at,
            case.case_id,
        )
    )
    return active


def _source_domain(case: MissedOpportunityCase) -> str:
    try:
        parts = urlsplit(case.ground_truth_url)
    except ValueError:
        return ""
    if parts.scheme.casefold() != "https" or not parts.hostname:
        return ""
    return parts.hostname.casefold().rstrip(".")


def _source_gap_query(case: MissedOpportunityCase, domain: str) -> str:
    company = _compact(case.ground_truth_company).replace('"', "")
    if not company or not domain:
        return ""
    terms = _MARKET_QUERY_TERMS.get(
        case.market_code.upper(),
        "(inventory OR stock OR liquidation OR auction)",
    )
    return f'site:{domain} "{company}" {terms}'


def build_source_gap_follow_up_plan(
    cases: Sequence[MissedOpportunityCase],
    *,
    max_cases: int,
) -> list[dict[str, Any]]:
    """Build deterministic source-domain fallbacks for active SOURCE_GAP cases."""
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    if bounded == 0:
        return []
    rows: list[dict[str, Any]] = []
    for case in _active_source_gap_cases(cases):
        domain = _source_domain(case)
        query = _source_gap_query(case, domain)
        if not query:
            continue
        target = _compact(case.ground_truth_company)
        row = {
            "case_id": case.case_id,
            "case_title": target,
            "target_label": target,
            "country": case.market_code.upper(),
            "query": query,
            "follow_up_stage": "SOURCE_GAP_DOMAIN_FALLBACK",
            "follow_up_stage_index": 0,
            "source_gap_feedback": True,
            "source_gap_root_cause": "SOURCE_GAP",
            "source_gap_repeat_miss": case.repeat_miss,
            "source_gap_domain": domain,
            "source_gap_ground_truth_url": case.ground_truth_url,
            "explicit_linked_commercial_case_ids": [],
            "_source_case": {
                "case_id": case.case_id,
                "_follow_up_market": case.market_code.upper(),
                "_follow_up_target": target,
                "source_urls": [case.ground_truth_url],
            },
        }
        rows.append(row)
        if len(rows) >= bounded:
            break
    return rows


class _DomainBoundProvider:
    """Filter provider output to the site: domain carried by the adaptive query."""

    name = "Domain-bound Brave Search"

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        hits = list(self._provider.search(query, count=count))
        match = _SITE_RE.search(query)
        if match is None:
            return []
        expected = match.group("domain").casefold().rstrip(".")
        accepted: list[SearchHit] = []
        for hit in hits:
            try:
                host = (urlsplit(hit.url).hostname or "").casefold().rstrip(".")
            except ValueError:
                continue
            if host == expected or host.endswith(f".{expected}"):
                accepted.append(hit)
        return accepted


def _domain_bound_factory(
    provider_factory: ProviderFactory | None,
) -> ProviderFactory:
    if provider_factory is None:
        # _run_memory_plan already owns the project's default provider factory;
        # use a lazy import through the same default only when a source-gap query
        # actually reaches the Brave step.
        from opportunity_engine.discovery.signal_follow_up_engine import (  # noqa: PLC0415
            _default_provider_factory,
        )

        factory = _default_provider_factory
    else:
        factory = provider_factory

    def build(market_code: str, api_key: str) -> SearchProvider:
        return _DomainBoundProvider(factory(market_code, api_key))

    return build


def _combined_status(
    *,
    rows: Sequence[Mapping[str, Any]],
    api_key: str,
    search_requests: int,
    errors: int,
) -> str:
    if not rows:
        return "VALID_ZERO_NO_FOLLOW_UP_CASES"
    if not api_key:
        return "SKIPPED_NO_API_KEY"
    if errors:
        return "PARTIAL_SUCCESS" if search_requests > errors else "FAILED"
    return "SUCCESS"


def _merge_reports(
    source_gap_result: Mapping[str, Any],
    base_report: Mapping[str, Any],
    *,
    source_gap_case_count: int,
    source_gap_selected_count: int,
    follow_up_case_budget: int,
    api_key: str,
) -> dict[str, Any]:
    rows = [
        *[dict(row) for row in source_gap_result.get("cases") or [] if isinstance(row, Mapping)],
        *[dict(row) for row in base_report.get("cases") or [] if isinstance(row, Mapping)],
    ]
    searched = int(source_gap_result.get("search_request_count") or 0) + int(
        base_report.get("search_request_count") or 0
    )
    errors = int(source_gap_result.get("search_error_count") or 0) + int(
        base_report.get("search_error_count") or 0
    )
    lead_count = int(source_gap_result.get("commercial_lead_count") or 0) + int(
        base_report.get("commercial_lead_count") or 0
    )
    link_count = int(
        source_gap_result.get("explicit_commercial_case_link_count") or 0
    ) + int(base_report.get("explicit_commercial_case_link_count") or 0)

    report = dict(base_report)
    report.update(
        {
            "source_gap_adaptive_schema_version": SCHEMA_VERSION,
            "status": _combined_status(
                rows=rows,
                api_key=api_key,
                search_requests=searched,
                errors=errors,
            ),
            "purpose": "PRIORITIZE_PROVEN_SOURCE_GAPS_WITHIN_EXISTING_FOLLOW_UP_BUDGET",
            "follow_up_case_budget": follow_up_case_budget,
            "source_gap_case_count": source_gap_case_count,
            "source_gap_selected_count": source_gap_selected_count,
            "source_gap_search_request_count": int(
                source_gap_result.get("search_request_count") or 0
            ),
            "source_gap_commercial_lead_count": int(
                source_gap_result.get("commercial_lead_count") or 0
            ),
            "eligible_follow_up_case_count": source_gap_case_count
            + int(base_report.get("eligible_follow_up_case_count") or 0),
            "selected_case_count": len(rows),
            "search_request_count": searched,
            "search_error_count": errors,
            "commercial_lead_count": lead_count,
            "explicit_commercial_case_link_count": link_count,
            "top_follow_up_lead": _top_lead(rows),
            "cases": rows,
            "source_gap_priority_before_generic_follow_up": True,
            "source_gap_same_domain_required": True,
            "source_gap_known_ground_truth_url_excluded": True,
            "source_gap_uses_existing_case_budget": True,
            "search_result_is_not_commercial_proof": True,
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
            "decision_owner": DECISION_OWNER,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    )
    return report


def run_source_gap_adaptive_followup_with_continuity(
    cases_report: Mapping[str, Any],
    *,
    entity_signals: Sequence[Mapping[str, Any]],
    source_gap_cases: Sequence[MissedOpportunityCase],
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
    results_per_case: int = DEFAULT_RESULTS_PER_CASE,
) -> dict[str, Any]:
    """Spend the existing case budget on SOURCE_GAP first, then normal follow-up."""
    env = environment if environment is not None else os.environ
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    active_gaps = _active_source_gap_cases(source_gap_cases)
    plan = build_source_gap_follow_up_plan(active_gaps, max_cases=bounded)
    source_result = _run_memory_plan(
        plan,
        environment=env,
        provider_factory=_domain_bound_factory(provider_factory),
        results_per_case=results_per_case,
    )
    remaining = max(0, bounded - len(plan))
    base = run_signal_follow_up_engine_with_continuity(
        cases_report,
        entity_signals=entity_signals,
        environment=env,
        provider_factory=provider_factory,
        observed_at=observed_at,
        max_cases=remaining,
        results_per_case=results_per_case,
    )
    return _merge_reports(
        source_result,
        base,
        source_gap_case_count=len(active_gaps),
        source_gap_selected_count=len(plan),
        follow_up_case_budget=bounded,
        api_key=_compact(env.get("BRAVE_SEARCH_API_KEY")),
    )


def write_source_gap_adaptive_followup_with_continuity(
    output_dir: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
    results_per_case: int = DEFAULT_RESULTS_PER_CASE,
) -> dict[str, Any]:
    """Load durable SOURCE_GAP memory and wrap the existing continuity writer."""
    directory = Path(output_dir)
    env = environment if environment is not None else os.environ
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    input_root = Path(
        _compact(env.get("INPUT_ROOT"))
        or (directory.parent / "multi-market-inputs").as_posix()
    )
    source_gap_cases = load_missed_opportunity_memory(
        input_root / MEMORY_RELATIVE_PATH
    )
    active_gaps = _active_source_gap_cases(source_gap_cases)
    plan = build_source_gap_follow_up_plan(active_gaps, max_cases=bounded)
    source_result = _run_memory_plan(
        plan,
        environment=env,
        provider_factory=_domain_bound_factory(provider_factory),
        results_per_case=results_per_case,
    )
    remaining = max(0, bounded - len(plan))
    base = write_signal_follow_up_engine_with_continuity(
        directory,
        environment=env,
        provider_factory=provider_factory,
        observed_at=observed_at,
        max_cases=remaining,
        results_per_case=results_per_case,
    )
    report = _merge_reports(
        source_result,
        base,
        source_gap_case_count=len(active_gaps),
        source_gap_selected_count=len(plan),
        follow_up_case_budget=bounded,
        api_key=_compact(env.get("BRAVE_SEARCH_API_KEY")),
    )
    _write_json(directory / OUTPUT_FILENAME, report)
    _attach_to_domain_brief(directory, report)
    return report
