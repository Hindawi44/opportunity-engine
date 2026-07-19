from datetime import date

import pytest

from opportunity_engine.ods.daily_opportunity_report import (
    DailyOpportunityReport,
    RankedDailyOpportunity,
)
from opportunity_engine.ods.today_dashboard import (
    OpportunityDisplayMetadata,
    build_today_dashboard,
)


def _ranked(opportunity_id: str, rank: int = 1) -> RankedDailyOpportunity:
    return RankedDailyOpportunity(
        rank=rank,
        opportunity_id=opportunity_id,
        decision="buy",
        decision_label="🟢 اشترِ",
        score=355.0,
        expected_profit_nok=12_000.0,
        roi=0.45,
        confidence="high",
        maximum_purchase_price_nok=20_000.0,
        reasons=("ربح جيد",),
        warnings=(),
        blockers=(),
    )


def test_builds_dashboard_rows_with_source_metadata() -> None:
    report = DailyOpportunityReport(
        report_date=date(2026, 7, 19),
        total_count=1,
        buy_count=1,
        monitor_count=0,
        reject_count=0,
        ranked=(_ranked("unified-auksjonen-123"),),
        summary_lines=("ملخص اليوم",),
    )
    metadata = {
        "unified-auksjonen-123": OpportunityDisplayMetadata(
            title="Butikkinnredning",
            url="https://www.auksjonen.no/auksjon/123",
            city="Trondheim",
            ends_at="2026-07-31T18:00:00+02:00",
        )
    }

    view = build_today_dashboard(report, metadata)

    assert view.report_date == "2026-07-19"
    assert view.best is not None
    assert view.best.title == "Butikkinnredning"
    assert view.best.url == "https://www.auksjonen.no/auksjon/123"
    assert view.best.maximum_purchase_price_nok == 20_000.0
    assert view.summary_lines == ("ملخص اليوم",)


def test_missing_metadata_uses_identifier_without_inventing_source_facts() -> None:
    report = DailyOpportunityReport(
        report_date=date(2026, 7, 19),
        total_count=1,
        buy_count=1,
        monitor_count=0,
        reject_count=0,
        ranked=(_ranked("opportunity-unknown"),),
        summary_lines=(),
    )

    row = build_today_dashboard(report).rows[0]

    assert row.title == "opportunity-unknown"
    assert row.url is None
    assert row.city is None
    assert row.ends_at is None


def test_display_metadata_rejects_insecure_links() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OpportunityDisplayMetadata(title="Listing", url="http://example.test/listing")
