import json
from datetime import date

from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.live_data import SourceDocument
from opportunity_engine.ods.market_pricing import MarketComparable
from opportunity_engine.ods.real_cost import RealCostInputs


def _document(price: float = 10_000) -> SourceDocument:
    return SourceDocument(
        document_id="auksjonen-123",
        source_name="Auksjonen.no",
        source_type="public_auction_listing",
        title="Butikkinnredning",
        text="Butikkinnredning | Salær: 10 % | inkl. mva",
        url="https://www.auksjonen.no/auksjon/123",
        country="Norway",
        metadata={
            "current_price_nok": price,
            "city": "Trondheim",
            "ends_at": "2026-08-01T18:00:00+02:00",
            "mva_status": "included",
            "seller_id": "seller-123",
            "seller_name": "Verified Asset AS",
            "seller_type": "company",
            "seller_verified": True,
            "seller_rating": 4.7,
            "seller_review_count": 24,
            "seller_account_age_days": 1200,
            "seller_listing_count": 40,
            "seller_relist_count": 0,
        },
    )


def test_pipeline_writes_complete_dashboard_snapshot(tmp_path) -> None:
    opportunity_id = "unified-auksjonen-123"
    output = tmp_path / "today.json"
    history = tmp_path / "history.json"
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
        DailyPipelineConfig(output_path=str(output), history_path=str(history)),
        documents=(_document(),),
        comparables_by_id={opportunity_id: comparables},
        costs_by_id={opportunity_id: costs},
        report_date=date(2026, 7, 20),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    intelligence = payload["intelligence_by_id"][opportunity_id]
    assert result.fetched_count == 1
    assert result.extracted_count == 1
    assert result.deduplicated_count == 1
    assert result.duplicate_count == 0
    assert result.history_path == str(history)
    assert payload["schema_version"] == 10
    assert payload["report_date"] == "2026-07-20"
    assert row["title"] == "Butikkinnredning"
    assert row["url"].startswith("https://")
    assert 0 <= row["score"] <= 100
    assert row["score_grade"] in {"A", "B", "C", "D", "E"}
    assert row["score_breakdown"]
    assert row["asking_price_nok"] == 10_000
    assert row["market_value_nok"] is not None
    assert row["market_discount"] > 0
    assert row["market_verification_status"] == "strong_discount"
    assert row["market_is_verified"] is True
    assert row["first_price_nok"] == 10_000
    assert row["lowest_price_nok"] == 10_000
    assert row["price_change_count"] == 0
    assert row["price_history_status"] == "new"
    assert row["seller_id"] == "seller-123"
    assert row["seller_name"] == "Verified Asset AS"
    assert row["seller_score"] >= 75
    assert row["seller_grade"] in {"A", "B"}
    assert row["seller_risk"] == "low"
    assert row["seller_is_verified"] is True
    assert intelligence["recommendation"] == "buy"
    assert intelligence["strengths"]
    assert intelligence["next_actions"]
    assert intelligence["headline"]
    assert history.exists()
    assert payload["buy_count"] == 1


def test_pipeline_detects_price_drop_across_runs(tmp_path) -> None:
    output = tmp_path / "today.json"
    history = tmp_path / "history.json"
    config = DailyPipelineConfig(output_path=str(output), history_path=str(history))
    pipeline = AutomatedDailyPipeline()

    pipeline.run(config, documents=(_document(10_000),), report_date=date(2026, 7, 20))
    pipeline.run(config, documents=(_document(8_000),), report_date=date(2026, 7, 22))

    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    intelligence = payload["intelligence_by_id"]["unified-auksjonen-123"]
    assert row["first_price_nok"] == 10_000
    assert row["lowest_price_nok"] == 8_000
    assert row["highest_price_nok"] == 10_000
    assert row["price_change_count"] == 1
    assert row["price_change_from_first"] == -0.2
    assert row["listing_age_days"] == 2
    assert row["price_history_status"] == "price_drop"
    assert row["significant_price_drop"] is True
    assert any("انخفض" in item for item in intelligence["strengths"])


def test_pipeline_keeps_unverified_opportunity_as_monitor(tmp_path) -> None:
    output = tmp_path / "today.json"
    history = tmp_path / "history.json"
    document = _document()
    document = SourceDocument(
        document_id=document.document_id,
        source_name=document.source_name,
        source_type=document.source_type,
        title=document.title,
        text=document.text,
        url=document.url,
        country=document.country,
        metadata={key: value for key, value in document.metadata.items() if not key.startswith("seller_")},
    )
    AutomatedDailyPipeline().run(
        DailyPipelineConfig(output_path=str(output), history_path=str(history)),
        documents=(document,),
        report_date=date(2026, 7, 20),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    intelligence = payload["intelligence_by_id"]["unified-auksjonen-123"]
    assert row["decision"] == "monitor"
    assert row["score"] <= 59
    assert row["market_verification_status"] == "unavailable"
    assert row["market_is_verified"] is False
    assert row["seller_score"] is None
    assert row["seller_grade"] == "U"
    assert row["seller_risk"] == "unknown"
    assert intelligence["recommendation"] == "monitor"
    assert intelligence["missing_evidence"]
    assert intelligence["is_actionable"] is False
    assert "market_comparables" in row["blockers"]
    assert any(item.startswith("cost:") for item in row["blockers"])


def test_pipeline_supports_empty_collection(tmp_path) -> None:
    output = tmp_path / "today.json"
    history = tmp_path / "history.json"
    result = AutomatedDailyPipeline().run(
        DailyPipelineConfig(output_path=str(output), history_path=str(history)),
        documents=(),
        report_date=date(2026, 7, 20),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.extracted_count == 0
    assert result.deduplicated_count == 0
    assert payload["rows"] == []
    assert payload["intelligence_by_id"] == {}
    assert payload["total_count"] == 0
