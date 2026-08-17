"""Integrity correction for SEARCH_VALIDATION_GATE_V1.

This wrapper stays fully offline. It reuses the V1 observation/report model, then
adds two protections exposed by replaying the Aug 15-17 saved checkpoint artifacts:

1. legacy source query diagnostics without an explicit status are counted as
   successful only when they contain numeric retrieval evidence and no error;
2. one identical verified active listing repeated across several days cannot by
   itself prove a search source. At least two distinct verified active identities
   are required before a source may remain PROVEN.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from opportunity_engine.discovery.search_validation_gate import (
    CORE_MARKETS,
    SearchObservation,
    SearchValidationPolicy,
    build_search_validation_report as _build_v1_report,
    load_observations as _load_v1_observations,
)

INTEGRITY_VERSION = "SEARCH_VALIDATION_GATE_V1_1_INTEGRITY"


@dataclass(frozen=True, slots=True)
class SearchValidationIntegrityPolicy:
    min_live_runs: int = 3
    min_retrieval_success_rate: float = 0.80
    min_productive_run_rate: float = 0.50
    min_verified_active_runs: int = 2
    min_distinct_verified_active_leads: int = 2

    def base_policy(self) -> SearchValidationPolicy:
        return SearchValidationPolicy(
            min_live_runs=self.min_live_runs,
            min_retrieval_success_rate=self.min_retrieval_success_rate,
            min_productive_run_rate=self.min_productive_run_rate,
            min_verified_active_runs=self.min_verified_active_runs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_live_runs": self.min_live_runs,
            "min_retrieval_success_rate": self.min_retrieval_success_rate,
            "min_productive_run_rate": self.min_productive_run_rate,
            "min_verified_active_runs": self.min_verified_active_runs,
            "min_distinct_verified_active_leads": self.min_distinct_verified_active_leads,
        }


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _legacy_query_succeeded(row: Mapping[str, Any]) -> bool:
    status = _compact(row.get("status") or row.get("search_status")).upper()
    if status:
        return status in {"SUCCESS", "PASS"}
    if _compact(row.get("error")):
        return False
    evidence_fields = (
        "raw_hits",
        "result_count",
        "accepted_hits",
        "accepted_count",
        "rejected_hits",
        "rejected_count",
        "duplicate_count",
    )
    return any(_is_number(row.get(key)) for key in evidence_fields)


def _correct_legacy_retrieval(row: SearchObservation) -> SearchObservation:
    path = Path(row.artifact_path)
    if path.name != "search-run-report.json" or not path.exists():
        return row
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return row
    if not isinstance(payload, Mapping):
        return row
    source = payload.get("source_diagnostics")
    if not isinstance(source, Mapping):
        return row
    diagnostics = source.get("query_diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        return row
    attempted = len(diagnostics)
    succeeded = sum(
        1 for item in diagnostics
        if isinstance(item, Mapping) and _legacy_query_succeeded(item)
    )
    if attempted == row.queries_attempted and succeeded == row.queries_succeeded:
        return row
    return replace(row, queries_attempted=attempted, queries_succeeded=succeeded)


def load_integrity_observations(run_dirs: Sequence[str | Path]) -> list[SearchObservation]:
    """Load V1 observations and repair legacy query-success accounting offline."""
    return [_correct_legacy_retrieval(row) for row in _load_v1_observations(run_dirs)]


def _canonical_identity(value: object) -> str | None:
    text = _compact(value)
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlsplit(text)
        if not parsed.netloc:
            return text
        path = parsed.path.rstrip("/") or "/"
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))
    return text


def _record_identity(record: Mapping[str, Any]) -> str | None:
    for key in (
        "opportunity_id",
        "listing_id",
        "object_id",
        "source_record_id",
        "source_url",
        "url",
    ):
        value = _canonical_identity(record.get(key))
        if value:
            return value
    return None


def _verified_active_identity(record: Mapping[str, Any]) -> str | None:
    if record.get("verified") is not True:
        return None
    if _compact(record.get("listing_status")).upper() != "ACTIVE":
        return None
    return _record_identity(record)


def _source_dir_index(observations: Sequence[SearchObservation]) -> dict[Path, tuple[str, str, str]]:
    index: dict[Path, tuple[str, str, str]] = {}
    for row in observations:
        index[Path(row.artifact_path).parent.resolve()] = (
            row.run_label,
            row.market_code,
            row.source_name,
        )
    return index


def collect_verified_active_identities(
    run_dirs: Sequence[str | Path], observations: Sequence[SearchObservation]
) -> dict[tuple[str, str], dict[str, set[str]]]:
    """Return distinct verified ACTIVE identities grouped by (market, source)."""
    by_source: dict[tuple[str, str], dict[str, set[str]]] = {}
    source_dirs = _source_dir_index(observations)

    for raw_root in run_dirs:
        root = Path(raw_root)
        if not root.exists():
            continue
        for path in root.rglob("unified-opportunity-report.json"):
            source_info = source_dirs.get(path.parent.resolve())
            if source_info is None:
                continue
            run_label, market, source_name = source_info
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            records = payload.get("records") if isinstance(payload, Mapping) else None
            if not isinstance(records, list):
                continue
            key = (market, source_name)
            run_map = by_source.setdefault(key, {})
            bucket = run_map.setdefault(run_label, set())
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                identity = _verified_active_identity(record)
                if identity:
                    bucket.add(identity)

        for path in root.rglob("auksjonen-live-clothing-listings.json"):
            source_info = source_dirs.get(path.parent.resolve())
            if source_info is None:
                continue
            run_label, market, source_name = source_info
            if source_name != "Auksjonen Public API":
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            listings = payload.get("listings") if isinstance(payload, Mapping) else None
            if not isinstance(listings, list):
                continue
            key = (market, source_name)
            bucket = by_source.setdefault(key, {}).setdefault(run_label, set())
            for listing in listings:
                if not isinstance(listing, Mapping):
                    continue
                if _compact(listing.get("listing_status")).upper() != "ACTIVE":
                    continue
                if listing.get("inventory_lot_signal") is not True:
                    continue
                identity = _record_identity(listing)
                if identity:
                    bucket.add(identity)
    return by_source


def _recompute_market_and_overall(report: dict[str, Any]) -> None:
    source_by_market: dict[str, list[dict[str, Any]]] = {}
    for source in report.get("sources") or []:
        if isinstance(source, dict):
            source_by_market.setdefault(str(source.get("market_code") or ""), []).append(source)

    market_verdicts: dict[str, str] = {}
    for market_row in report.get("markets") or []:
        if not isinstance(market_row, dict):
            continue
        market = str(market_row.get("market_code") or "")
        rows = source_by_market.get(market, [])
        verdicts = [str(row.get("verdict") or "INSUFFICIENT_EVIDENCE") for row in rows]
        if any(v == "PROVEN" for v in verdicts):
            verdict = "PROVEN"
        elif rows and all(v == "NOT_PROVEN" for v in verdicts):
            verdict = "NOT_PROVEN"
        else:
            verdict = "INSUFFICIENT_EVIDENCE"
        market_row["verdict"] = verdict
        market_row["proven_source_count"] = sum(v == "PROVEN" for v in verdicts)
        market_row["not_proven_source_count"] = sum(v == "NOT_PROVEN" for v in verdicts)
        market_row["insufficient_evidence_source_count"] = sum(
            v == "INSUFFICIENT_EVIDENCE" for v in verdicts
        )
        market_verdicts[market] = verdict

    required = [str(m).upper() for m in report.get("required_markets") or CORE_MARKETS]
    required_statuses = [market_verdicts.get(m, "INSUFFICIENT_EVIDENCE") for m in required]
    if all(v == "PROVEN" for v in required_statuses):
        overall = "PROVEN"
    elif any(v == "NOT_PROVEN" for v in required_statuses):
        overall = "NOT_PROVEN"
    else:
        overall = "INSUFFICIENT_EVIDENCE"
    report["overall_verdict"] = overall
    report["progression_gate_open"] = overall == "PROVEN"
    report["next_stage_authorized"] = "MEMORY_FOLLOW_UP" if overall == "PROVEN" else None
    downstream = report.get("downstream_progression_authorized")
    if isinstance(downstream, dict):
        downstream["new_memory_follow_up_work"] = overall == "PROVEN"


def build_integrity_search_validation_report(
    run_dirs: Sequence[str | Path],
    *,
    policy: SearchValidationIntegrityPolicy | None = None,
    required_markets: Sequence[str] = CORE_MARKETS,
) -> dict[str, Any]:
    policy = policy or SearchValidationIntegrityPolicy()
    observations = load_integrity_observations(run_dirs)
    report = _build_v1_report(
        observations,
        policy=policy.base_policy(),
        required_markets=required_markets,
    )
    identity_map = collect_verified_active_identities(run_dirs, observations)

    for source in report.get("sources") or []:
        if not isinstance(source, dict):
            continue
        key = (str(source.get("market_code") or ""), str(source.get("source_name") or ""))
        run_map = identity_map.get(key, {})
        distinct = sorted({identity for ids in run_map.values() for identity in ids})
        source["verified_active_identities_by_run"] = {
            run: sorted(ids) for run, ids in sorted(run_map.items())
        }
        source["distinct_verified_active_identity_count"] = len(distinct)
        source["distinct_verified_active_identities"] = distinct

        verified_count = int(source.get("verified_active_lead_count") or 0)
        if verified_count > 0 and not distinct:
            reasons = list(source.get("reasons") or [])
            if "VERIFIED_ACTIVE_IDENTITY_ACCOUNTING_INCOMPLETE" not in reasons:
                reasons.append("VERIFIED_ACTIVE_IDENTITY_ACCOUNTING_INCOMPLETE")
            source["reasons"] = reasons
            source["verdict"] = "INSUFFICIENT_EVIDENCE"
        elif source.get("verdict") == "PROVEN" and len(distinct) < policy.min_distinct_verified_active_leads:
            reasons = list(source.get("reasons") or [])
            if "DISTINCT_VERIFIED_ACTIVE_LEADS_NOT_PROVEN" not in reasons:
                reasons.append("DISTINCT_VERIFIED_ACTIVE_LEADS_NOT_PROVEN")
            source["reasons"] = reasons
            source["verdict"] = "NOT_PROVEN"

    report["engine_version"] = INTEGRITY_VERSION
    report["policy"] = policy.to_dict()
    report["integrity_correction"] = {
        "legacy_query_statusless_diagnostics_supported": True,
        "distinct_verified_active_identity_required": True,
        "same_listing_repeated_across_days_is_not_distinct_proof": True,
        "external_api_calls": False,
        "brave_requests": 0,
    }
    _recompute_market_and_overall(report)
    return report
