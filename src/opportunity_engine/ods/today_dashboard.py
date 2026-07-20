"""Presentation helpers for the Today's Opportunities Streamlit dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .daily_opportunity_report import DailyOpportunityReport


@dataclass(frozen=True)
class OpportunityDisplayMetadata:
    """Human-facing metadata joined to a ranked opportunity."""

    title: str
    url: str | None = None
    city: str | None = None
    ends_at: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.url is not None and not self.url.startswith("https://"):
            raise ValueError("url must use HTTPS")


@dataclass(frozen=True)
class TodayOpportunityRow:
    rank: int
    opportunity_id: str
    title: str
    url: str | None
    decision: str
    decision_label: str
    score: float
    score_grade: str
    score_breakdown: tuple[str, ...]
    expected_profit_nok: float | None
    roi: float | None
    maximum_purchase_price_nok: float | None
    confidence: str
    city: str | None
    ends_at: str | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class TodayDashboardView:
    report_date: str
    total_count: int
    buy_count: int
    monitor_count: int
    reject_count: int
    rows: tuple[TodayOpportunityRow, ...]
    summary_lines: tuple[str, ...]

    @property
    def best(self) -> TodayOpportunityRow | None:
        return self.rows[0] if self.rows else None


def build_today_dashboard(
    report: DailyOpportunityReport,
    metadata_by_id: Mapping[str, OpportunityDisplayMetadata] | None = None,
) -> TodayDashboardView:
    """Join ranking results with display metadata without inventing financial facts."""

    metadata_by_id = metadata_by_id or {}
    rows: list[TodayOpportunityRow] = []
    for item in report.ranked:
        metadata = metadata_by_id.get(item.opportunity_id)
        rows.append(
            TodayOpportunityRow(
                rank=item.rank,
                opportunity_id=item.opportunity_id,
                title=metadata.title if metadata else item.opportunity_id,
                url=metadata.url if metadata else None,
                decision=item.decision,
                decision_label=item.decision_label,
                score=item.score,
                score_grade=item.score_grade,
                score_breakdown=item.score_breakdown,
                expected_profit_nok=item.expected_profit_nok,
                roi=item.roi,
                maximum_purchase_price_nok=item.maximum_purchase_price_nok,
                confidence=item.confidence,
                city=metadata.city if metadata else None,
                ends_at=metadata.ends_at if metadata else None,
                reasons=item.reasons,
                warnings=item.warnings,
                blockers=item.blockers,
            )
        )

    return TodayDashboardView(
        report_date=report.report_date.isoformat(),
        total_count=report.total_count,
        buy_count=report.buy_count,
        monitor_count=report.monitor_count,
        reject_count=report.reject_count,
        rows=tuple(rows),
        summary_lines=report.summary_lines,
    )
