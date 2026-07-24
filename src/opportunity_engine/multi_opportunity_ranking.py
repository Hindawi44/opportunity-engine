"""V3.0 ranking layer over already-evaluated V2.10/V2.11 opportunities.

This module does not search, infer evidence, recalculate financial values, or alter
any V2.8-V2.11 contract. It only filters and deterministically ranks eligible
financial-review records.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable


_READY = "READY_FOR_FINANCIAL_REVIEW"


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


@dataclass(frozen=True, slots=True)
class RankedOpportunity:
    rank: int
    opportunity_id: str
    decision_gate: str
    expected_profit_nok: float
    roi_percent: float
    verified_comparable_count: int
    verified_cost_component_count: int
    evidence_completeness_score: float
    comparable_quality_score: float | None
    risk_level: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_ready_record(record: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    opportunity_id = str(record.get("opportunity_id") or "").strip()
    if not opportunity_id:
        errors.append("missing opportunity_id")
    if record.get("decision_gate") != _READY:
        errors.append("decision gate is not ready")
    if record.get("automatic_purchase_decision") is not False:
        errors.append("automatic purchase decision must remain false")
    if record.get("market_evidence_status") not in ("COMPLETE", None) and record.get("market_status") != "COMPLETE":
        errors.append("market evidence incomplete")
    if record.get("cost_evidence_status") not in ("COMPLETE", None) and record.get("cost_status") != "COMPLETE":
        errors.append("cost evidence incomplete")
    if int(record.get("verified_comparable_count") or 0) < 3:
        errors.append("fewer than three verified comparables")
    if int(record.get("verified_cost_component_count") or 0) < 6:
        errors.append("fewer than six verified cost components")
    if _number(record.get("expected_profit_nok")) is None:
        errors.append("missing expected profit")
    if _number(record.get("roi_percent")) is None:
        errors.append("missing ROI")
    return not errors, errors


def rank_evaluated_opportunities(
    records: Iterable[dict[str, Any]],
    *,
    analysis_date: str | None = None,
) -> dict[str, Any]:
    """Filter and rank already evaluated opportunities.

    Ranking order is deterministic and uses only existing outputs:
    ROI descending, expected profit descending, evidence completeness descending,
    comparable quality descending, then opportunity_id ascending.
    """
    received = list(records)
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for record in received:
        if not isinstance(record, dict):
            excluded.append({"opportunity_id": None, "reason": "record is not an object"})
            continue
        valid, reasons = _validate_ready_record(record)
        if not valid:
            excluded.append({
                "opportunity_id": str(record.get("opportunity_id") or "") or None,
                "decision_gate": record.get("decision_gate"),
                "reasons": reasons,
            })
            continue
        eligible.append(record)

    def key(record: dict[str, Any]) -> tuple[float, float, float, float, str]:
        completeness = float(record.get("evidence_completeness_score") or 1.0)
        quality = float(record.get("comparable_quality_score") or 0.0)
        return (
            -float(record["roi_percent"]),
            -float(record["expected_profit_nok"]),
            -completeness,
            -quality,
            str(record["opportunity_id"]),
        )

    eligible.sort(key=key)
    rankings: list[dict[str, Any]] = []
    for index, record in enumerate(eligible, start=1):
        rankings.append(RankedOpportunity(
            rank=index,
            opportunity_id=str(record["opportunity_id"]),
            decision_gate=_READY,
            expected_profit_nok=float(record["expected_profit_nok"]),
            roi_percent=float(record["roi_percent"]),
            verified_comparable_count=int(record["verified_comparable_count"]),
            verified_cost_component_count=int(record["verified_cost_component_count"]),
            evidence_completeness_score=float(record.get("evidence_completeness_score") or 1.0),
            comparable_quality_score=(
                float(record["comparable_quality_score"])
                if _number(record.get("comparable_quality_score")) is not None
                else None
            ),
            risk_level=str(record.get("risk_level")) if record.get("risk_level") is not None else None,
        ).to_dict())

    return {
        "schema_version": "3.0",
        "analysis_date": analysis_date or datetime.now(timezone.utc).isoformat(),
        "opportunities_processed": len(received),
        "ready_for_financial_review": len(rankings),
        "excluded_count": len(excluded),
        "rankings": rankings,
        "excluded": excluded,
        "automatic_purchase_decision": False,
        "status": "PASS" if rankings else "NO_ELIGIBLE_OPPORTUNITIES",
    }
