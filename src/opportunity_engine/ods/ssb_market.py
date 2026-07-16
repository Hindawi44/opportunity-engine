"""Market-evidence integration for selected official SSB tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ssb import SSBClient

SSB_RETAIL_TABLE_ID = "12938"
SSB_RETAIL_TABLE_URL = "https://www.ssb.no/en/statbank1/table/12938"


@dataclass(frozen=True)
class SSBMarketEvidence:
    table_id: str
    title: str
    first_period: str | None
    last_period: str | None
    variables: tuple[str, ...]
    value_count: int
    source_url: str
    evidence_score: float
    interpretation: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.table_id or not self.title:
            raise ValueError("table_id and title must not be empty")
        if not 0 <= self.evidence_score <= 100:
            raise ValueError("evidence_score must be between 0 and 100")


class SSBMarketEvidenceService:
    """Load and interpret a curated SSB retail-market evidence table."""

    def __init__(self, client: SSBClient | None = None) -> None:
        self.client = client or SSBClient(language="en")

    def load_retail_evidence(self) -> SSBMarketEvidence:
        info = self.client.get_table_info(SSB_RETAIL_TABLE_ID)
        data = self.client.get_default_data(SSB_RETAIL_TABLE_ID)
        return self.from_payloads(info, data)

    @staticmethod
    def from_payloads(info: dict[str, Any], data: dict[str, Any]) -> SSBMarketEvidence:
        title = str(info.get("label") or info.get("title") or "SSB retail market table")
        first_period = _optional_text(info.get("firstPeriod"))
        last_period = _optional_text(info.get("lastPeriod"))
        raw_variables = info.get("variableNames", ())
        variables = tuple(str(item) for item in raw_variables) if isinstance(raw_variables, list) else ()
        values = data.get("value", ())
        value_count = len(values) if isinstance(values, list) else 0

        interpretation = [
            "Official SSB evidence for wholesale and retail trade market structure.",
            "Use this table to test whether turnover, employment, online sales, and business counts support the opportunity thesis.",
        ]
        if first_period or last_period:
            interpretation.append(f"Available period: {first_period or '?'} to {last_period or '?' }.")
        if value_count:
            interpretation.append(f"The default JSON-stat2 extraction contains {value_count} observations.")

        score = 50.0
        if last_period:
            score += 15
        if len(variables) >= 3:
            score += 15
        if value_count >= 2:
            score += 10
        if value_count >= 10:
            score += 10

        return SSBMarketEvidence(
            table_id=SSB_RETAIL_TABLE_ID,
            title=title,
            first_period=first_period,
            last_period=last_period,
            variables=variables,
            value_count=value_count,
            source_url=SSB_RETAIL_TABLE_URL,
            evidence_score=min(100.0, score),
            interpretation=tuple(interpretation),
        )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
