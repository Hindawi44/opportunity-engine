"""Bridge accepted external research evidence into conservative financial scoring inputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _load_evidence_file(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if "opportunity_id" in payload and "evidence_type" in payload:
            return [payload]
        records = payload.get("evidence", payload.get("records"))
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def _valid_observations(record: dict[str, Any]) -> list[tuple[float, dict[str, Any]]]:
    observations = record.get("observations")
    if not isinstance(observations, list):
        return []
    valid: list[tuple[float, dict[str, Any]]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        value = _number(observation.get("numeric_value"))
        currency = str(observation.get("currency") or "").upper()
        if value is not None and currency == "NOK":
            valid.append((value, observation))
    return valid


def collect_external_financial_evidence(root: str | Path) -> dict[str, dict[str, Any]]:
    """Export only persisted, explicit and verified market/cost evidence.

    V2.9 adds auction-price, fee, VAT, transport, dismantling and storage fields. The
    bridge exposes them to the evidence payload but does not alter the Financial Score
    formula. Missing or conflicting values remain absent.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(root).rglob("*.json")):
        for record in _load_evidence_file(path):
            opportunity_id = str(record.get("opportunity_id") or "").strip()
            evidence_type = str(record.get("evidence_type") or "")
            source = str(record.get("source_name") or "").strip()
            url = str(record.get("source_url") or "").strip()
            if not opportunity_id or not source or not url.startswith("https://"):
                continue

            observations = _valid_observations(record)
            if evidence_type == "market_price":
                target = grouped.setdefault(opportunity_id, {"market_comparables": []})
                comparables = target.setdefault("market_comparables", [])
                for value, observation in observations:
                    if value <= 0:
                        continue
                    candidate = {
                        "verified": True,
                        "source": source,
                        "url": url,
                        "price_nok": value,
                        "evidence_id": record.get("evidence_id"),
                        "observed_at": observation.get("observed_at"),
                    }
                    if not any(
                        item.get("url") == url and item.get("price_nok") == value
                        for item in comparables
                        if isinstance(item, dict)
                    ):
                        comparables.append(candidate)
                continue

            if evidence_type not in {"cost", "logistics"}:
                continue
            metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
            field = str(metadata.get("financial_field") or "").strip()
            component = str(metadata.get("cost_component") or "").strip()
            allowed_fields = {
                "auction_price_nok",
                "auction_fee_nok",
                "vat_nok",
                "transport_cost_nok",
                "dismantling_cost_nok",
                "storage_cost_nok",
            }
            if field not in allowed_fields or not component or len(observations) != 1:
                continue
            value, observation = observations[0]
            if value == 0 and metadata.get("zero_cost_confirmed") is not True:
                continue
            target = grouped.setdefault(opportunity_id, {"market_comparables": []})
            existing = target.get(field)
            if existing is None:
                target[field] = value
                target.setdefault("cost_evidence", {})[field] = {
                    "verified": True,
                    "component": component,
                    "source": source,
                    "url": url,
                    "evidence_id": record.get("evidence_id"),
                    "observed_at": observation.get("observed_at"),
                }
            elif existing != value:
                target.pop(field, None)
                target.setdefault("cost_conflicts", []).append(field)
    return grouped


def merge_evidence(existing: object, external: dict[str, dict[str, Any]]) -> dict[str, Any]:
    records = existing.get("evidence", existing) if isinstance(existing, dict) else {}
    merged = {key: dict(value) for key, value in records.items() if isinstance(value, dict)} if isinstance(records, dict) else {}
    for opportunity_id, supplied in external.items():
        target = merged.setdefault(opportunity_id, {})
        old = target.get("market_comparables")
        combined = [item for item in old if isinstance(item, dict)] if isinstance(old, list) else []
        for item in supplied.get("market_comparables", []):
            if not any(
                existing_item.get("url") == item.get("url")
                and existing_item.get("price_nok") == item.get("price_nok")
                for existing_item in combined
            ):
                combined.append(item)
        target["market_comparables"] = combined
        for field in (
            "auction_price_nok",
            "auction_fee_nok",
            "vat_nok",
            "transport_cost_nok",
            "dismantling_cost_nok",
            "storage_cost_nok",
        ):
            if field in supplied:
                target[field] = supplied[field]
        if isinstance(supplied.get("cost_evidence"), dict):
            target["cost_evidence"] = dict(supplied["cost_evidence"])
        if isinstance(supplied.get("cost_conflicts"), list):
            target["cost_conflicts"] = list(supplied["cost_conflicts"])
    return {"schema_version": 4, "evidence": merged}
