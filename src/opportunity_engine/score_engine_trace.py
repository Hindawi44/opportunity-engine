"""Trace how score data moves from the scoring engine into the daily dataset.

This module is diagnostic only. It does not alter scores, thresholds, recommendations,
or external-research eligibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import re

_COMPONENT_PATTERN = re.compile(r"^(financial|confidence|data_quality|resale|logistics)=(-?\d+(?:\.\d+)?)/")
_PENALTY_PATTERN = re.compile(r"^(evidence_gap_penalty|warning_penalty|risk_penalty)=(-?\d+(?:\.\d+)?)$")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "opportunities", "items", "results", "data"):
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


def _parse_breakdown(value: Any) -> tuple[dict[str, float], tuple[str, ...]]:
    if not isinstance(value, (list, tuple)):
        return {}, ()
    components: dict[str, float] = {}
    raw: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        raw.append(entry)
        match = _COMPONENT_PATTERN.match(entry)
        if match:
            components[match.group(1)] = float(match.group(2))
            continue
        penalty = _PENALTY_PATTERN.match(entry)
        if penalty:
            components[penalty.group(1)] = float(penalty.group(2))
    return components, tuple(raw)


@dataclass(frozen=True, slots=True)
class ScoreTraceRecord:
    opportunity_id: str
    title: str | None
    total_score: float | None
    decision: str | None
    score_breakdown_present: bool
    parsed_components: dict[str, float]
    raw_score_breakdown: tuple[str, ...]
    component_sum_before_penalty: float | None
    calculated_raw_score: float | None
    cap_expected: float | None
    cap_applied: bool | None
    trace_stage: str
    diagnosis: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoreEngineTraceReport:
    dataset_path: str
    record_count: int
    scoring_function_called_count: int
    breakdown_serialized_count: int
    missing_breakdown_count: int
    records: tuple[ScoreTraceRecord, ...]
    schema_version: str = "2.7.2.3"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScoreEngineTraceAuditor:
    """Audit score invocation evidence and serialization boundaries."""

    def audit_payload(self, payload: Any, *, dataset_path: str = "<memory>") -> ScoreEngineTraceReport:
        records: list[ScoreTraceRecord] = []
        for index, row in enumerate(_rows(payload)):
            opportunity_id = str(row.get("opportunity_id") or row.get("id") or f"row-{index + 1}")
            title = row.get("title")
            total = _number(row.get("score"))
            if total is None:
                total = _number(row.get("internal_score"))
            if total is None:
                total = _number(row.get("opportunity_score"))
            decision = row.get("decision")
            components, raw_breakdown = _parse_breakdown(row.get("score_breakdown"))
            if not components and isinstance(row.get("score_components"), dict):
                components = {
                    str(key): float(value)
                    for key, value in row["score_components"].items()
                    if _number(value) is not None
                }

            diagnosis: list[str] = []
            breakdown_present = bool(raw_breakdown or components)
            if total is not None:
                diagnosis.append("score_value_serialized")
            else:
                diagnosis.append("score_value_missing")
            if breakdown_present:
                diagnosis.append("scoring_components_serialized")
            else:
                diagnosis.append("scoring_components_missing_at_dataset_boundary")

            positive_keys = ("financial", "confidence", "data_quality", "resale", "logistics")
            positive_values = [components[key] for key in positive_keys if key in components]
            component_sum = round(sum(positive_values), 2) if positive_values else None
            risk = components.get("risk_penalty")
            calculated_raw = round(component_sum - risk, 2) if component_sum is not None and risk is not None else None

            cap_expected: float | None = None
            decision_text = str(decision) if decision is not None else None
            if decision_text == "reject":
                cap_expected = 39.0
            elif decision_text == "monitor":
                cap_expected = 59.0
            cap_applied = None
            if total is not None and calculated_raw is not None and cap_expected is not None:
                cap_applied = calculated_raw > cap_expected and total <= cap_expected
                diagnosis.append("decision_cap_applied" if cap_applied else "decision_cap_not_applied")

            if total is not None and not breakdown_present:
                diagnosis.append("score_engine_likely_called_but_details_dropped_in_projection")
                trace_stage = "dashboard_projection"
            elif breakdown_present:
                diagnosis.append("score_engine_called_and_breakdown_reached_dataset")
                trace_stage = "dataset_serialization"
            else:
                diagnosis.append("cannot_confirm_score_engine_invocation")
                trace_stage = "scoring_invocation"

            records.append(ScoreTraceRecord(
                opportunity_id=opportunity_id,
                title=str(title) if title is not None else None,
                total_score=total,
                decision=decision_text,
                score_breakdown_present=breakdown_present,
                parsed_components=components,
                raw_score_breakdown=raw_breakdown,
                component_sum_before_penalty=component_sum,
                calculated_raw_score=calculated_raw,
                cap_expected=cap_expected,
                cap_applied=cap_applied,
                trace_stage=trace_stage,
                diagnosis=tuple(diagnosis),
            ))

        called = sum(record.total_score is not None for record in records)
        serialized = sum(record.score_breakdown_present for record in records)
        return ScoreEngineTraceReport(
            dataset_path=dataset_path,
            record_count=len(records),
            scoring_function_called_count=called,
            breakdown_serialized_count=serialized,
            missing_breakdown_count=len(records) - serialized,
            records=tuple(records),
        )

    def audit_file(self, path: str | Path) -> ScoreEngineTraceReport:
        source = Path(path)
        return self.audit_payload(json.loads(source.read_text(encoding="utf-8")), dataset_path=str(source))

    @staticmethod
    def write_report(report: ScoreEngineTraceReport, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target
