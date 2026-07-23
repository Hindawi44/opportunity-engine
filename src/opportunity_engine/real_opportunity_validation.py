"""Real-opportunity validation metrics for Opportunity Engine v2.7.1.

This module evaluates persisted daily-pipeline output without changing investment
recommendations. It records measurable coverage and data-quality KPIs so later
validation phases can compare system output with real market outcomes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json
import time


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("opportunities", "rows", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    # A single opportunity is accepted for deterministic/manual validation.
    if any(key in payload for key in ("opportunity_id", "id", "title", "source_url", "url")):
        return [payload]
    return []


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


@dataclass(frozen=True, slots=True)
class OpportunityValidationRecord:
    opportunity_id: str
    title: str | None
    source: str | None
    source_url: str | None
    internal_score: float | None
    external_research_eligible: bool
    comparable_count: int
    buyer_count: int
    evidence_count: int
    scenario_count: int
    best_scenario_present: bool
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationKpis:
    opportunities_discovered: int
    unique_opportunities: int
    duplicates_detected: int
    opportunities_with_source_url: int
    opportunities_with_price: int
    external_research_eligible: int
    opportunities_with_comparables: int
    accepted_comparables: int
    opportunities_with_buyers: int
    potential_buyers: int
    opportunities_with_evidence: int
    opportunities_with_scenarios: int
    opportunities_with_best_scenario: int
    average_internal_score: float | None
    source_coverage_rate: float
    price_coverage_rate: float
    comparable_coverage_rate: float
    buyer_coverage_rate: float
    scenario_coverage_rate: float


@dataclass(frozen=True, slots=True)
class RealDatasetValidationReport:
    generated_at: str
    dataset_path: str
    duration_ms: int
    kpis: ValidationKpis
    records: tuple[OpportunityValidationRecord, ...]
    warnings: tuple[str, ...] = ()
    schema_version: str = "2.7.1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RealOpportunityValidator:
    external_research_score_threshold: float = 60.0
    required_fields: tuple[str, ...] = ("opportunity_id", "title", "source_url")

    def validate_payload(self, payload: Any, *, dataset_path: str = "<memory>") -> RealDatasetValidationReport:
        started = time.perf_counter()
        rows = _as_rows(payload)
        records: list[OpportunityValidationRecord] = []
        warnings: list[str] = []
        seen: set[str] = set()
        duplicates = 0
        prices_present = 0
        scores: list[float] = []

        for index, row in enumerate(rows):
            raw_id = _first(row, "opportunity_id", "id", "document_id", "listing_id")
            source_url = _first(row, "source_url", "url", "listing_url")
            title = _first(row, "title", "name", "headline")
            opportunity_id = str(raw_id or source_url or f"row-{index + 1}")
            if opportunity_id in seen:
                duplicates += 1
            else:
                seen.add(opportunity_id)

            score = _number(_first(row, "score", "internal_score", "opportunity_score", "quality_score"))
            if score is not None:
                scores.append(score)
            price = _number(_first(row, "price_nok", "price", "asking_price_nok", "current_bid_nok"))
            prices_present += int(price is not None)

            comparable_count = self._count(row, "accepted_comparables", "comparables", "market_comparables", "comparable_count")
            buyer_count = self._count(row, "potential_buyers", "buyers", "buyer_candidates", "buyer_count")
            evidence_count = self._count(row, "evidence", "evidence_ids", "research_evidence", "evidence_count")
            scenario_count = self._count(row, "scenarios", "investment_scenarios", "scenario_count")
            best_scenario = _first(row, "best_scenario", "best_path", "recommended_scenario")

            missing: list[str] = []
            if raw_id is None:
                missing.append("opportunity_id")
            if title is None:
                missing.append("title")
            if source_url is None:
                missing.append("source_url")

            explicit_eligible = row.get("external_research_eligible")
            eligible = (
                bool(explicit_eligible)
                if isinstance(explicit_eligible, bool)
                else score is not None and score >= self.external_research_score_threshold
            )

            records.append(
                OpportunityValidationRecord(
                    opportunity_id=opportunity_id,
                    title=str(title) if title is not None else None,
                    source=str(_first(row, "source", "source_name", "provider")) if _first(row, "source", "source_name", "provider") is not None else None,
                    source_url=str(source_url) if source_url is not None else None,
                    internal_score=score,
                    external_research_eligible=eligible,
                    comparable_count=comparable_count,
                    buyer_count=buyer_count,
                    evidence_count=evidence_count,
                    scenario_count=scenario_count,
                    best_scenario_present=best_scenario is not None,
                    missing_fields=tuple(missing),
                )
            )

        count = len(records)
        if not rows:
            warnings.append("No opportunity rows were found in the supplied payload")
        if any(record.missing_fields for record in records):
            warnings.append("Some opportunities are missing one or more core identity fields")

        def rate(numerator: int) -> float:
            return round(numerator / count, 4) if count else 0.0

        source_count = sum(record.source_url is not None for record in records)
        eligible_count = sum(record.external_research_eligible for record in records)
        opportunities_with_comparables = sum(record.comparable_count > 0 for record in records)
        accepted_comparables = sum(record.comparable_count for record in records)
        opportunities_with_buyers = sum(record.buyer_count > 0 for record in records)
        potential_buyers = sum(record.buyer_count for record in records)
        opportunities_with_evidence = sum(record.evidence_count > 0 for record in records)
        opportunities_with_scenarios = sum(record.scenario_count > 0 for record in records)
        opportunities_with_best = sum(record.best_scenario_present for record in records)

        kpis = ValidationKpis(
            opportunities_discovered=count,
            unique_opportunities=len(seen),
            duplicates_detected=duplicates,
            opportunities_with_source_url=source_count,
            opportunities_with_price=prices_present,
            external_research_eligible=eligible_count,
            opportunities_with_comparables=opportunities_with_comparables,
            accepted_comparables=accepted_comparables,
            opportunities_with_buyers=opportunities_with_buyers,
            potential_buyers=potential_buyers,
            opportunities_with_evidence=opportunities_with_evidence,
            opportunities_with_scenarios=opportunities_with_scenarios,
            opportunities_with_best_scenario=opportunities_with_best,
            average_internal_score=round(sum(scores) / len(scores), 2) if scores else None,
            source_coverage_rate=rate(source_count),
            price_coverage_rate=rate(prices_present),
            comparable_coverage_rate=rate(opportunities_with_comparables),
            buyer_coverage_rate=rate(opportunities_with_buyers),
            scenario_coverage_rate=rate(opportunities_with_scenarios),
        )
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        return RealDatasetValidationReport(
            generated_at=utc_now_iso(),
            dataset_path=dataset_path,
            duration_ms=duration_ms,
            kpis=kpis,
            records=tuple(records),
            warnings=tuple(warnings),
        )

    def validate_file(self, path: str | Path) -> RealDatasetValidationReport:
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        return self.validate_payload(payload, dataset_path=str(source))

    @staticmethod
    def write_report(report: RealDatasetValidationReport, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target

    @staticmethod
    def _count(row: dict[str, Any], *keys: str) -> int:
        value = _first(row, *keys)
        if isinstance(value, bool) or value is None:
            return 0
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, (list, tuple, set, dict)):
            return len(value)
        return 0
