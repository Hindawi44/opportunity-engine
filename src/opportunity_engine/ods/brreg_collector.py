"""Collect and consolidate live Brreg opportunity leads across multiple searches.

The collector deliberately works with bounded search slices. It does not claim to be a
complete national bankruptcy feed. Each slice is run through the existing live Brreg
pipeline, then candidates are deduplicated, ranked together, remembered, and passed to
the conservative executive decision engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .decision import DecisionInputs, ExecutiveDecisionReport, build_executive_decision
from .live_brreg_pipeline import LiveBrregAnalysis, run_live_brreg_analysis
from .memory import MemoryRunResult, OpportunityMemoryEngine
from .models import ODSRequest, ODSSession, OpportunityCandidate, Stage, StageResult, Status
from .ranking import OpportunityRankingPlugin, RankedOpportunity
from .scanner import ConnectorScanStatus, ScanSnapshot

LiveRunner = Callable[..., LiveBrregAnalysis]


@dataclass(frozen=True)
class BrregSearchSlice:
    subject: str
    municipality: str | None = None
    industry_code: str | None = None
    page_size: int = 50

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("subject must not be empty")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class BrregCollectionResult:
    slices_requested: int
    slices_completed: int
    slices_failed: int
    duplicate_count: int
    snapshot: ScanSnapshot
    ranked_opportunities: tuple[RankedOpportunity, ...]
    memory: MemoryRunResult
    decision: ExecutiveDecisionReport | None
    errors: tuple[str, ...]


class BrregOpportunityCollector:
    """Run bounded Brreg searches and consolidate grounded status leads."""

    def __init__(
        self,
        storage_path: str | Path,
        *,
        runner: LiveRunner = run_live_brreg_analysis,
        shortlist_size: int = 20,
    ) -> None:
        if shortlist_size < 1:
            raise ValueError("shortlist_size must be at least 1")
        self.memory_engine = OpportunityMemoryEngine(storage_path)
        self.runner = runner
        self.shortlist_size = shortlist_size

    def collect(
        self,
        slices: Iterable[BrregSearchSlice],
        *,
        country: str = "Norway",
    ) -> BrregCollectionResult:
        search_slices = tuple(slices)
        if not search_slices:
            raise ValueError("collector requires at least one search slice")

        started_at = datetime.now(timezone.utc)
        documents = []
        candidates: dict[str, OpportunityCandidate] = {}
        statuses: list[ConnectorScanStatus] = []
        errors: list[str] = []
        duplicate_count = 0
        completed = 0
        failed = 0

        for item in search_slices:
            label = _slice_label(item)
            try:
                analysis = self.runner(
                    item.subject,
                    country=country,
                    municipality=item.municipality,
                    industry_code=item.industry_code,
                    page_size=item.page_size,
                    shortlist_size=self.shortlist_size,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                failed += 1
                errors.append(f"{label}: {exc}")
                statuses.append(ConnectorScanStatus(label, "failed", 0, str(exc)))
                continue

            completed += 1
            documents.extend(analysis.scan.documents)
            statuses.append(
                ConnectorScanStatus(label, "completed", len(analysis.scan.documents))
            )
            for candidate in analysis.scan.opportunities:
                existing = candidates.get(candidate.opportunity_id)
                if existing is None:
                    candidates[candidate.opportunity_id] = candidate
                else:
                    duplicate_count += 1
                    candidates[candidate.opportunity_id] = _prefer_candidate(existing, candidate)

        completed_at = datetime.now(timezone.utc)
        request = ODSRequest(subject="Brreg status collection", country=country)
        snapshot = ScanSnapshot(
            scan_id=f"brreg-collection-{int(started_at.timestamp())}",
            started_at=started_at,
            completed_at=completed_at,
            documents=tuple(documents),
            opportunities=tuple(sorted(candidates.values(), key=lambda value: value.opportunity_id)),
            connector_statuses=tuple(statuses),
            duplicate_count=duplicate_count,
        )
        memory = self.memory_engine.run(snapshot, country=country)
        ranked = _rank(snapshot, request, self.shortlist_size)
        decision = _decision(ranked)
        return BrregCollectionResult(
            slices_requested=len(search_slices),
            slices_completed=completed,
            slices_failed=failed,
            duplicate_count=duplicate_count,
            snapshot=snapshot,
            ranked_opportunities=ranked,
            memory=memory,
            decision=decision,
            errors=tuple(errors),
        )


def _rank(
    snapshot: ScanSnapshot,
    request: ODSRequest,
    shortlist_size: int,
) -> tuple[RankedOpportunity, ...]:
    if not snapshot.opportunities:
        return ()
    session = ODSSession(request=request, status=Status.RUNNING)
    session.results[Stage.DISCOVERY] = StageResult(
        stage=Stage.DISCOVERY,
        status=Status.COMPLETED,
        payload=snapshot.opportunities,
        evidence=[f"collector_scan:{snapshot.scan_id}"],
    )
    result = OpportunityRankingPlugin(shortlist_size=shortlist_size).run(session)
    if result.status is not Status.COMPLETED or not isinstance(result.payload, tuple):
        raise RuntimeError("Brreg collection ranking failed")
    return result.payload


def _decision(ranked: tuple[RankedOpportunity, ...]) -> ExecutiveDecisionReport | None:
    if not ranked:
        return None
    return build_executive_decision(
        DecisionInputs(
            opportunity_confidence=ranked[0].final_score,
            validation_readiness=40.0,
            evidence_quality=90.0,
            market_health=None,
            financial_report=None,
        )
    )


def _prefer_candidate(
    first: OpportunityCandidate,
    second: OpportunityCandidate,
) -> OpportunityCandidate:
    if second.confidence > first.confidence:
        return second
    if second.confidence < first.confidence:
        return first
    return second if len(second.evidence) > len(first.evidence) else first


def _slice_label(item: BrregSearchSlice) -> str:
    details = [item.subject.strip()]
    if item.municipality:
        details.append(item.municipality.strip())
    if item.industry_code:
        details.append(item.industry_code.strip())
    return "brreg:" + ":".join(details)
