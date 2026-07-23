"""Preliminary research candidate scoring.

This module decides which opportunities deserve limited external research before
final investment scoring. It never changes the final investment threshold and
never invents financial evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import re

_COMPONENT_PATTERN = re.compile(r"^(data_quality|resale|logistics)=(-?\d+(?:\.\d+)?)/")
_PENALTY_PATTERN = re.compile(r"^(evidence_gap_penalty|warning_penalty|risk_penalty)=(-?\d+(?:\.\d+)?)$")
_HEAVY_TERMS = (
    "gravemaskin", "hjullaster", "truck", "traktor", "lastebil", "bil", "motor",
    "container", "anleggsmaskin", "excavator", "loader", "vehicle",
)


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


def _parse_breakdown(value: Any) -> dict[str, float]:
    components: dict[str, float] = {}
    if not isinstance(value, (list, tuple)):
        return components
    for entry in value:
        if not isinstance(entry, str):
            continue
        match = _COMPONENT_PATTERN.match(entry)
        if match:
            components[match.group(1)] = float(match.group(2))
            continue
        penalty = _PENALTY_PATTERN.match(entry)
        if penalty:
            components[penalty.group(1)] = float(penalty.group(2))
    return components


def _present(row: dict[str, Any], *keys: str) -> bool:
    return any(row.get(key) not in (None, "", [], {}) for key in keys)


@dataclass(frozen=True, slots=True)
class ResearchCandidateResult:
    opportunity_id: str
    title: str | None
    research_candidate_score: float
    research_threshold: float
    research_eligible: bool
    research_rank: int
    selected_for_external_research: bool
    research_reasons: tuple[str, ...]
    score_components: dict[str, float]
    final_investment_score: float | None
    final_investment_threshold: float = 60.0


@dataclass(frozen=True, slots=True)
class ResearchCandidateReport:
    record_count: int
    eligible_count: int
    selected_count: int
    research_threshold: float
    selection_limit: int
    records: tuple[ResearchCandidateResult, ...]
    schema_version: str = "2.7.2.4.1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PreliminaryResearchCandidateScorer:
    """Rank opportunities using only evidence available before external research."""

    def __init__(self, *, threshold: float = 25.0, selection_limit: int = 3) -> None:
        self.threshold = float(threshold)
        self.selection_limit = max(0, int(selection_limit))

    def _score_row(self, row: dict[str, Any], index: int) -> tuple[dict[str, Any], list[str]]:
        components = _parse_breakdown(row.get("score_breakdown"))
        reasons: list[str] = []

        data_quality = min(12.0, max(0.0, components.get("data_quality", 0.0) / 15.0 * 12.0))
        resale = min(15.0, max(0.0, components.get("resale", 0.0)))
        logistics = min(15.0, max(0.0, components.get("logistics", 0.0)))

        completeness = 0.0
        if _present(row, "title"):
            completeness += 2.0
        if _present(row, "source_url", "url"):
            completeness += 2.0
        if _present(row, "location", "city", "municipality"):
            completeness += 2.0
        if _present(row, "price", "current_price", "bid", "amount"):
            completeness += 2.0

        title = str(row.get("title") or "")
        title_lower = title.lower()
        heavy_penalty = 10.0 if any(term in title_lower for term in _HEAVY_TERMS) else 0.0
        warning_penalty = min(4.0, max(0.0, components.get("warning_penalty", 0.0)))
        risk_penalty = min(4.0, max(0.0, components.get("risk_penalty", 0.0) / 3.0))
        penalty = heavy_penalty + warning_penalty + risk_penalty

        if resale >= 10:
            reasons.append("strong_resale_potential")
        elif resale > 0:
            reasons.append("some_resale_potential")
        if logistics >= 10:
            reasons.append("manageable_logistics")
        if data_quality >= 6 or completeness >= 6:
            reasons.append("listing_data_sufficient")
        if completeness < 4:
            reasons.append("listing_data_incomplete")
        if heavy_penalty:
            reasons.append("heavy_or_complex_asset")
        if warning_penalty:
            reasons.append("listing_warnings_present")

        score = round(max(0.0, min(50.0, data_quality + resale + logistics + completeness - penalty)), 2)
        return {
            "opportunity_id": str(row.get("opportunity_id") or row.get("id") or f"row-{index + 1}"),
            "title": title or None,
            "score": score,
            "components": {
                "data_quality": round(data_quality, 2),
                "resale": round(resale, 2),
                "logistics": round(logistics, 2),
                "listing_completeness": round(completeness, 2),
                "penalty": round(penalty, 2),
            },
            "reasons": reasons,
            "final_investment_score": row.get("score") if isinstance(row.get("score"), (int, float)) else row.get("internal_score"),
        }, reasons

    def evaluate_payload(self, payload: Any) -> ResearchCandidateReport:
        scored = [self._score_row(row, index)[0] for index, row in enumerate(_rows(payload))]
        scored.sort(key=lambda item: (-item["score"], item["opportunity_id"]))
        eligible_ids = [item["opportunity_id"] for item in scored if item["score"] >= self.threshold]
        selected_ids = set(eligible_ids[: self.selection_limit])

        records: list[ResearchCandidateResult] = []
        for rank, item in enumerate(scored, start=1):
            eligible = item["score"] >= self.threshold
            reasons = list(item["reasons"])
            reasons.append("research_threshold_met" if eligible else "research_threshold_not_met")
            if item["opportunity_id"] in selected_ids:
                reasons.append("selected_within_external_research_limit")
            elif eligible:
                reasons.append("eligible_but_outside_selection_limit")
            records.append(ResearchCandidateResult(
                opportunity_id=item["opportunity_id"],
                title=item["title"],
                research_candidate_score=item["score"],
                research_threshold=self.threshold,
                research_eligible=eligible,
                research_rank=rank,
                selected_for_external_research=item["opportunity_id"] in selected_ids,
                research_reasons=tuple(reasons),
                score_components=item["components"],
                final_investment_score=float(item["final_investment_score"]) if isinstance(item["final_investment_score"], (int, float)) else None,
            ))

        return ResearchCandidateReport(
            record_count=len(records),
            eligible_count=sum(record.research_eligible for record in records),
            selected_count=sum(record.selected_for_external_research for record in records),
            research_threshold=self.threshold,
            selection_limit=self.selection_limit,
            records=tuple(records),
        )
