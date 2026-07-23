"""Synchronize daily pipeline dashboard rows into Living Investment Files.

The synchronizer is intentionally additive: it preserves existing research,
updates only discovery fields, and records the old score/decision as internal
signals rather than presenting them as the final investment product.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .living_investment_file import (
    Confidence,
    Evidence,
    LivingInvestmentFile,
    LivingInvestmentFileRepository,
)


@dataclass(frozen=True)
class InvestmentFileSyncResult:
    created_count: int
    updated_count: int
    unchanged_count: int
    file_ids: tuple[str, ...]


class InvestmentFileSynchronizer:
    """Create or update one living file for every discovered dashboard row."""

    def __init__(self, root: str | Path = "data/investment_files") -> None:
        self.repository = LivingInvestmentFileRepository(root)

    def sync_payload(self, payload: dict[str, Any]) -> InvestmentFileSyncResult:
        rows = payload.get("rows", ())
        if not isinstance(rows, (list, tuple)):
            raise ValueError("Daily pipeline payload must contain a rows list")
        return self.sync_rows(rows)

    def sync_rows(self, rows: Iterable[dict[str, Any]]) -> InvestmentFileSyncResult:
        created = 0
        updated = 0
        unchanged = 0
        file_ids: list[str] = []

        for row in rows:
            opportunity_id = str(row.get("opportunity_id") or "").strip()
            title = str(row.get("title") or "").strip()
            if not opportunity_id or not title:
                continue

            try:
                item = self.repository.load(opportunity_id)
                existed = True
            except FileNotFoundError:
                item = LivingInvestmentFile.create(
                    opportunity_id=opportunity_id,
                    title=title,
                    source_url=_optional_text(row.get("url")),
                    location=_optional_text(row.get("city")),
                    asking_price_nok=_optional_non_negative_number(row.get("asking_price_nok")),
                    summary=_initial_summary(row),
                )
                existed = False

            changed = item.merge_discovery_update(
                {
                    "title": title,
                    "source_url": _optional_text(row.get("url")),
                    "summary": item.summary or _initial_summary(row),
                    "location": _optional_text(row.get("city")),
                    "asking_price_nok": _optional_non_negative_number(row.get("asking_price_nok")),
                }
            )

            signal_changed = _sync_internal_signal(item, row)
            evidence_changed = _add_verified_market_evidence(item, row)
            self.repository.save(item)
            file_ids.append(opportunity_id)

            if not existed:
                created += 1
            elif changed or signal_changed or evidence_changed:
                updated += 1
            else:
                unchanged += 1

        return InvestmentFileSyncResult(created, updated, unchanged, tuple(file_ids))


def _sync_internal_signal(item: LivingInvestmentFile, row: dict[str, Any]) -> bool:
    score = _optional_non_negative_number(row.get("score"))
    decision = _optional_text(row.get("decision"))
    changed = score != item.internal_score or decision != item.internal_signal
    if changed:
        item.internal_score = score
        item.internal_signal = decision
        item._touch(
            "internal_signal_updated",
            "Updated legacy score/decision as internal supporting metadata",
            ["internal_score", "internal_signal"],
        )
    return changed


def _add_verified_market_evidence(item: LivingInvestmentFile, row: dict[str, Any]) -> bool:
    if not row.get("market_is_verified"):
        return False
    market_value = _optional_non_negative_number(row.get("market_value_nok"))
    if market_value is None:
        return False
    statement = f"Verified conservative market value recorded at {market_value:.2f} NOK"
    if any(existing.statement == statement for existing in item.evidence):
        return False
    item.add_evidence(
        Evidence.create(
            statement,
            source_url=_optional_text(row.get("url")),
            source_name="daily_pipeline_market_verification",
            confidence=Confidence.MEDIUM,
        )
    )
    return True


def _initial_summary(row: dict[str, Any]) -> str:
    city = _optional_text(row.get("city"))
    decision_label = _optional_text(row.get("decision_label"))
    parts = ["Opportunity discovered automatically by the daily pipeline."]
    if city:
        parts.append(f"Location: {city}.")
    if decision_label:
        parts.append(f"Legacy internal signal: {decision_label}.")
    return " ".join(parts)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_non_negative_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
