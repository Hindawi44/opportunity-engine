"""Persistent, auditable price history for opportunity listings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(frozen=True)
class PriceHistorySummary:
    opportunity_id: str
    first_seen_at: str
    last_seen_at: str
    first_price_nok: float | None
    current_price_nok: float | None
    lowest_price_nok: float | None
    highest_price_nok: float | None
    price_change_count: int
    change_from_first: float | None
    age_days: int
    status: str
    status_label: str
    significant_drop: bool


class HistoricalPriceDatabase:
    """Store listing price changes in an atomic JSON database.

    Missing prices remain missing. The database records observations only when a
    numeric price is available and never converts unknown prices to zero.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data = self._load()

    def record(
        self,
        opportunity_id: str,
        price_nok: float | None,
        *,
        observed_at: datetime | None = None,
    ) -> PriceHistorySummary:
        if not opportunity_id.strip():
            raise ValueError("opportunity_id must not be empty")
        if price_nok is not None and price_nok < 0:
            raise ValueError("price_nok must not be negative")

        observed_at = observed_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        observed_at = observed_at.astimezone(timezone.utc)
        timestamp = observed_at.isoformat()

        opportunities = self._data.setdefault("opportunities", {})
        entry = opportunities.setdefault(
            opportunity_id,
            {"first_seen_at": timestamp, "last_seen_at": timestamp, "prices": []},
        )
        entry["last_seen_at"] = timestamp
        prices = entry.setdefault("prices", [])

        if price_nok is not None:
            rounded = round(float(price_nok), 2)
            last_price = prices[-1]["price_nok"] if prices else None
            if last_price != rounded:
                prices.append({"observed_at": timestamp, "price_nok": rounded})

        return self._summary(opportunity_id, entry, observed_at)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"schema_version": 1, "opportunities": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid price history database: {self.path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("opportunities"), dict):
            raise RuntimeError(f"Invalid price history database schema: {self.path}")
        payload.setdefault("schema_version", 1)
        return payload

    @staticmethod
    def _summary(
        opportunity_id: str,
        entry: dict[str, object],
        observed_at: datetime,
    ) -> PriceHistorySummary:
        observations = entry.get("prices", [])
        values = [float(item["price_nok"]) for item in observations]
        first_price = values[0] if values else None
        current_price = values[-1] if values else None
        change = None
        if first_price is not None and current_price is not None and first_price > 0:
            change = round((current_price - first_price) / first_price, 4)

        if not values:
            status, label = "unpriced", "⚪ لا يوجد سعر"
        elif len(values) == 1:
            status, label = "new", "🔵 سعر أولي"
        elif values[-1] < values[-2]:
            status, label = "price_drop", "🟢 انخفض السعر"
        elif values[-1] > values[-2]:
            status, label = "price_increase", "🔴 ارتفع السعر"
        else:
            status, label = "unchanged", "⚪ دون تغيير"

        first_seen = datetime.fromisoformat(str(entry["first_seen_at"]))
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)
        age_days = max(0, (observed_at - first_seen.astimezone(timezone.utc)).days)
        return PriceHistorySummary(
            opportunity_id=opportunity_id,
            first_seen_at=str(entry["first_seen_at"]),
            last_seen_at=str(entry["last_seen_at"]),
            first_price_nok=first_price,
            current_price_nok=current_price,
            lowest_price_nok=min(values) if values else None,
            highest_price_nok=max(values) if values else None,
            price_change_count=max(0, len(values) - 1),
            change_from_first=change,
            age_days=age_days,
            status=status,
            status_label=label,
            significant_drop=change is not None and change <= -0.10,
        )
