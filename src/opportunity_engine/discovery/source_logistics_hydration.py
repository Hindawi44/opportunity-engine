"""Hydrate source-backed logistics facts for the already-selected central case.

The unified river intentionally keeps a compact projection. Some collectors,
however, know exact pickup/shipment facts that are present in their raw daily
candidate artifact. This module copies only those already-observed fields into
the selected unified intelligence item immediately before official route/freight
calculation.

No source page is fetched here, no case is selected or promoted, and no missing
fact is estimated.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

OUTPUT_FILENAME = "selected-source-logistics-hydration.json"
SCHEMA_VERSION = "selected-source-logistics-hydration-1.0"

_LOGISTICS_KEYS = (
    "source_postal_code",
    "source_city",
    "weight_kg",
    "gross_weight_kg",
    "pallet_count",
    "number_of_pallets",
    "numberOfPallets",
    "length_cm",
    "width_cm",
    "height_cm",
    "bring_volume",
    "source_item_url",
    "exact_item_page_verified",
    "shipping_details_source",
    "source_start_or_minimum_price_eur",
    "source_displayed_bid_eur",
    "buyer_premium_percent",
    "vat_percent",
)
_COMMERCIAL_KINDS = {"CANONICAL_OPPORTUNITY", "B2B_STOCK_OFFER", "AUCTION_LOT"}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _find_case(cases_report: Mapping[str, Any], case_id: str) -> dict[str, Any] | None:
    for case in _rows(cases_report.get("cases")):
        if _compact(case.get("case_id")) == case_id:
            return case
    return None


def _selected_item(
    brief: Mapping[str, Any],
    items_report: Mapping[str, Any],
    cases_report: Mapping[str, Any],
) -> tuple[int, dict[str, Any]] | None:
    opportunity = brief.get("top_actionable_opportunity")
    if not isinstance(opportunity, Mapping):
        return None
    case_id = _compact(opportunity.get("case_id"))
    if not case_id:
        return None
    case = _find_case(cases_report, case_id)
    if not case:
        return None
    item_ids = {_compact(value) for value in case.get("item_ids") or [] if _compact(value)}
    for index, item in enumerate(_rows(items_report.get("items"))):
        if _compact(item.get("intelligence_id")) not in item_ids:
            continue
        if _compact(item.get("record_kind")).upper() not in _COMMERCIAL_KINDS:
            continue
        return index, item
    return None


def _opportunity_identity(item: Mapping[str, Any]) -> str | None:
    details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
    direct = _compact(details.get("opportunity_identity"))
    if direct:
        return direct
    metadata = details.get("metadata") if isinstance(details.get("metadata"), Mapping) else {}
    nested = _compact(metadata.get("opportunity_identity"))
    if nested:
        return nested
    stable = _compact(item.get("stable_identity"))
    if stable.startswith("opportunity:"):
        return stable.split("opportunity:", 1)[1]
    return None


def _candidate_files(output_dir: Path) -> list[Path]:
    input_root = output_dir.parent / "multi-market-inputs"
    if not input_root.exists():
        return []
    return sorted(input_root.glob("*/all-discovered-candidates.json"))


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, Mapping)]


def _matching_candidate(
    output_dir: Path,
    *,
    identity: str | None,
    source_url: str | None,
) -> tuple[Path, dict[str, Any]] | None:
    for path in _candidate_files(output_dir):
        for candidate in _load_candidates(path):
            if identity and _compact(candidate.get("opportunity_identity")) == identity:
                return path, candidate
            urls = {_compact(value) for value in candidate.get("source_urls") or [] if _compact(value)}
            if source_url and source_url in urls:
                return path, candidate
    return None


def hydrate_selected_source_logistics(
    output_dir: str | Path,
    central_brief: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy exact source logistics fields into the selected unified item artifact."""
    root = Path(output_dir)
    items_path = root / "unified-intelligence-items.json"
    cases_path = root / "unified-market-cases.json"
    items_report = _read_json(items_path)
    cases_report = _read_json(cases_path)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "NO_SELECTED_COMMERCIAL_ITEM",
        "selected_intelligence_id": None,
        "opportunity_identity": None,
        "source_candidate_artifact": None,
        "hydrated_fields": [],
        "source_page_fetch_performed": False,
        "estimated_values_added": False,
    }

    selected = _selected_item(central_brief, items_report, cases_report)
    if selected is None:
        _write_json(root / OUTPUT_FILENAME, report)
        return report
    index, item = selected
    identity = _opportunity_identity(item)
    report["selected_intelligence_id"] = item.get("intelligence_id")
    report["opportunity_identity"] = identity
    source_url = _compact(item.get("source_url")) or None
    match = _matching_candidate(root, identity=identity, source_url=source_url)
    if match is None:
        report["status"] = "SOURCE_CANDIDATE_NOT_FOUND"
        _write_json(root / OUTPUT_FILENAME, report)
        return report

    source_path, candidate = match
    details = dict(item.get("details") or {}) if isinstance(item.get("details"), Mapping) else {}
    metadata = dict(details.get("metadata") or {}) if isinstance(details.get("metadata"), Mapping) else {}
    hydrated: list[str] = []
    for key in _LOGISTICS_KEYS:
        value = candidate.get(key)
        if value in (None, "", [], {}):
            continue
        details[key] = value
        metadata[key] = value
        hydrated.append(key)
    if candidate.get("location") not in (None, ""):
        item["location"] = candidate.get("location")
        details["source_location"] = candidate.get("location")
        hydrated.append("location")
    if candidate.get("quantity") not in (None, ""):
        details["quantity"] = candidate.get("quantity")
        hydrated.append("quantity")

    details["metadata"] = metadata
    item["details"] = details
    items = _rows(items_report.get("items"))
    if index >= len(items):
        report["status"] = "ITEM_INDEX_MISMATCH"
        _write_json(root / OUTPUT_FILENAME, report)
        return report
    items[index] = item
    items_report["items"] = items
    _write_json(items_path, items_report)

    report["source_candidate_artifact"] = source_path.relative_to(root.parent).as_posix()
    report["hydrated_fields"] = sorted(set(hydrated))
    report["status"] = "HYDRATED" if hydrated else "NO_SOURCE_LOGISTICS_FIELDS"
    _write_json(root / OUTPUT_FILENAME, report)
    return report
