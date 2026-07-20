"""Persistent portfolio manager for manually confirmed purchases and sales.

The manager records only explicit transactions. It never buys, sells, or infers a
transaction from an opportunity recommendation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PortfolioPosition:
    opportunity_id: str
    title: str
    status: str
    purchased_at: str
    purchase_price_nok: float
    acquisition_cost_nok: float
    total_invested_nok: float
    estimated_value_nok: float | None
    sold_at: str | None
    sale_price_nok: float | None
    selling_cost_nok: float
    realized_profit_nok: float | None
    unrealized_profit_nok: float | None
    roi: float | None
    notes: str | None


@dataclass(frozen=True)
class PortfolioSnapshot:
    initial_capital_nok: float
    cash_balance_nok: float
    invested_capital_nok: float
    estimated_open_value_nok: float
    realized_profit_nok: float
    unrealized_profit_nok: float
    total_equity_nok: float
    open_position_count: int
    closed_position_count: int
    positions: tuple[PortfolioPosition, ...]


class PortfolioManager:
    """Atomic JSON portfolio ledger with duplicate-purchase protection."""

    def __init__(self, path: str | Path, *, initial_capital_nok: float | None = None) -> None:
        self.path = Path(path)
        self._data = self._load(initial_capital_nok)

    def record_purchase(
        self,
        *,
        opportunity_id: str,
        title: str,
        purchase_price_nok: float,
        acquisition_cost_nok: float = 0.0,
        purchased_at: datetime | None = None,
        estimated_value_nok: float | None = None,
        notes: str | None = None,
    ) -> PortfolioPosition:
        opportunity_id = opportunity_id.strip()
        title = title.strip()
        if not opportunity_id:
            raise ValueError("opportunity_id must not be empty")
        if not title:
            raise ValueError("title must not be empty")
        for value, name in (
            (purchase_price_nok, "purchase_price_nok"),
            (acquisition_cost_nok, "acquisition_cost_nok"),
        ):
            if value < 0:
                raise ValueError(f"{name} must not be negative")
        if estimated_value_nok is not None and estimated_value_nok < 0:
            raise ValueError("estimated_value_nok must not be negative")

        positions = self._data["positions"]
        existing = positions.get(opportunity_id)
        if existing is not None:
            raise ValueError("opportunity is already recorded in the portfolio")

        total = round(float(purchase_price_nok) + float(acquisition_cost_nok), 2)
        if total > float(self._data["cash_balance_nok"]):
            raise ValueError("insufficient cash balance")

        timestamp = _timestamp(purchased_at)
        entry = {
            "opportunity_id": opportunity_id,
            "title": title,
            "status": "open",
            "purchased_at": timestamp,
            "purchase_price_nok": round(float(purchase_price_nok), 2),
            "acquisition_cost_nok": round(float(acquisition_cost_nok), 2),
            "estimated_value_nok": None if estimated_value_nok is None else round(float(estimated_value_nok), 2),
            "sold_at": None,
            "sale_price_nok": None,
            "selling_cost_nok": 0.0,
            "notes": notes.strip() if notes and notes.strip() else None,
        }
        positions[opportunity_id] = entry
        self._data["cash_balance_nok"] = round(float(self._data["cash_balance_nok"]) - total, 2)
        self.save()
        return self._position(entry)

    def update_estimated_value(self, opportunity_id: str, estimated_value_nok: float | None) -> PortfolioPosition:
        if estimated_value_nok is not None and estimated_value_nok < 0:
            raise ValueError("estimated_value_nok must not be negative")
        entry = self._entry(opportunity_id)
        if entry["status"] != "open":
            raise ValueError("estimated value can only be updated for an open position")
        entry["estimated_value_nok"] = None if estimated_value_nok is None else round(float(estimated_value_nok), 2)
        self.save()
        return self._position(entry)

    def record_sale(
        self,
        opportunity_id: str,
        *,
        sale_price_nok: float,
        selling_cost_nok: float = 0.0,
        sold_at: datetime | None = None,
    ) -> PortfolioPosition:
        if sale_price_nok < 0 or selling_cost_nok < 0:
            raise ValueError("sale price and selling cost must not be negative")
        entry = self._entry(opportunity_id)
        if entry["status"] != "open":
            raise ValueError("position is already closed")

        net_proceeds = round(float(sale_price_nok) - float(selling_cost_nok), 2)
        entry["status"] = "closed"
        entry["sold_at"] = _timestamp(sold_at)
        entry["sale_price_nok"] = round(float(sale_price_nok), 2)
        entry["selling_cost_nok"] = round(float(selling_cost_nok), 2)
        entry["estimated_value_nok"] = None
        self._data["cash_balance_nok"] = round(float(self._data["cash_balance_nok"]) + net_proceeds, 2)
        self.save()
        return self._position(entry)

    def snapshot(self) -> PortfolioSnapshot:
        positions = tuple(self._position(item) for item in self._data["positions"].values())
        open_positions = tuple(item for item in positions if item.status == "open")
        closed_positions = tuple(item for item in positions if item.status == "closed")
        invested = round(sum(item.total_invested_nok for item in open_positions), 2)
        estimated_open = round(
            sum(item.estimated_value_nok if item.estimated_value_nok is not None else item.total_invested_nok for item in open_positions),
            2,
        )
        realized = round(sum(item.realized_profit_nok or 0.0 for item in closed_positions), 2)
        unrealized = round(sum(item.unrealized_profit_nok or 0.0 for item in open_positions), 2)
        cash = round(float(self._data["cash_balance_nok"]), 2)
        return PortfolioSnapshot(
            initial_capital_nok=round(float(self._data["initial_capital_nok"]), 2),
            cash_balance_nok=cash,
            invested_capital_nok=invested,
            estimated_open_value_nok=estimated_open,
            realized_profit_nok=realized,
            unrealized_profit_nok=unrealized,
            total_equity_nok=round(cash + estimated_open, 2),
            open_position_count=len(open_positions),
            closed_position_count=len(closed_positions),
            positions=positions,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def _load(self, initial_capital_nok: float | None) -> dict[str, Any]:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Invalid portfolio database: {self.path}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("positions"), dict):
                raise RuntimeError(f"Invalid portfolio database schema: {self.path}")
            return payload
        if initial_capital_nok is None:
            raise ValueError("initial_capital_nok is required when creating a new portfolio")
        if initial_capital_nok < 0:
            raise ValueError("initial_capital_nok must not be negative")
        amount = round(float(initial_capital_nok), 2)
        return {"schema_version": 1, "initial_capital_nok": amount, "cash_balance_nok": amount, "positions": {}}

    def _entry(self, opportunity_id: str) -> dict[str, Any]:
        entry = self._data["positions"].get(opportunity_id.strip())
        if entry is None:
            raise KeyError(f"unknown opportunity_id: {opportunity_id}")
        return entry

    @staticmethod
    def _position(entry: dict[str, Any]) -> PortfolioPosition:
        total = round(float(entry["purchase_price_nok"]) + float(entry["acquisition_cost_nok"]), 2)
        realized = None
        unrealized = None
        roi = None
        if entry["status"] == "closed":
            net = float(entry["sale_price_nok"]) - float(entry["selling_cost_nok"])
            realized = round(net - total, 2)
            roi = None if total <= 0 else round(realized / total, 4)
        elif entry.get("estimated_value_nok") is not None:
            unrealized = round(float(entry["estimated_value_nok"]) - total, 2)
            roi = None if total <= 0 else round(unrealized / total, 4)
        return PortfolioPosition(
            opportunity_id=str(entry["opportunity_id"]),
            title=str(entry["title"]),
            status=str(entry["status"]),
            purchased_at=str(entry["purchased_at"]),
            purchase_price_nok=float(entry["purchase_price_nok"]),
            acquisition_cost_nok=float(entry["acquisition_cost_nok"]),
            total_invested_nok=total,
            estimated_value_nok=entry.get("estimated_value_nok"),
            sold_at=entry.get("sold_at"),
            sale_price_nok=entry.get("sale_price_nok"),
            selling_cost_nok=float(entry.get("selling_cost_nok", 0.0)),
            realized_profit_nok=realized,
            unrealized_profit_nok=unrealized,
            roi=roi,
            notes=entry.get("notes"),
        )


def snapshot_to_dict(snapshot: PortfolioSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


def _timestamp(value: datetime | None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
