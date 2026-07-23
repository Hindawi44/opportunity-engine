"""Audit transparent internal opportunity scores without changing scoring rules."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("opportunities", "rows", "items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


@dataclass(frozen=True, slots=True)
class ScoreAuditRecord:
    opportunity_id: str
    title: str | None
    total_score: float | None
    required_score: float
    score_gap: float | None
    score_components: dict[str, float]
    component_total: float
    score_reasons: tuple[str, ...]
    upstream_decision: str | None
    missing_evidence_count: int
    diagnosis: tuple[str, ...]
    eligible: bool


@dataclass(frozen=True, slots=True)
class InternalScoreAuditReport:
    generated_at: str
    dataset_path: str
    required_score: float
    records: tuple[ScoreAuditRecord, ...]
    eligible_count: int
    below_threshold_count: int
    missing_score_count: int
    component_mismatch_count: int
    schema_version: str = "2.7.2.2"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InternalScoreAuditor:
    required_score: float = 60.0

    def audit_payload(self, payload: Any, *, dataset_path: str = "<memory>") -> InternalScoreAuditReport:
        records: list[ScoreAuditRecord] = []
        for index, row in enumerate(_rows(payload)):
            opportunity_id = str(row.get("opportunity_id") or row.get("id") or f"row-{index + 1}")
            title_value = row.get("title") or row.get("name")
            total_score = _number(row.get("opportunity_score"))
            if total_score is None:
                total_score = _number(row.get("internal_score"))
            if total_score is None:
                total_score = _number(row.get("score"))

            raw_components = row.get("score_components")
            components: dict[str, float] = {}
            if isinstance(raw_components, dict):
                for key, value in raw_components.items():
                    number = _number(value)
                    if number is not None:
                        components[str(key)] = number
            component_total = round(sum(components.values()), 2)

            raw_reasons = row.get("score_reasons")
            reasons = tuple(str(value) for value in raw_reasons) if isinstance(raw_reasons, list) else ()
            missing = row.get("missing_evidence")
            missing_count = len(missing) if isinstance(missing, list) else 0
            upstream = row.get("decision")
            upstream_decision = str(upstream) if upstream not in (None, "") else None

            diagnosis: list[str] = []
            if total_score is None:
                diagnosis.append("missing_total_score")
            if not components:
                diagnosis.append("missing_score_components")
            if total_score is not None and components and abs(component_total - total_score) > 0.01:
                diagnosis.append("component_total_differs_from_final_score_due_to_gate_or_cap")
            if components.get("verified_economics", 0.0) == 0.0:
                diagnosis.append("no_verified_economics_points")
            if components.get("evidence", 0.0) == 0.0:
                diagnosis.append("no_evidence_points")
            if missing_count:
                diagnosis.append("missing_evidence_blocks_financial_validation")
            if upstream_decision and upstream_decision != "REVIEW_NUMBERS":
                diagnosis.append("upstream_evidence_gate_active")
            if total_score is not None and total_score < self.required_score:
                diagnosis.append("below_external_research_threshold")

            gap = round(self.required_score - total_score, 2) if total_score is not None else None
            records.append(ScoreAuditRecord(
                opportunity_id=opportunity_id,
                title=str(title_value) if title_value is not None else None,
                total_score=total_score,
                required_score=self.required_score,
                score_gap=gap,
                score_components=components,
                component_total=component_total,
                score_reasons=reasons,
                upstream_decision=upstream_decision,
                missing_evidence_count=missing_count,
                diagnosis=tuple(diagnosis),
                eligible=total_score is not None and total_score >= self.required_score,
            ))

        return InternalScoreAuditReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_path=dataset_path,
            required_score=self.required_score,
            records=tuple(records),
            eligible_count=sum(record.eligible for record in records),
            below_threshold_count=sum(record.total_score is not None and not record.eligible for record in records),
            missing_score_count=sum(record.total_score is None for record in records),
            component_mismatch_count=sum("component_total_differs_from_final_score_due_to_gate_or_cap" in record.diagnosis for record in records),
        )

    def audit_file(self, path: str | Path) -> InternalScoreAuditReport:
        source = Path(path)
        return self.audit_payload(json.loads(source.read_text(encoding="utf-8")), dataset_path=str(source))

    @staticmethod
    def write_report(report: InternalScoreAuditReport, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target
