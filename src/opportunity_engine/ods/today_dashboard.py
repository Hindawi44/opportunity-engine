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
    asking_price_nok: float | None = None
    market_value_nok: float | None = None
    market_median_nok: float | None = None
    market_discount: float | None = None
    market_verification_status: str = "unavailable"
    market_verification_label: str = "⚪ سوق غير متحقق"
    market_comparable_count: int = 0
    market_is_verified: bool = False
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    first_price_nok: float | None = None
    lowest_price_nok: float | None = None
    highest_price_nok: float | None = None
    price_change_count: int = 0
    price_change_from_first: float | None = None
    listing_age_days: int = 0
    price_history_status: str = "unpriced"
    price_history_label: str = "⚪ لا يوجد سعر"
    significant_price_drop: bool = False

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
    asking_price_nok: float | None
    market_value_nok: float | None
    market_median_nok: float | None
    market_discount: float | None
    market_verification_status: str
    market_verification_label: str
    market_comparable_count: int
    market_is_verified: bool
    first_seen_at: str | None
    last_seen_at: str | None
    first_price_nok: float | None
    lowest_price_nok: float | None
    highest_price_nok: float | None
    price_change_count: int
    price_change_from_first: float | None
    listing_age_days: int
    price_history_status: str
    price_history_label: str
    significant_price_drop: bool
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
                asking_price_nok=metadata.asking_price_nok if metadata else None,
                market_value_nok=metadata.market_value_nok if metadata else None,
                market_median_nok=metadata.market_median_nok if metadata else None,
                market_discount=metadata.market_discount if metadata else None,
                market_verification_status=(metadata.market_verification_status if metadata else "unavailable"),
                market_verification_label=(metadata.market_verification_label if metadata else "⚪ سوق غير متحقق"),
                market_comparable_count=metadata.market_comparable_count if metadata else 0,
                market_is_verified=metadata.market_is_verified if metadata else False,
                first_seen_at=metadata.first_seen_at if metadata else None,
                last_seen_at=metadata.last_seen_at if metadata else None,
                first_price_nok=metadata.first_price_nok if metadata else None,
                lowest_price_nok=metadata.lowest_price_nok if metadata else None,
                highest_price_nok=metadata.highest_price_nok if metadata else None,
                price_change_count=metadata.price_change_count if metadata else 0,
                price_change_from_first=metadata.price_change_from_first if metadata else None,
                listing_age_days=metadata.listing_age_days if metadata else 0,
                price_history_status=metadata.price_history_status if metadata else "unpriced",
                price_history_label=metadata.price_history_label if metadata else "⚪ لا يوجد سعر",
                significant_price_drop=metadata.significant_price_drop if metadata else False,
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
