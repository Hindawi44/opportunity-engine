"""Build operator-facing reports from persisted historical market evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from .models import UnifiedOpportunityModel
from .repository import PersistenceError
from .unified_repository import UnifiedOpportunityRepository


REPORT_SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "historical-market-evidence-report.json"
SUMMARY_FILENAME = "historical-market-evidence-summary.txt"


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _metadata(model: UnifiedOpportunityModel) -> Mapping[str, Any]:
    record = model.record_json
    if not isinstance(record, Mapping):
        return {}
    metadata = record.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _report_item(
    model: UnifiedOpportunityModel,
    *,
    price_analysis_eligible: bool,
) -> dict[str, Any]:
    metadata = _metadata(model)
    return {
        "opportunity_id": model.opportunity_id,
        "title": model.title,
        "source_provider": model.source_provider,
        "source_url": model.source_url,
        "market_code": model.market_code,
        "listing_status": model.listing_status,
        "evaluation_status": model.evaluation_status,
        "workflow_status": model.workflow_status,
        "scenario": model.scenario,
        "location": model.location,
        "inventory_type": model.inventory_type,
        "quantity": model.quantity,
        "currency": model.currency,
        "bid_price": model.bid_price,
        "price_analysis_eligible": price_analysis_eligible,
        "source_object_id": metadata.get("source_object_id"),
        "auction_occurrence_id": metadata.get("auction_occurrence_id"),
        "verification_content_match": metadata.get("verification_content_match"),
        "historical_market_evidence_eligible": metadata.get(
            "historical_market_evidence_eligible"
        ),
        "historical_data_fields_trusted": metadata.get(
            "historical_data_fields_trusted"
        ),
        "bid_price_trusted": metadata.get("bid_price_trusted"),
        "reference_value_trusted": metadata.get("reference_value_trusted"),
        "exclude_from_historical_price_analysis": metadata.get(
            "exclude_from_historical_price_analysis"
        ),
        "historical_price_analysis_exclusion_reason": metadata.get(
            "historical_price_analysis_exclusion_reason"
        ),
        "raw_bid_price_amount": metadata.get("bid_price_sek"),
        "raw_bid_price_currency": metadata.get("bid_price_currency"),
        "reference_value_amount": metadata.get("reference_value_sek"),
        "reference_value_kind": metadata.get("reference_value_kind"),
        "first_seen_at": _utc_iso(model.first_seen_at),
        "last_seen_at": _utc_iso(model.last_seen_at),
    }


def build_historical_market_evidence_report(
    repository: UnifiedOpportunityRepository,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Return trusted and manual-review historical records in separate sections."""
    if not isinstance(repository, UnifiedOpportunityRepository):
        raise PersistenceError("repository must be UnifiedOpportunityRepository")

    trusted = repository.list_trusted_historical_market_evidence()
    trusted_prices = repository.list_trusted_historical_price_records()
    manual_review = repository.list_historical_evidence_manual_review()

    trusted_price_ids = {model.opportunity_id for model in trusted_prices}
    trusted_ids = {model.opportunity_id for model in trusted}
    manual_ids = {model.opportunity_id for model in manual_review}
    overlap = trusted_ids.intersection(manual_ids)
    if overlap:
        joined = ", ".join(sorted(overlap))
        raise PersistenceError(
            f"historical report sections overlap for opportunity IDs: {joined}"
        )

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PersistenceError("generated_at must be timezone-aware")

    trusted_items = [
        _report_item(
            model,
            price_analysis_eligible=model.opportunity_id in trusted_price_ids,
        )
        for model in trusted
    ]
    manual_items = [
        _report_item(model, price_analysis_eligible=False)
        for model in manual_review
    ]

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": _utc_iso(timestamp),
        "summary": {
            "trusted_historical_evidence_count": len(trusted_items),
            "trusted_historical_price_record_count": len(trusted_prices),
            "manual_review_count": len(manual_items),
            "total_reported_record_count": len(trusted_items) + len(manual_items),
        },
        "trusted_historical_market_evidence": trusted_items,
        "manual_review": manual_items,
        "scope": {
            "source": "SQLite unified_opportunities",
            "includes_current_opportunities": False,
            "includes_top5": False,
            "performs_financial_analysis": False,
            "performs_fx_conversion": False,
            "performs_tax_or_logistics_calculation": False,
        },
    }


def serialize_historical_market_evidence_report(report: Mapping[str, Any]) -> str:
    """Serialize the report in stable, human-readable JSON."""
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def render_historical_market_evidence_summary(report: Mapping[str, Any]) -> str:
    """Render a compact text summary for operators."""
    summary = report.get("summary")
    trusted = report.get("trusted_historical_market_evidence")
    manual = report.get("manual_review")
    if not isinstance(summary, Mapping):
        raise PersistenceError("historical report summary must be an object")
    if not isinstance(trusted, list) or not isinstance(manual, list):
        raise PersistenceError("historical report sections must be lists")

    lines = [
        "Historical Market Evidence Report",
        f"Generated at: {report.get('generated_at')}",
        "",
        f"Trusted historical evidence: {summary.get('trusted_historical_evidence_count')}",
        f"Trusted price records: {summary.get('trusted_historical_price_record_count')}",
        f"Manual review: {summary.get('manual_review_count')}",
        "",
        "Trusted historical market evidence:",
    ]
    if not trusted:
        lines.append("- None")
    for item in trusted:
        if not isinstance(item, Mapping):
            raise PersistenceError("trusted historical report item must be an object")
        bid = item.get("bid_price")
        currency = item.get("currency") or ""
        price_text = f"{bid:g} {currency}" if isinstance(bid, (int, float)) else "no trusted bid"
        quantity = item.get("quantity")
        quantity_text = f"qty {quantity}" if quantity is not None else "quantity unknown"
        lines.append(
            f"- {item.get('title')} | {price_text} | {quantity_text} | "
            f"{item.get('opportunity_id')}"
        )

    lines.extend(["", "Manual review:"])
    if not manual:
        lines.append("- None")
    for item in manual:
        if not isinstance(item, Mapping):
            raise PersistenceError("manual-review report item must be an object")
        raw_bid = item.get("raw_bid_price_amount")
        raw_currency = item.get("raw_bid_price_currency") or ""
        raw_text = (
            f"raw {raw_bid:g} {raw_currency}"
            if isinstance(raw_bid, (int, float))
            else "no raw bid"
        )
        lines.append(
            f"- {item.get('title')} | {raw_text} | excluded: "
            f"{item.get('historical_price_analysis_exclusion_reason')} | "
            f"{item.get('opportunity_id')}"
        )

    return "\n".join(lines) + "\n"


def write_historical_market_evidence_report(
    repository: UnifiedOpportunityRepository,
    output_dir: str | Path,
    *,
    generated_at: datetime | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    """Build and write JSON plus compact text reports."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report = build_historical_market_evidence_report(
        repository,
        generated_at=generated_at,
    )
    report_path = destination / REPORT_FILENAME
    summary_path = destination / SUMMARY_FILENAME
    report_path.write_text(
        serialize_historical_market_evidence_report(report) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        render_historical_market_evidence_summary(report),
        encoding="utf-8",
    )
    return report, report_path, summary_path
