"""Orchestrate evidence collection, scoring and scenario regeneration.

The orchestrator is intentionally conservative: it never invents missing values,
keeps evidence strength separate from investment attractiveness, and only
regenerates scenarios when research inputs changed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .evidence_collector import ExistingSourceEvidenceCollector
from .evidence_scoring import EvidenceScoringEngine
from .evidence_store import EvidenceRepository
from .living_investment_file import LivingInvestmentFile, LivingInvestmentFileRepository
from .scenario_generator import ScenarioGeneratorEngine, ScenarioInputs


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ResearchPipelineResult:
    opportunity_id: str
    started_at: str
    finished_at: str
    duration_ms: float
    evidence_extracted: int
    evidence_created: int
    evidence_updated: int
    evidence_linked: int
    evidence_scored: int
    scenarios_regenerated: bool
    best_path_id: str | None
    changed: bool
    errors: tuple[str, ...]


class ResearchPipelineOrchestrator:
    """Run the v2.5.2 research cycle for one Living Investment File."""

    def __init__(
        self,
        *,
        evidence_repository: EvidenceRepository | None = None,
        investment_repository: LivingInvestmentFileRepository | None = None,
        collector: ExistingSourceEvidenceCollector | None = None,
        scorer: EvidenceScoringEngine | None = None,
        scenario_engine: ScenarioGeneratorEngine | None = None,
        run_log_root: str | Path = "data/research_runs",
    ) -> None:
        self.evidence_repository = evidence_repository or EvidenceRepository()
        self.investment_repository = investment_repository or LivingInvestmentFileRepository()
        self.collector = collector or ExistingSourceEvidenceCollector(self.evidence_repository)
        self.scorer = scorer or EvidenceScoringEngine()
        self.scenario_engine = scenario_engine or ScenarioGeneratorEngine()
        self.run_log_root = Path(run_log_root)

    def run(
        self,
        investment_file: LivingInvestmentFile,
        row: dict[str, Any],
        *,
        intelligence: dict[str, Any] | None = None,
        discovery: dict[str, Any] | None = None,
    ) -> ResearchPipelineResult:
        started_at = utc_now()
        timer = perf_counter()
        errors: list[str] = []
        before_fingerprint = self._research_fingerprint(investment_file)

        evidence_extracted = 0
        evidence_created = 0
        evidence_updated = 0
        evidence_linked = 0
        evidence_scored = 0
        scenarios_regenerated = False
        best_path_id = investment_file.best_current_path_id

        try:
            collection = self.collector.collect(
                investment_file,
                row,
                intelligence=intelligence,
                discovery=discovery,
            )
            evidence_extracted = collection.extracted_count
            evidence_created = collection.created_count
            evidence_updated = collection.updated_count
            evidence_linked = collection.linked_count
        except Exception as exc:  # keep the remaining cycle auditable
            errors.append(f"collector: {exc}")

        stored_evidence = []
        try:
            stored_evidence = self.evidence_repository.list_for_opportunity(
                investment_file.opportunity_id
            )
            for item in stored_evidence:
                result = self.scorer.score(item, peers=stored_evidence)
                item.metadata["evidence_score"] = result.score
                item.metadata["evidence_grade"] = result.grade.value
                item.metadata["source_tier"] = result.source_tier.value
                item.metadata["score_breakdown"] = asdict(result.breakdown)
                item.metadata["score_reasons"] = list(result.reasons)
                item.metadata["score_warnings"] = list(result.warnings)
                self.evidence_repository.upsert(item)
                evidence_scored += 1
        except Exception as exc:
            errors.append(f"scoring: {exc}")

        changed_by_evidence = any(
            (evidence_created, evidence_updated, evidence_linked)
        )
        if changed_by_evidence:
            try:
                inputs = self._scenario_inputs(investment_file, stored_evidence)
                linked_ids = tuple(entry.evidence_id for entry in investment_file.evidence)
                scenario_result = self.scenario_engine.generate(
                    investment_file,
                    inputs,
                    evidence_ids=linked_ids,
                )
                scenarios_regenerated = True
                best_path_id = scenario_result.best_path_id
            except Exception as exc:
                errors.append(f"scenario_generator: {exc}")

        after_fingerprint = self._research_fingerprint(investment_file)
        changed = before_fingerprint != after_fingerprint

        try:
            if changed:
                self.investment_repository.save(investment_file)
        except Exception as exc:
            errors.append(f"investment_repository: {exc}")

        finished_at = utc_now()
        result = ResearchPipelineResult(
            opportunity_id=investment_file.opportunity_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=round((perf_counter() - timer) * 1000, 2),
            evidence_extracted=evidence_extracted,
            evidence_created=evidence_created,
            evidence_updated=evidence_updated,
            evidence_linked=evidence_linked,
            evidence_scored=evidence_scored,
            scenarios_regenerated=scenarios_regenerated,
            best_path_id=best_path_id,
            changed=changed,
            errors=tuple(errors),
        )
        self._write_run_log(result)
        return result

    @staticmethod
    def _scenario_inputs(
        item: LivingInvestmentFile,
        evidence: list[Any],
    ) -> ScenarioInputs:
        conservative_market_values: list[float] = []
        for record in evidence:
            if record.evidence_type.value != "market_price":
                continue
            if record.direction.value != "supports":
                continue
            for observation in record.observations:
                if observation.numeric_value is not None:
                    conservative_market_values.append(observation.numeric_value)

        resale_value = min(conservative_market_values) if conservative_market_values else None
        return ScenarioInputs(
            purchase_price_nok=item.asking_price_nok,
            conservative_resale_value_nok=resale_value,
        )

    @staticmethod
    def _research_fingerprint(item: LivingInvestmentFile) -> str:
        payload = {
            "evidence": [asdict(entry) for entry in item.evidence],
            "revenue_paths": [asdict(entry) for entry in item.revenue_paths],
            "best_current_path_id": item.best_current_path_id,
            "next_action": item.next_action,
            "missing_information": [asdict(entry) for entry in item.missing_information],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _write_run_log(self, result: ResearchPipelineResult) -> Path:
        directory = self.run_log_root / result.opportunity_id
        directory.mkdir(parents=True, exist_ok=True)
        stamp = result.started_at.replace(":", "-").replace("+", "_")
        destination = directory / f"{stamp}.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination
