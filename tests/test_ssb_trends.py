from opportunity_engine.ods import (
    SSBTrendSignal,
    analyze_json_stat2,
    analyze_series,
    calculate_trend_adjustment,
)


def _json_stat_payload() -> dict:
    return {
        "id": ["ContentsCode", "Tid"],
        "size": [1, 4],
        "dimension": {
            "ContentsCode": {
                "label": "Contents",
                "category": {"index": {"Turnover": 0}},
            },
            "Tid": {
                "label": "Year",
                "category": {
                    "index": {"2021": 0, "2022": 1, "2023": 2, "2024": 3}
                },
            },
        },
        "value": [100.0, 104.0, 108.0, 113.4],
    }


def test_analyze_json_stat2_extracts_time_series_and_growth() -> None:
    signal = analyze_json_stat2(
        _json_stat_payload(),
        table_id="12938",
        metric="Turnover",
        source_url="https://example.test/12938",
    )

    assert signal.periods == ("2021", "2022", "2023", "2024")
    assert signal.values == (100.0, 104.0, 108.0, 113.4)
    assert signal.latest_change_pct == 5.0
    assert signal.direction == "up"
    assert signal.market_health_score > 50
    assert signal.confidence > 0


def test_analyze_series_classifies_decline() -> None:
    signal = analyze_series(
        ("2022", "2023", "2024"),
        (100.0, 94.0, 88.0),
        table_id="12938",
        metric="Retail",
        source_url="https://example.test",
    )

    assert signal.direction == "down"
    assert signal.latest_change_pct < 0
    assert signal.cagr_pct < 0
    assert signal.market_health_score < 50


def test_analyze_series_is_neutral_with_insufficient_values() -> None:
    signal = analyze_series(
        ("2024",),
        (100.0,),
        table_id="12938",
        metric="Retail",
        source_url="https://example.test",
    )

    assert signal.direction == "insufficient"
    assert signal.market_health_score == 50.0
    assert signal.confidence == 0.0


def test_growth_trend_prioritizes_growth_relevant_category() -> None:
    signal = SSBTrendSignal(
        table_id="12938",
        metric="Retail",
        periods=("2023", "2024"),
        values=(100.0, 110.0),
        latest_change_pct=10.0,
        cagr_pct=10.0,
        direction="up",
        market_health_score=85.0,
        confidence=0.9,
        source_url="https://example.test",
        explanation=("up",),
    )

    supplier = calculate_trend_adjustment(base_score=70, category="supplier_enablement", signal=signal)
    inventory = calculate_trend_adjustment(base_score=70, category="inventory", signal=signal)

    assert supplier.adjustment > inventory.adjustment
    assert 0 < supplier.adjustment <= 3.0


def test_decline_trend_prioritizes_pressure_solution_category() -> None:
    signal = SSBTrendSignal(
        table_id="12938",
        metric="Retail",
        periods=("2023", "2024"),
        values=(100.0, 90.0),
        latest_change_pct=-10.0,
        cagr_pct=-10.0,
        direction="down",
        market_health_score=20.0,
        confidence=1.0,
        source_url="https://example.test",
        explanation=("down",),
    )

    inventory = calculate_trend_adjustment(base_score=70, category="inventory", signal=signal)
    supplier = calculate_trend_adjustment(base_score=70, category="supplier_enablement", signal=signal)

    assert inventory.adjustment > supplier.adjustment
    assert inventory.final_score == 73.0


def test_trend_adjustment_never_exceeds_score_bounds() -> None:
    signal = SSBTrendSignal(
        table_id="12938",
        metric="Retail",
        periods=("2023", "2024"),
        values=(100.0, 200.0),
        latest_change_pct=100.0,
        cagr_pct=100.0,
        direction="up",
        market_health_score=100.0,
        confidence=1.0,
        source_url="https://example.test",
        explanation=("up",),
    )

    adjustment = calculate_trend_adjustment(
        base_score=99.0,
        category="supplier_enablement",
        signal=signal,
    )

    assert adjustment.adjustment == 3.0
    assert adjustment.final_score == 100.0
