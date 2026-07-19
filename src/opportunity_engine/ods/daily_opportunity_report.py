"""Daily ranking and concise reporting for opportunity decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .opportunity_profit import OpportunityProfitDecision


_DECISION_PRIORITY = {"buy": 3, "monitor": 2, "reject": 1}
_CONFIDENCE_SCORE = {"high": 1.0, "medium": 0.75, "low": 0.4, "insufficient": 0.0}


@dataclass(frozen=True)
class RankedDailyOpportunity:
    rank: int
    opportunity_id: str
    decision: str
    decision_label: str
    score: float
    expected_profit_nok: float | None
    roi: float | None
    confidence: str
    maximum_purchase_price_nok: float | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class DailyOpportunityReport:
    report_date: date
    total_count: int
    buy_count: int
    monitor_count: int
    reject_count: int
    ranked: tuple[RankedDailyOpportunity, ...]
    summary_lines: tuple[str, ...]

    @property
    def best(self) -> RankedDailyOpportunity | None:
        return self.ranked[0] if self.ranked else None


class DailyOpportunityReportEngine:
    """Rank decisions conservatively and build a human-readable daily report."""

    def build(
        self,
        decisions: Iterable[OpportunityProfitDecision],
        *,
        report_date: date | None = None,
        limit: int | None = None,
    ) -> DailyOpportunityReport:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")

        unique: dict[str, OpportunityProfitDecision] = {}
        for item in decisions:
            current = unique.get(item.opportunity_id)
            if current is None or self._score(item) > self._score(current):
                unique[item.opportunity_id] = item

        ordered = sorted(
            unique.values(),
            key=lambda item: (
                self._score(item),
                item.expected_profit_nok if item.expected_profit_nok is not None else float("-inf"),
                item.roi if item.roi is not None else float("-inf"),
                item.opportunity_id,
            ),
            reverse=True,
        )
        if limit is not None:
            ordered = ordered[:limit]

        ranked = tuple(
            RankedDailyOpportunity(
                rank=index,
                opportunity_id=item.opportunity_id,
                decision=item.decision,
                decision_label=item.decision_label,
                score=round(self._score(item), 2),
                expected_profit_nok=item.expected_profit_nok,
                roi=item.roi,
                confidence=item.confidence,
                maximum_purchase_price_nok=item.maximum_purchase_price_nok,
                reasons=item.reasons,
                warnings=item.warnings,
                blockers=item.blockers,
            )
            for index, item in enumerate(ordered, start=1)
        )

        all_items = tuple(unique.values())
        counts = {name: sum(item.decision == name for item in all_items) for name in _DECISION_PRIORITY}
        summary = self._summary(ranked, counts)
        return DailyOpportunityReport(
            report_date=report_date or date.today(),
            total_count=len(all_items),
            buy_count=counts["buy"],
            monitor_count=counts["monitor"],
            reject_count=counts["reject"],
            ranked=ranked,
            summary_lines=summary,
        )

    def _score(self, item: OpportunityProfitDecision) -> float:
        decision_component = _DECISION_PRIORITY.get(item.decision, 0) * 100.0
        confidence_component = _CONFIDENCE_SCORE.get(item.confidence, 0.0) * 20.0
        roi_component = max(-1.0, min(item.roi or 0.0, 2.0)) * 40.0
        profit_component = max(-20.0, min((item.expected_profit_nok or 0.0) / 1_000.0, 40.0))
        blocker_penalty = len(item.blockers) * 15.0
        warning_penalty = len(item.warnings) * 2.0
        actionable_bonus = 5.0 if item.is_actionable else 0.0
        return (
            decision_component
            + confidence_component
            + roi_component
            + profit_component
            + actionable_bonus
            - blocker_penalty
            - warning_penalty
        )

    @staticmethod
    def _summary(
        ranked: tuple[RankedDailyOpportunity, ...],
        counts: dict[str, int],
    ) -> tuple[str, ...]:
        lines = (
            f"الفرص: {sum(counts.values())} — شراء: {counts['buy']}، مراقبة: {counts['monitor']}، رفض: {counts['reject']}.",
        )
        if not ranked:
            return lines + ("لا توجد فرص قابلة للعرض اليوم.",)
        best = ranked[0]
        profit = "غير متوفر" if best.expected_profit_nok is None else f"{best.expected_profit_nok:,.0f} NOK"
        roi = "غير متوفر" if best.roi is None else f"{best.roi * 100:.1f}%"
        return lines + (
            f"أفضل فرصة: {best.opportunity_id} — {best.decision_label} — ربح {profit} — ROI {roi}.",
        )
