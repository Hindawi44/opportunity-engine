"""Build a conservative capital plan from the daily opportunity snapshot."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from .capital_allocation import (
    CapitalAllocationCandidate,
    CapitalAllocationEngine,
    CapitalAllocationPlan,
    CapitalAllocationPolicy,
)


class SnapshotCapitalAllocator:
    def __init__(self, engine: CapitalAllocationEngine | None = None) -> None:
        self.engine = engine or CapitalAllocationEngine()

    def process(
        self,
        snapshot_path: str | Path,
        *,
        total_capital_nok: float,
        reserve_fraction: float = 0.20,
        max_single_opportunity_fraction: float = 0.25,
        output_path: str | Path = "data/capital_allocation.json",
    ) -> CapitalAllocationPlan:
        snapshot_path = Path(snapshot_path)
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid opportunity snapshot: {snapshot_path}") from exc

        rows = payload.get("rows", [])
        discovery_by_id = payload.get("discovery_by_id", {})
        if not isinstance(rows, list) or not isinstance(discovery_by_id, dict):
            raise RuntimeError("Invalid opportunity snapshot schema")

        candidates = tuple(self._candidate(row, discovery_by_id) for row in rows if isinstance(row, dict))
        policy = CapitalAllocationPolicy(
            total_capital_nok=total_capital_nok,
            reserve_fraction=reserve_fraction,
            max_single_opportunity_fraction=max_single_opportunity_fraction,
        )
        plan = self.engine.allocate(candidates, policy)
        self._write_json_atomic(Path(output_path), {"schema_version": 1, **asdict(plan)})
        return plan

    @staticmethod
    def _candidate(row: dict[str, Any], discovery_by_id: dict[str, Any]) -> CapitalAllocationCandidate:
        opportunity_id = str(row.get("opportunity_id") or "").strip()
        discovery = discovery_by_id.get(opportunity_id, {})
        if not isinstance(discovery, dict):
            discovery = {}
        blockers = row.get("blockers", ())
        if not isinstance(blockers, (list, tuple)):
            blockers = ()
        return CapitalAllocationCandidate(
            opportunity_id=opportunity_id,
            decision=str(row.get("decision") or "monitor"),
            discovery_score=_number(discovery.get("discovery_score")) or 0.0,
            maximum_purchase_price_nok=_number(row.get("maximum_purchase_price_nok")),
            total_cost_nok=_number(row.get("total_cost_nok")),
            expected_profit_nok=_number(row.get("expected_profit_nok")),
            roi=_number(row.get("roi")),
            is_actionable=bool(discovery.get("is_exceptional") or discovery.get("requires_immediate_review")),
            blockers=tuple(str(item) for item in blockers),
        )

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


def _number(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
