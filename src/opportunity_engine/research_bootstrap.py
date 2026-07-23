"""Bootstrap preliminary research candidates into the external evidence loop.

This layer breaks the circular dependency between final investment scoring and
external evidence. It forwards only explicitly selected preliminary candidates,
keeps the final investment threshold unchanged, and records a complete trace.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from .research_candidate import PreliminaryResearchCandidateScorer


@dataclass(frozen=True, slots=True)
class BootstrapCandidateRecord:
    opportunity_id: str
    research_rank: int
    research_candidate_score: float
    selected_for_external_research: bool
    bootstrap_forwarded: bool
    bootstrap_reason: str
    external_research_requested: bool
    external_research_completed: bool
    searches_executed: int
    searches_skipped: int
    evidence_created: int
    evidence_updated: int
    comparables_found: int
    buyers_found: int
    scenarios_regenerated: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchBootstrapReport:
    record_count: int
    eligible_candidates: int
    selected_candidates: int
    external_research_queue_size: int
    forwarded_candidates: int
    completed_candidates: int
    failed_candidates: int
    searches_executed: int
    searches_skipped: int
    evidence_created: int
    evidence_updated: int
    records: tuple[BootstrapCandidateRecord, ...]
    schema_version: str = "2.7.2.4.2"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchBootstrapPipeline:
    """Select preliminary candidates and forward only those candidates to research."""

    def __init__(
        self,
        *,
        investment_repository: Any,
        external_loop_factory: Callable[[], Any],
        research_threshold: float = 25.0,
        selection_limit: int = 3,
        enabled: bool = True,
        disabled_reason: str = "external_research_disabled",
    ) -> None:
        self.investment_repository = investment_repository
        self.external_loop_factory = external_loop_factory
        self.scorer = PreliminaryResearchCandidateScorer(
            threshold=research_threshold,
            selection_limit=selection_limit,
        )
        self.enabled = enabled
        self.disabled_reason = disabled_reason

    def run(self, payload: Any) -> ResearchBootstrapReport:
        candidate_report = self.scorer.evaluate_payload(payload)
        loop = self.external_loop_factory() if self.enabled and candidate_report.selected_count else None
        records: list[BootstrapCandidateRecord] = []

        for candidate in candidate_report.records:
            selected = candidate.selected_for_external_research
            if not selected:
                records.append(self._not_forwarded(candidate, "not_selected_for_external_research"))
                continue
            if not self.enabled or loop is None:
                records.append(self._not_forwarded(candidate, self.disabled_reason))
                continue

            opportunity_id = candidate.opportunity_id
            try:
                investment_file = self.investment_repository.load(opportunity_id)
                result = loop.run(investment_file)
                self.investment_repository.save(investment_file)
                errors = tuple(str(item) for item in getattr(result, "errors", ()))
                records.append(BootstrapCandidateRecord(
                    opportunity_id=opportunity_id,
                    research_rank=candidate.research_rank,
                    research_candidate_score=candidate.research_candidate_score,
                    selected_for_external_research=True,
                    bootstrap_forwarded=True,
                    bootstrap_reason="top_ranked_candidate",
                    external_research_requested=True,
                    external_research_completed=not errors,
                    searches_executed=int(getattr(result, "searches_executed", 0)),
                    searches_skipped=int(getattr(result, "searches_skipped", 0)),
                    evidence_created=int(getattr(result, "evidence_created", 0)),
                    evidence_updated=int(getattr(result, "evidence_updated", 0)),
                    comparables_found=int(getattr(result, "comparables_found", 0)),
                    buyers_found=int(getattr(result, "buyers_found", 0)),
                    scenarios_regenerated=bool(getattr(result, "scenarios_regenerated", False)),
                    errors=errors,
                ))
            except Exception as exc:  # one failed candidate must not abort the queue
                records.append(BootstrapCandidateRecord(
                    opportunity_id=opportunity_id,
                    research_rank=candidate.research_rank,
                    research_candidate_score=candidate.research_candidate_score,
                    selected_for_external_research=True,
                    bootstrap_forwarded=True,
                    bootstrap_reason="top_ranked_candidate",
                    external_research_requested=True,
                    external_research_completed=False,
                    searches_executed=0,
                    searches_skipped=0,
                    evidence_created=0,
                    evidence_updated=0,
                    comparables_found=0,
                    buyers_found=0,
                    scenarios_regenerated=False,
                    errors=(str(exc),),
                ))

        forwarded = [item for item in records if item.bootstrap_forwarded]
        return ResearchBootstrapReport(
            record_count=len(records),
            eligible_candidates=candidate_report.eligible_count,
            selected_candidates=candidate_report.selected_count,
            external_research_queue_size=candidate_report.selected_count,
            forwarded_candidates=len(forwarded),
            completed_candidates=sum(item.external_research_completed for item in forwarded),
            failed_candidates=sum(not item.external_research_completed for item in forwarded),
            searches_executed=sum(item.searches_executed for item in forwarded),
            searches_skipped=sum(item.searches_skipped for item in forwarded),
            evidence_created=sum(item.evidence_created for item in forwarded),
            evidence_updated=sum(item.evidence_updated for item in forwarded),
            records=tuple(records),
        )

    @staticmethod
    def _not_forwarded(candidate: Any, reason: str) -> BootstrapCandidateRecord:
        return BootstrapCandidateRecord(
            opportunity_id=candidate.opportunity_id,
            research_rank=candidate.research_rank,
            research_candidate_score=candidate.research_candidate_score,
            selected_for_external_research=candidate.selected_for_external_research,
            bootstrap_forwarded=False,
            bootstrap_reason=reason,
            external_research_requested=False,
            external_research_completed=False,
            searches_executed=0,
            searches_skipped=0,
            evidence_created=0,
            evidence_updated=0,
            comparables_found=0,
            buyers_found=0,
            scenarios_regenerated=False,
        )
