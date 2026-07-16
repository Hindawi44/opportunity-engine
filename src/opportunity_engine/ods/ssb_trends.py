"""Deterministic trend intelligence for SSB JSON-stat2 datasets.

The module extracts one comparable time series from a JSON-stat2 payload,
computes transparent growth metrics, and produces bounded category-specific
ranking adjustments. Missing or ambiguous data results in a neutral signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .ssb import SSBClient
from .ssb_market import SSB_RETAIL_TABLE_ID, SSB_RETAIL_TABLE_URL


@dataclass(frozen=True)
class SSBTrendSignal:
    table_id: str
    metric: str
    periods: tuple[str, ...]
    values: tuple[float, ...]
    latest_change_pct: float | None
    cagr_pct: float | None
    direction: str
    market_health_score: float
    confidence: float
    source_url: str
    explanation: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.direction not in {"up", "down", "stable", "insufficient"}:
            raise ValueError("unsupported trend direction")
        if not 0 <= self.market_health_score <= 100:
            raise ValueError("market_health_score must be between 0 and 100")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if len(self.periods) != len(self.values):
            raise ValueError("periods and values must have equal length")


@dataclass(frozen=True)
class TrendAdjustment:
    base_score: float
    adjustment: float
    final_score: float
    relevance: float
    reason: str


class SSBTrendIntelligenceService:
    """Load the curated retail table and derive a conservative market signal."""

    def __init__(self, client: SSBClient | None = None) -> None:
        self.client = client or SSBClient(language="en")

    def load_retail_trend(self) -> SSBTrendSignal:
        info = self.client.get_table_info(SSB_RETAIL_TABLE_ID)
        data = self.client.get_default_data(SSB_RETAIL_TABLE_ID)
        metric = str(info.get("label") or info.get("title") or "SSB retail indicator")
        return analyze_json_stat2(
            data,
            table_id=SSB_RETAIL_TABLE_ID,
            metric=metric,
            source_url=SSB_RETAIL_TABLE_URL,
        )


def analyze_json_stat2(
    payload: dict[str, Any],
    *,
    table_id: str,
    metric: str,
    source_url: str,
) -> SSBTrendSignal:
    periods, values = _extract_first_time_series(payload)
    return analyze_series(
        periods,
        values,
        table_id=table_id,
        metric=metric,
        source_url=source_url,
    )


def analyze_series(
    periods: tuple[str, ...],
    values: tuple[float, ...],
    *,
    table_id: str,
    metric: str,
    source_url: str,
) -> SSBTrendSignal:
    clean = tuple(
        (period, float(value))
        for period, value in zip(periods, values)
        if isinstance(value, (int, float)) and isfinite(float(value))
    )
    clean_periods = tuple(item[0] for item in clean)
    clean_values = tuple(item[1] for item in clean)

    if len(clean_values) < 2:
        return SSBTrendSignal(
            table_id=table_id,
            metric=metric,
            periods=clean_periods,
            values=clean_values,
            latest_change_pct=None,
            cagr_pct=None,
            direction="insufficient",
            market_health_score=50.0,
            confidence=0.0,
            source_url=source_url,
            explanation=("Not enough comparable numeric periods to infer a trend.",),
        )

    previous, latest = clean_values[-2], clean_values[-1]
    latest_change = _percentage_change(previous, latest)
    cagr = _cagr(clean_values[0], clean_values[-1], len(clean_values) - 1)

    directional_value = latest_change if latest_change is not None else cagr
    if directional_value is None or abs(directional_value) < 1.0:
        direction = "stable"
    elif directional_value > 0:
        direction = "up"
    else:
        direction = "down"

    health = 50.0
    if latest_change is not None:
        health += max(-20.0, min(20.0, latest_change * 2.0))
    if cagr is not None:
        health += max(-15.0, min(15.0, cagr * 1.5))
    health = round(max(0.0, min(100.0, health)), 2)

    confidence = min(1.0, 0.35 + 0.08 * len(clean_values))
    explanation = [f"Direction: {direction} across {len(clean_values)} comparable periods."]
    if latest_change is not None:
        explanation.append(f"Latest period change: {latest_change:+.2f}%.")
    if cagr is not None:
        explanation.append(f"Compound annual growth estimate: {cagr:+.2f}%.")
    explanation.append("Signal is descriptive official-statistics evidence, not a profitability forecast.")

    return SSBTrendSignal(
        table_id=table_id,
        metric=metric,
        periods=clean_periods,
        values=clean_values,
        latest_change_pct=latest_change,
        cagr_pct=cagr,
        direction=direction,
        market_health_score=health,
        confidence=round(confidence, 2),
        source_url=source_url,
        explanation=tuple(explanation),
    )


def calculate_trend_adjustment(
    *,
    base_score: float,
    category: str,
    signal: SSBTrendSignal,
    maximum_absolute_adjustment: float = 3.0,
) -> TrendAdjustment:
    """Apply a bounded adjustment based on observed direction and category fit."""
    if not 0 <= base_score <= 100:
        raise ValueError("base_score must be between 0 and 100")
    if not 0 <= maximum_absolute_adjustment <= 10:
        raise ValueError("maximum_absolute_adjustment must be between 0 and 10")

    if signal.direction == "insufficient":
        return TrendAdjustment(base_score, 0.0, base_score, 0.0, "Insufficient comparable SSB periods.")

    growth_relevance = {
        "supplier_enablement": 1.00,
        "fit_data": 0.90,
        "logistics": 0.85,
        "industry_structure": 0.75,
        "membership": 0.65,
    }
    pressure_relevance = {
        "inventory": 1.00,
        "resale": 0.95,
        "returns": 0.90,
        "circular_economy": 0.85,
        "compliance_data": 0.55,
    }

    if signal.direction == "up":
        relevance = growth_relevance.get(category, 0.35)
        sign = 1.0
        thesis = "market expansion relevance"
    elif signal.direction == "down":
        relevance = pressure_relevance.get(category, 0.35)
        sign = 1.0
        thesis = "market-pressure problem relevance"
    else:
        relevance = 0.25
        sign = 0.25
        thesis = "stable-market relevance"

    strength = abs((signal.latest_change_pct or signal.cagr_pct or 0.0))
    normalized_strength = min(1.0, strength / 10.0)
    adjustment = maximum_absolute_adjustment * relevance * signal.confidence * normalized_strength * sign
    adjustment = round(adjustment, 2)
    final_score = round(min(100.0, max(0.0, base_score + adjustment)), 2)
    return TrendAdjustment(
        base_score=base_score,
        adjustment=adjustment,
        final_score=final_score,
        relevance=relevance,
        reason=f"SSB {signal.direction} trend; {thesis}; bounded descriptive adjustment.",
    )


def _extract_first_time_series(payload: dict[str, Any]) -> tuple[tuple[str, ...], tuple[float, ...]]:
    dimension_ids = payload.get("id")
    sizes = payload.get("size")
    dimensions = payload.get("dimension")
    raw_values = payload.get("value")
    if not isinstance(dimension_ids, list) or not isinstance(sizes, list):
        return (), ()
    if not isinstance(dimensions, dict) or not isinstance(raw_values, list):
        return (), ()
    if len(dimension_ids) != len(sizes) or not sizes:
        return (), ()

    time_axis = _find_time_axis(dimension_ids, dimensions)
    if time_axis is None:
        return (), ()
    periods = _ordered_categories(dimensions.get(dimension_ids[time_axis], {}))
    if not periods:
        return (), ()

    strides: list[int] = []
    for axis in range(len(sizes)):
        stride = 1
        for later_size in sizes[axis + 1 :]:
            if not isinstance(later_size, int):
                return (), ()
            stride *= later_size
        strides.append(stride)

    values: list[float] = []
    valid_periods: list[str] = []
    for time_index, period in enumerate(periods):
        flat_index = time_index * strides[time_axis]
        if flat_index >= len(raw_values):
            continue
        raw = raw_values[flat_index]
        if isinstance(raw, (int, float)) and isfinite(float(raw)):
            valid_periods.append(period)
            values.append(float(raw))
    return tuple(valid_periods), tuple(values)


def _find_time_axis(ids: list[Any], dimensions: dict[str, Any]) -> int | None:
    preferred = ("time", "tid", "year", "år", "periode", "period")
    for index, raw_id in enumerate(ids):
        dim_id = str(raw_id)
        label = str(dimensions.get(dim_id, {}).get("label", ""))
        combined = f"{dim_id} {label}".casefold()
        if any(token in combined for token in preferred):
            return index
    return None


def _ordered_categories(dimension: Any) -> tuple[str, ...]:
    if not isinstance(dimension, dict):
        return ()
    category = dimension.get("category")
    if not isinstance(category, dict):
        return ()
    index = category.get("index")
    if isinstance(index, list):
        return tuple(str(item) for item in index)
    if isinstance(index, dict):
        return tuple(str(key) for key, _ in sorted(index.items(), key=lambda item: item[1]))
    labels = category.get("label")
    if isinstance(labels, dict):
        return tuple(str(key) for key in labels)
    return ()


def _percentage_change(previous: float, latest: float) -> float | None:
    if previous == 0:
        return None
    return round(((latest - previous) / abs(previous)) * 100.0, 2)


def _cagr(first: float, last: float, periods: int) -> float | None:
    if first <= 0 or last < 0 or periods <= 0:
        return None
    return round(((last / first) ** (1.0 / periods) - 1.0) * 100.0, 2)
