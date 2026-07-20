"""Create a persistent, deduplicated alert outbox from the daily snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class SnapshotAlertProcessor:
    def process(self, snapshot_path: str, alerts_path: str) -> tuple[dict[str, Any], ...]:
        snapshot_file = Path(snapshot_path)
        payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        state_file = Path(alerts_path)
        state = self._load(state_file)
        seen = set(state["signatures"])
        rows = {row["opportunity_id"]: row for row in payload.get("rows", [])}
        intelligence = payload.get("intelligence_by_id", {})
        alerts: list[dict[str, Any]] = []

        for opportunity_id, discovery in payload.get("discovery_by_id", {}).items():
            row = rows.get(opportunity_id, {})
            alert_type = None
            if discovery.get("is_exceptional"):
                alert_type = "exceptional_opportunity"
            elif discovery.get("requires_immediate_review"):
                alert_type = "immediate_review"
            elif discovery.get("discovery_score", 0) >= 70:
                alert_type = "strong_opportunity"
            elif row.get("significant_price_drop"):
                alert_type = "significant_price_drop"
            elif row.get("decision") == "buy" and (row.get("expected_profit_nok") or 0) >= 2_000:
                alert_type = "verified_profit"
            if alert_type is None:
                continue

            signature = self._signature(
                opportunity_id,
                alert_type,
                row.get("asking_price_nok"),
                row.get("price_change_count"),
                discovery.get("discovery_score"),
            )
            if signature in seen:
                continue
            seen.add(signature)
            alerts.append(
                {
                    "alert_id": signature,
                    "opportunity_id": opportunity_id,
                    "alert_type": alert_type,
                    "severity": "critical" if discovery.get("is_exceptional") else "high",
                    "title": row.get("title") or opportunity_id,
                    "url": row.get("url"),
                    "created_at": payload.get("generated_at"),
                    "discovery_score": discovery.get("discovery_score"),
                    "expected_profit_nok": row.get("expected_profit_nok"),
                    "ends_at": row.get("ends_at"),
                    "summary": intelligence.get(opportunity_id, {}).get("summary")
                    or discovery.get("suggested_action"),
                }
            )

        state["signatures"] = sorted(seen)
        state["alerts"].extend(alerts)
        self._write(state_file, state)
        payload["schema_version"] = 12
        payload["alerts_path"] = alerts_path
        payload["alert_count"] = len(alerts)
        payload["alerts"] = alerts
        self._write(snapshot_file, payload)
        return tuple(alerts)

    @staticmethod
    def _signature(*parts: Any) -> str:
        value = "|".join(map(str, parts))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": 1, "signatures": [], "alerts": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Invalid smart alerts database: {path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
            raise RuntimeError(f"Invalid smart alerts database schema: {path}")
        payload.setdefault("signatures", [])
        return payload

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
