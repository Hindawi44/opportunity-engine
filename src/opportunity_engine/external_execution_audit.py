"""Trace Brave execution and adapter acceptance without changing research logic."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchExecutionTrace:
    query: str
    request_count_before: int
    request_count_after: int
    cache_hits_before: int
    cache_hits_after: int
    response_count: int
    https_result_count: int
    explicit_price_result_count: int
    title_result_count: int
    error: str | None = None


class TracingSearchProvider:
    """Transparent provider wrapper that records live Brave execution facts."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.traces: list[SearchExecutionTrace] = []
        self._responses: list[Any] = []

    @staticmethod
    def _explicit_price_count(response: Any) -> int:
        rows = response if isinstance(response, list) else []
        return sum(
            isinstance(item, dict)
            and isinstance(item.get("price_nok"), (int, float))
            and not isinstance(item.get("price_nok"), bool)
            for item in rows
        )

    def search(self, query: str, **kwargs: Any) -> Any:
        before_requests = int(getattr(self.provider, "request_count", 0))
        before_cache = int(getattr(self.provider, "cache_hits", 0))
        try:
            response = self.provider.search(query, **kwargs)
        except Exception as exc:
            self.traces.append(SearchExecutionTrace(
                query=query,
                request_count_before=before_requests,
                request_count_after=int(getattr(self.provider, "request_count", before_requests)),
                cache_hits_before=before_cache,
                cache_hits_after=int(getattr(self.provider, "cache_hits", before_cache)),
                response_count=0,
                https_result_count=0,
                explicit_price_result_count=0,
                title_result_count=0,
                error=str(exc),
            ))
            self._responses.append(None)
            raise

        rows = response if isinstance(response, list) else []
        self.traces.append(SearchExecutionTrace(
            query=query,
            request_count_before=before_requests,
            request_count_after=int(getattr(self.provider, "request_count", before_requests)),
            cache_hits_before=before_cache,
            cache_hits_after=int(getattr(self.provider, "cache_hits", before_cache)),
            response_count=len(rows),
            https_result_count=sum(
                isinstance(item, dict) and str(item.get("url") or "").startswith("https://")
                for item in rows
            ),
            explicit_price_result_count=self._explicit_price_count(response),
            title_result_count=sum(
                isinstance(item, dict) and bool(str(item.get("title") or "").strip())
                for item in rows
            ),
        ))
        self._responses.append(response)
        return response

    def refresh_price_counts(self, start: int = 0) -> None:
        """Recount prices after adapters enrich the same result dictionaries in place."""
        upper = min(len(self.traces), len(self._responses))
        for index in range(max(0, start), upper):
            response = self._responses[index]
            if response is None:
                continue
            count = self._explicit_price_count(response)
            if count != self.traces[index].explicit_price_result_count:
                self.traces[index] = replace(
                    self.traces[index],
                    explicit_price_result_count=count,
                )


@dataclass(frozen=True, slots=True)
class CandidateExecutionAudit:
    opportunity_id: str
    research_rank: int
    selected_for_external_research: bool
    brave_called: bool
    search_trace_count: int
    searches_executed: int
    searches_skipped: int
    needs_detected: int
    response_results_total: int
    explicit_price_results_total: int
    evidence_created: int
    evidence_updated: int
    comparables_found: int
    buyers_found: int
    scenarios_regenerated: bool
    external_loop_errors: tuple[str, ...]
    external_loop_events: tuple[str, ...]
    diagnosis: tuple[str, ...]
    search_traces: tuple[SearchExecutionTrace, ...]


@dataclass(frozen=True, slots=True)
class ExternalExecutionAuditReport:
    selected_candidates: int
    audited_candidates: int
    brave_request_count: int
    brave_cache_hits: int
    searches_executed: int
    results_returned: int
    explicit_price_results: int
    evidence_created: int
    records: tuple[CandidateExecutionAudit, ...]
    schema_version: str = "2.7.2.4.10"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def diagnose_candidate(*, result: Any, traces: tuple[SearchExecutionTrace, ...]) -> tuple[str, ...]:
    findings: list[str] = []
    if traces:
        findings.append("brave_search_called")
    else:
        findings.append("brave_search_not_called")
    if any(trace.error for trace in traces):
        findings.append("brave_search_error_present")
    if sum(trace.response_count for trace in traces) > 0:
        findings.append("brave_results_returned")
    else:
        findings.append("no_brave_results_returned")
    if sum(trace.explicit_price_result_count for trace in traces) == 0:
        findings.append("no_explicit_price_nok_in_results_or_landing_pages")
    if int(getattr(result, "comparables_found", 0)) == 0:
        findings.append("no_market_comparables_accepted")
    if int(getattr(result, "buyers_found", 0)) == 0:
        findings.append("no_buyer_candidates_accepted")
    if int(getattr(result, "evidence_created", 0)) == 0:
        findings.append("no_external_evidence_created")
    if tuple(getattr(result, "errors", ())):
        findings.append("external_loop_errors_present")
    return tuple(findings)
