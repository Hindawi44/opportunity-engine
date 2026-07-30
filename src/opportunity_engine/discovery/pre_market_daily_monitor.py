"""Bounded daily orchestration for pre-market clothing bankruptcy monitoring.

The monitor combines the existing clothing-bankruptcy lead ranking, targeted public
sale-channel search, and persistent case tracker. It is intentionally conservative:
failed or incomplete sources are recorded as ``SOURCE_TEMPORARILY_UNAVAILABLE``
and are excluded from the tracker update, so an outage cannot erase or downgrade a
previously known case state.

No page is opened automatically, FINN is never scraped, and no contact, bid,
purchase, reservation, payment, or automatic investment decision is performed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichmentCollector,
)
from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_PAGE_SIZE,
    KonkursAppClothingCollector,
)
from opportunity_engine.discovery.pre_market_case_tracker import (
    CaseSnapshot,
    CaseTrackerResult,
    observation_from_sale_channel_report,
    update_case_registry,
    write_case_tracker_artifacts,
)
from opportunity_engine.discovery.pre_market_clothing_leads import (
    MAX_REVIEW_LIMIT,
    PreMarketClothingPilotResult,
    build_pre_market_pilot,
    write_pre_market_artifacts,
)
from opportunity_engine.discovery.pre_market_sale_channel_search import (
    DEFAULT_RESULTS_PER_QUERY,
    MAX_QUERY_COUNT,
    MAX_RESULTS_PER_QUERY,
    SaleChannelSearchResult,
    run_sale_channel_search,
    write_sale_channel_artifacts,
)
from opportunity_engine.discovery.search_provider import SearchProvider

SOURCE_COMPLETE = "COMPLETE"
SOURCE_TEMPORARILY_UNAVAILABLE = "SOURCE_TEMPORARILY_UNAVAILABLE"
MONITOR_SCHEMA_VERSION = "pre-market-daily-monitor-1.0"
SOURCE_STATUS_SCHEMA_VERSION = "pre-market-source-status-1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _error_messages(errors: object) -> tuple[str, ...]:
    if not isinstance(errors, (list, tuple)):
        return ()
    messages: list[str] = []
    for error in errors:
        if isinstance(error, Mapping):
            text = _compact(error.get("error"))
        else:
            text = _compact(error)
        if text:
            messages.append(text)
    return tuple(messages)


@dataclass(frozen=True, slots=True)
class CaseSourceAttempt:
    estate_orgnr: str
    debtor_name: str
    source_status: str
    scan_complete: bool
    requests_made: int
    raw_hits: int
    errors: tuple[str, ...] = ()
    search_result: SaleChannelSearchResult | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "estate_orgnr": self.estate_orgnr,
            "debtor_name": self.debtor_name,
            "source_status": self.source_status,
            "scan_complete": self.scan_complete,
            "requests_made": self.requests_made,
            "raw_hits": self.raw_hits,
            "error_count": len(self.errors),
            "errors": list(self.errors),
            "tracker_observation_applied": self.scan_complete,
            "automatic_page_open": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


@dataclass(frozen=True, slots=True)
class PreMarketDailyMonitorResult:
    captured_at: str
    pilot: PreMarketClothingPilotResult
    tracker: CaseTrackerResult
    case_limit: int
    results_per_query: int
    attempts: tuple[CaseSourceAttempt, ...]

    @property
    def completed_attempts(self) -> tuple[CaseSourceAttempt, ...]:
        return tuple(attempt for attempt in self.attempts if attempt.scan_complete)

    @property
    def unavailable_attempts(self) -> tuple[CaseSourceAttempt, ...]:
        return tuple(attempt for attempt in self.attempts if not attempt.scan_complete)

    @property
    def allocated_query_budget(self) -> int:
        return len(self.pilot.review_top) * MAX_QUERY_COUNT

    @property
    def requests_made(self) -> int:
        return sum(attempt.requests_made for attempt in self.attempts)

    @property
    def monitor_complete(self) -> bool:
        return self.pilot.scan_complete and not self.unavailable_attempts

    @property
    def source_status(self) -> str:
        return SOURCE_COMPLETE if self.monitor_complete else SOURCE_TEMPORARILY_UNAVAILABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MONITOR_SCHEMA_VERSION,
            "captured_at": self.captured_at,
            "source_status": self.source_status,
            "monitor_complete": self.monitor_complete,
            "lead_scan_complete": self.pilot.scan_complete,
            "lead_scan_error_count": len(self.pilot.errors),
            "ranked_lead_count": len(self.pilot.leads),
            "selected_case_count": len(self.pilot.review_top),
            "attempted_case_count": len(self.attempts),
            "completed_case_count": len(self.completed_attempts),
            "temporarily_unavailable_case_count": len(self.unavailable_attempts),
            "case_limit": self.case_limit,
            "queries_per_case": MAX_QUERY_COUNT,
            "results_per_query": self.results_per_query,
            "allocated_query_budget": self.allocated_query_budget,
            "requests_made": self.requests_made,
            "retained_case_count": len(self.tracker.cases),
            "material_change_count": len(self.tracker.changes),
            "alert_count": len(self.tracker.alerts),
            "verified_active_inventory_sale_count": len(self.tracker.verified_cases),
            "commercial_top5_count": len(self.tracker.verified_cases[:5]),
            "incomplete_sources_are_treated_as_no_sale": False,
            "automatic_page_open": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }

    def source_status_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_STATUS_SCHEMA_VERSION,
            "captured_at": self.captured_at,
            "lead_source": {
                "name": "Konkurs.app clothing bankruptcy API",
                "source_status": (
                    SOURCE_COMPLETE
                    if self.pilot.scan_complete
                    else SOURCE_TEMPORARILY_UNAVAILABLE
                ),
                "scan_complete": self.pilot.scan_complete,
                "error_count": len(self.pilot.errors),
                "errors": list(self.pilot.errors),
            },
            "sale_channel_searches": [attempt.to_dict() for attempt in self.attempts],
            "failed_or_incomplete_observations_applied_to_registry": False,
        }


CollectorFactory = Callable[[], KonkursAppClothingCollector]
EnrichmentFactory = Callable[[str], EstateManagerEnrichmentCollector]
ProviderFactory = Callable[[str], SearchProvider]
SearchRunner = Callable[..., SaleChannelSearchResult]


def run_pre_market_daily_monitor(
    *,
    api_key: str,
    previous_cases: Mapping[str, CaseSnapshot],
    case_limit: int = 10,
    results_per_query: int = DEFAULT_RESULTS_PER_QUERY,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    freshness: str | None = "py",
    collector_factory: CollectorFactory | None = None,
    enrichment_factory: EnrichmentFactory | None = None,
    provider_factory: ProviderFactory | None = None,
    search_runner: SearchRunner = run_sale_channel_search,
    captured_at: str | None = None,
) -> PreMarketDailyMonitorResult:
    """Run one bounded monitoring cycle and preserve state on source failure."""
    key = api_key.strip()
    if not key:
        raise ValueError("BRAVE_SEARCH_API_KEY is required")
    if not 1 <= case_limit <= MAX_REVIEW_LIMIT:
        raise ValueError(f"case_limit must be between 1 and {MAX_REVIEW_LIMIT}")
    if not 1 <= results_per_query <= MAX_RESULTS_PER_QUERY:
        raise ValueError(
            f"results_per_query must be between 1 and {MAX_RESULTS_PER_QUERY}"
        )

    collector_factory = collector_factory or (
        lambda: KonkursAppClothingCollector(
            lookback_days=lookback_days,
            page_size=page_size,
        )
    )
    enrichment_factory = enrichment_factory or (
        lambda orgnr: EstateManagerEnrichmentCollector(estate_orgnr=orgnr)
    )
    provider_factory = provider_factory or (
        lambda token: BraveSearchProvider(
            token,
            freshness=freshness,
            extra_snippets=True,
            operators=True,
        )
    )

    collection = collector_factory().collect()
    pilot = build_pre_market_pilot(collection, review_limit=case_limit)
    provider = provider_factory(key)

    attempts: list[CaseSourceAttempt] = []
    observations = []

    for ranked_lead in pilot.review_top:
        lead = ranked_lead.source_lead
        try:
            enrichment = enrichment_factory(lead.estate_orgnr).collect()
            search_result = search_runner(
                enrichment,
                provider,
                results_per_query=results_per_query,
            )
        except Exception as exc:  # one estate must not erase the full registry
            attempts.append(
                CaseSourceAttempt(
                    estate_orgnr=lead.estate_orgnr,
                    debtor_name=lead.debtor_name,
                    source_status=SOURCE_TEMPORARILY_UNAVAILABLE,
                    scan_complete=False,
                    requests_made=0,
                    raw_hits=0,
                    errors=(_compact(exc) or exc.__class__.__name__,),
                )
            )
            continue

        errors = _error_messages(search_result.errors)
        if not search_result.scan_complete:
            attempts.append(
                CaseSourceAttempt(
                    estate_orgnr=lead.estate_orgnr,
                    debtor_name=lead.debtor_name,
                    source_status=SOURCE_TEMPORARILY_UNAVAILABLE,
                    scan_complete=False,
                    requests_made=search_result.requests_made,
                    raw_hits=search_result.raw_hits,
                    errors=errors or ("targeted sale-channel scan incomplete",),
                    search_result=search_result,
                )
            )
            continue

        attempts.append(
            CaseSourceAttempt(
                estate_orgnr=lead.estate_orgnr,
                debtor_name=lead.debtor_name,
                source_status=SOURCE_COMPLETE,
                scan_complete=True,
                requests_made=search_result.requests_made,
                raw_hits=search_result.raw_hits,
                errors=errors,
                search_result=search_result,
            )
        )
        observations.append(
            observation_from_sale_channel_report(
                search_result.to_dict(),
                source_report=(
                    f"daily-monitor:{lead.estate_orgnr}:{search_result.captured_at}"
                ),
            )
        )

    timestamp = captured_at or _now()
    tracker = update_case_registry(
        previous_cases,
        observations,
        captured_at=timestamp,
    )
    return PreMarketDailyMonitorResult(
        captured_at=timestamp,
        pilot=pilot,
        tracker=tracker,
        case_limit=case_limit,
        results_per_query=results_per_query,
        attempts=tuple(attempts),
    )


def write_pre_market_daily_monitor_artifacts(
    result: PreMarketDailyMonitorResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write durable registry outputs plus bounded audit artifacts."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    lead_paths = write_pre_market_artifacts(result.pilot, target / "lead-scan")
    tracker_paths = write_case_tracker_artifacts(result.tracker, target)

    for attempt in result.completed_attempts:
        if attempt.search_result is None:
            continue
        write_sale_channel_artifacts(
            attempt.search_result,
            target / "sale-channel" / attempt.estate_orgnr,
        )

    monitor_status_path = target / "pre-market-daily-monitor-status.json"
    source_status_path = target / "pre-market-source-status.json"
    summary_path = target / "daily-monitor-summary.txt"

    monitor_status_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    source_status_path.write_text(
        json.dumps(result.source_status_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "Pre-market daily clothing monitor",
        f"Source status: {result.source_status}",
        f"Lead scan complete: {result.pilot.scan_complete}",
        f"Ranked leads: {len(result.pilot.leads)}",
        f"Selected cases: {len(result.pilot.review_top)}",
        f"Completed case scans: {len(result.completed_attempts)}",
        f"Temporarily unavailable case scans: {len(result.unavailable_attempts)}",
        f"Allocated query budget: {result.allocated_query_budget}",
        f"Requests made: {result.requests_made}",
        f"Cases retained: {len(result.tracker.cases)}",
        f"Material changes: {len(result.tracker.changes)}",
        f"Alert-worthy changes: {len(result.tracker.alerts)}",
        f"Verified active inventory sales: {len(result.tracker.verified_cases)}",
        "Incomplete sources treated as no sale: false",
        "Automatic page open/contact/bid/purchase/payment: false",
        "",
    ]
    for attempt in result.attempts:
        lines.append(
            f"- {attempt.source_status} | {attempt.debtor_name} | "
            f"estate {attempt.estate_orgnr} | requests {attempt.requests_made}"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "registry": tracker_paths["registry"],
        "changes": tracker_paths["changes"],
        "alerts": tracker_paths["alerts"],
        "operator_actions": tracker_paths["operator_actions"],
        "commercial_top5": tracker_paths["commercial_top5"],
        "operator_summary": tracker_paths["summary"],
        "monitor_status": monitor_status_path,
        "source_status": source_status_path,
        "daily_summary": summary_path,
        "lead_report": lead_paths["report"],
        "lead_review_top": lead_paths["review_top"],
    }
