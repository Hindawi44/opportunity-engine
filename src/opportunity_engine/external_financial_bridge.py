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
        # EvidenceRepository persists one ResearchEvidence object per JSON file.
        # Detect that shape before treating an absent bundle key as an empty list.
        if "opportunity_id" in payload and "evidence_type" in payload:
            return [payload]
        records = payload.get("evidence", payload.get("records"))
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def collect_external_financial_evidence(root: str | Path) -> dict[str, dict[str, Any]]:
    """Return economic-evaluation evidence grouped by opportunity.

    Current EvidenceRepository files are stored under
    ``data/evidence/<opportunity_id>/rev_<id>.json``. Older fixtures and imported evidence
    may use top-level JSON bundle files, so the recursive scan intentionally accepts every
    JSON file beneath the evidence root. Only persisted market-price observations with a
    positive explicit NOK value and a public HTTPS source are exported as verified
    comparables. Missing costs stay absent.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(root).rglob("*.json")):
        for record in _load_evidence_file(path):
            opportunity_id = str(record.get("opportunity_id") or "").strip()
            if not opportunity_id or str(record.get("evidence_type") or "") != "market_price":
                continue
            source = str(record.get("source_name") or "external_market_comparable").strip()
            url = str(record.get("source_url") or "").strip()
            if not source or not url.startswith("https://"):
                continue
            observations = record.get("observations")
            if not isinstance(observations, list):
                continue
            target = grouped.setdefault(opportunity_id, {"market_comparables": []})
            comparables = target["market_comparables"]
            for observation in observations:
                if not isinstance(observation, dict):
                    continue
                value = _number(observation.get("numeric_value"))
                currency = str(observation.get("currency") or "").upper()
                if value is None or value <= 0 or currency != "NOK":
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
    return {"schema_version": 3, "evidence": merged}
