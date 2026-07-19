from datetime import date

import pytest

from opportunity_engine.ods.daily_opportunity_report import DailyOpportunityReportEngine
from opportunity_engine.ods.opportunity_profit import OpportunityProfitDecision


def _decision(
    opportunity_id: str,
    decision: str,
    *,
    profit: float | None,
    roi: float | None,
    confidence: str = "medium",
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    actionable: bool = True,
) -> OpportunityProfitDecision:
    labels = {"buy": "🟢 اشترِ", "monitor": "🟡 راقب", "reject": "🔴 ارفض"}
    return OpportunityProfitDecision(
        opportunity_id=opportunity_id,
        decision=decision,
        decision_label=labels[decision],
        conservative_resale_nok=20_000.0,
        total_cost_nok=10_000.0,
        expected_profit_nok=profit,
        roi=roi,
        margin_on_resale=0.5 if profit is not None else None,
        maximum_total_cost_nok=14_000.0,
        maximum_purchase_price_nok=9_000.0,
        confidence=confidence,
        blockers=blockers,
        warnings=warnings,
        reasons=("reason",),
        is_actionable=actionable,
    )


def test_ranks_buy_before_monitor_and_reject() -> None:
    report = DailyOpportunityReportEngine().build(
        (
            _decision("reject-1", "reject", profit=-500, roi=-0.05),
            _decision("monitor-1", "monitor", profit=2_500, roi=0.2),
            _decision("buy-1", "buy", profit=6_000, roi=0.6, confidence="high"),
        ),
        report_date=date(2026, 7, 19),
    )

    assert [item.opportunity_id for item in report.ranked] == ["buy-1", "monitor-1", "reject-1"]
    assert report.best is not None
    assert report.best.opportunity_id == "buy-1"
    assert report.buy_count == 1
    assert report.monitor_count == 1
    assert report.reject_count == 1
    assert report.report_date == date(2026, 7, 19)
    assert "أفضل فرصة: buy-1" in report.summary_lines[1]


def test_deduplicates_by_opportunity_and_keeps_stronger_result() -> None:
    report = DailyOpportunityReportEngine().build(
        (
            _decision("same", "monitor", profit=1_000, roi=0.1, confidence="low"),
            _decision("same", "buy", profit=5_000, roi=0.5, confidence="high"),
        )
    )

    assert report.total_count == 1
    assert report.ranked[0].decision == "buy"


def test_blockers_reduce_rank_and_non_actionable_is_preserved() -> None:
    blocked = _decision(
        "blocked",
        "monitor",
        profit=8_000,
        roi=0.8,
        confidence="insufficient",
        blockers=("market_comparables", "cost:transport_nok"),
        actionable=False,
    )
    clean = _decision("clean", "monitor", profit=2_000, roi=0.2, confidence="medium")

    report = DailyOpportunityReportEngine().build((blocked, clean))

    assert report.ranked[0].opportunity_id == "clean"
    assert report.ranked[1].blockers == blocked.blockers


def test_limit_and_empty_report() -> None:
    engine = DailyOpportunityReportEngine()
    report = engine.build(
        (
            _decision("a", "buy", profit=4_000, roi=0.4),
            _decision("b", "monitor", profit=2_000, roi=0.2),
        ),
        limit=1,
    )
    assert len(report.ranked) == 1

    empty = engine.build(())
    assert empty.best is None
    assert empty.total_count == 0
    assert empty.summary_lines[-1] == "لا توجد فرص قابلة للعرض اليوم."


def test_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        DailyOpportunityReportEngine().build((), limit=0)
