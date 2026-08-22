"""Merge verified promoted-learning results into the existing Norway checkpoint source.

The scheduled checkpoint already owns a durable Norway cross-source source with
canonical JSON + SQLite lifecycle persistence. Rather than adding an eleventh
source and changing operator contracts, this bridge contributes independently
verified promoted-query discoveries to that existing Norway source immediately
before checkpoint consolidation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.persistence.live_unified_persistence import (
    persist_unified_report_with_artifacts,
)

SCHEMA_VERSION = "promoted-learned-checkpoint-bridge-1.0"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    value = json.loads(path.read_text(encoding="utf-8"))
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _verified_context(record: Mapping[str, Any]) -> str:
    evidence = record.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        return ""
    for raw in evidence:
        if not isinstance(raw, Mapping) or raw.get("verified") is not True:
            continue
        value = _compact(raw.get("value"))
        if value:
            return value[:4000]
    return ""


def _missing_fields(record: Mapping[str, Any]) -> list[str]:
    raw = record.get("missing_information")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            value = _compact(item.get("field_name"))
        else:
            value = _compact(item)
        if value:
            values.append(value)
    return sorted(set(values))


def _candidate_from_canonical(record: Mapping[str, Any]) -> dict[str, Any]:
    opportunity_id = _compact(record.get("opportunity_id"))
    source_url = _compact(record.get("source_url"))
    source_provider = _compact(record.get("source_provider")) or "Promoted learned Core discovery"
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    verified_context = _verified_context(record)
    learned_term = _compact(metadata.get("learned_term"))

    return {
        "opportunity_identity": opportunity_id,
        "title": _compact(record.get("title")),
        "market_code": "NO",
        "currency": "NOK",
        "source_urls": [source_url] if source_url else [],
        "source_providers": [source_provider],
        "canonical_url": source_url or None,
        "scenario": record.get("scenario") or "STOCK_LIQUIDATION",
        "company_name": record.get("company_name"),
        "inventory_type": record.get("inventory_type") or "BUSINESS_INVENTORY",
        "textile_category": record.get("category") or "BUSINESS_STOCK_LIQUIDATION",
        "listing_status": record.get("listing_status") or "UNKNOWN",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "workflow_status": record.get("workflow_status") or "REQUIRES_VERIFICATION",
        "evaluation_status": record.get("evaluation_status") or "REQUIRES_VERIFICATION",
        "identity_stable": record.get("identity_stable") is True,
        "verified": record.get("verified") is True,
        "analysis_eligible": False,
        "top5_eligible": False,
        "discovery_score": 95,
        "missing_information": _missing_fields(record),
        "verification": [
            {
                "verified": True,
                "url": source_url,
                "bounded_context": verified_context,
                "page_role": "BUSINESS_CLOSURE_STOCK_LIQUIDATION",
                "listing_status": record.get("listing_status") or "UNKNOWN",
                "event_scenario": "STOCK_LIQUIDATION",
                "verification_content_match": True,
                "historical_data_fields_trusted": False,
                "exclude_from_historical_price_analysis": True,
            }
        ] if source_url and verified_context else [],
        "evidence_signals": [
            "VERIFIED_BUSINESS_CLOSURE",
            "VERIFIED_INVENTORY_LIQUIDATION",
        ],
        "learned_term": learned_term or None,
        "promotion_status": metadata.get("promotion_status"),
        "activation_source": metadata.get("activation_source"),
        "source_page_verified": metadata.get("source_page_verified") is True,
        "closure_verified": metadata.get("closure_verified") is True,
        "inventory_liquidation_verified": metadata.get("inventory_liquidation_verified") is True,
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _dedupe_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        identity = _compact(raw.get("opportunity_identity") or raw.get("opportunity_id"))
        if not identity:
            continue
        by_id[identity] = dict(raw)
    return [by_id[key] for key in sorted(by_id)]


def _dedupe_unified_records(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        identity = _compact(raw.get("opportunity_id"))
        if not identity:
            continue
        by_id[identity] = dict(raw)
    return [by_id[key] for key in sorted(by_id)]


def merge_promoted_learning_into_norway_cross_source(
    learned_output_dir: str | Path,
    cross_source_dir: str | Path,
    *,
    config_path: str | Path = "alembic.ini",
) -> dict[str, Any]:
    """Merge verified learned records and refresh canonical SQLite persistence."""
    learned_dir = Path(learned_output_dir)
    target_dir = Path(cross_source_dir)
    learned_unified = _read_json(learned_dir / "unified-opportunity-report.json", {})
    learned_records = (
        learned_unified.get("records")
        if isinstance(learned_unified, Mapping)
        else []
    )
    learned_records = [
        dict(item)
        for item in (learned_records or [])
        if isinstance(item, Mapping)
    ]

    if not learned_records:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "VALID_ZERO",
            "merged_record_count": 0,
            "target": target_dir.as_posix(),
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    candidates_path = target_dir / "all-discovered-candidates.json"
    unified_path = target_dir / "unified-opportunity-report.json"
    report_path = target_dir / "search-run-report.json"
    if not candidates_path.exists() or not unified_path.exists() or not report_path.exists():
        raise ValueError("Norway cross-source artifacts must exist before learned merge")

    existing_candidates = _read_json(candidates_path, [])
    existing_unified = _read_json(unified_path, {})
    source_report = _read_json(report_path, {})
    if not isinstance(existing_candidates, list):
        raise ValueError("Norway cross-source candidates must be a list")
    if not isinstance(existing_unified, Mapping):
        raise ValueError("Norway cross-source unified report must be an object")
    if not isinstance(source_report, Mapping):
        raise ValueError("Norway cross-source search report must be an object")

    learned_candidates = [_candidate_from_canonical(item) for item in learned_records]
    merged_candidates = _dedupe_candidates(
        [
            *(item for item in existing_candidates if isinstance(item, Mapping)),
            *learned_candidates,
        ]
    )
    merged_unified_records = _dedupe_unified_records(
        [
            *(
                item
                for item in (existing_unified.get("records") or [])
                if isinstance(item, Mapping)
            ),
            *learned_records,
        ]
    )

    updated_unified = dict(existing_unified)
    updated_unified["record_count"] = len(merged_unified_records)
    updated_unified["records"] = merged_unified_records
    updated_unified["conversion_error_count"] = 0
    updated_unified["conversion_errors"] = []
    learned_generated_at = _compact(learned_unified.get("generated_at"))
    if learned_generated_at:
        updated_unified["generated_at"] = learned_generated_at

    updated_report = dict(source_report)
    updated_report["record_count"] = len(merged_candidates)
    updated_report["promoted_learned_core_merged_count"] = len(learned_candidates)
    updated_report["promoted_learned_core_artifact"] = (
        learned_dir / "search-run-report.json"
    ).as_posix()

    _write_json(candidates_path, merged_candidates)
    _write_json(unified_path, updated_unified)
    _write_json(report_path, updated_report)

    persist_unified_report_with_artifacts(
        unified_path,
        target_dir,
        database_url=f"sqlite:///{target_dir / 'opportunity_engine.db'}",
        config_path=config_path,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "merged_record_count": len(learned_candidates),
        "combined_candidate_count": len(merged_candidates),
        "combined_unified_record_count": len(merged_unified_records),
        "target": target_dir.as_posix(),
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
