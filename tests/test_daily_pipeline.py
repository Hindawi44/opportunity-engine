import json
from datetime import date

from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.live_data import SourceDocument
from opportunity_engine.ods.market_pricing import MarketComparable
from opportunity_engine.ods.real_cost import RealCostInputs


def _document() -> SourceDocument:
    return SourceDocument(
        document_id="auksjonen-123",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title="Butikkinnredning",
        text="Butikkinnredning | Salær: 10 % | inkl. mva",
        url="https://www.auksjonen.no/auksjon/123",
        country="Norway",
        metadata={
            "current_price_nok": 10_000,
            "city": "Trondheim",
            "ends_at": "2026-08-01T18:00:00+02:00",
            "mva_status": "included",
        },
    )


def test_pipeline_writes_complete_dashboard_snapshot(tmp_path) -> None:
    opportunity_id = "unified-auksjonen-123"
    output = tmp_path / "today.json"
    comparables = tuple(
        MarketComparable(
            comparable_id=f"c{index}",
            title="Comparable shop fittings",
            price_nok=price,
            source_name="verified",
        )
        for index, price in enumerate((24_000, 25_000, 26_000), start=1)
    )
    costs = RealCostInputs(
        purchase_price_nok=10_000,
        auction_fee_nok=1_000,
        vat_status="included",
        transport_nok=1_000,
        dismantling_nok=500,
        storage_nok=0,
        repair_nok=0,
        cleaning_nok=0,
        selling_cost_nok=500,
        other_cost_nok=0,
        contingency_rate=0.05,
    )

    result = AutomatedDailyPipeline().run(
        DailyPipelineConfig(output_path=str(output)),
        documents=(_document(),),
        comparables_by_id={opportunity_id: comparables},
        costs_by_id={opportunity_id: costs},
        report_date=date(2026, 7, 20),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.fetched_count == 1
    assert result.extracted_count == 1
    assert result.deduplicated_count == 1
    assert result.duplicate_count == 0
    assert payload["schema_version"] == 4
    assert payload["report_date"] == "2026-07-20"
    assert payload["rows"][0]["title"] == "Butikkinnredning"
    assert payload["rows"][0]["url"].startswith("https://")
    assert payload["buy_count"] == 1


def test_pipeline_keeps_unverified_opportunity_as_monitor(tmp_path) -> None:
    output = tmp_path / "today.json"
    AutomatedDailyPipeline().run(
        DailyPipelineConfig(output_path=str(output)),
        documents=(_document(),),
        report_date=date(2026, 7, 20),
    )
    row = json.loads(output.read_text(encoding="utf-8"))["rows"][0]
    assert row["decision"] == "monitor"
    assert "market_comparables" in row["blockers"]
    assert any(item.startswith("cost:") for item in row["blockers"])


def test_pipeline_supports_empty_collection(tmp_path) -> None:
    output = tmp_path / "today.json"
    result = AutomatedDailyPipeline().run(
        DailyPipelineConfig(output_path=str(output)),
        documents=(),
        report_date=date(2026, 7, 20),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.extracted_count == 0
    assert result.deduplicated_count == 0
    assert payload["rows"] == []
    assert payload["total_count"] == 0
