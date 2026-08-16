"""Read-only consolidation for Norway, Sweden, and Germany discovery artifacts.

The checkpoint does not collect, contact, bid, buy, reserve, pay, convert prices,
or alter any source runtime state. It only reconciles existing JSON artifacts into
one operator-facing report.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


MARKET_CURRENCIES = {"NO": "NOK", "SE": "SEK", "DE": "EUR"}
SUCCESS_STATES = {"PASS", "SUCCESS", "OK", "COMPLETED"}
ENDED_STATES = {"ENDED", "CLOSED", "EXPIRED", "SOLD", "UNAVAILABLE"}
HISTORICAL_LIFECYCLE_STATES = {
    "HISTORICAL_MARKET_EVIDENCE",
    "HISTORICAL_EVIDENCE",
    "HISTORICAL_ONLY",
}
AUKSJONEN_ANALYSIS_BLOCKERS = (
    "verified exact item-page evidence",
    "verified quantity and condition",
    "documented final payable price including auction fees and VAT",
    "domestic pickup or delivery logistics basis",
    "documented resale-market evidence",
)
STATUS_RANK = {
    "ACTIVE": 5,
    "UPCOMING": 4,
    "UNRESOLVED": 3,
    "HISTORICAL": 2,
    "ENDED": 1,
}


class CheckpointIntegrityError(ValueError):
    """Raised when source artifacts violate the checkpoint contract."""


def _read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointIntegrityError(f"Invalid JSON artifact: {path}: {exc}") from exc


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _first_text(record: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = _compact(record.get(key))
        if value:
            return value
    return None


def opportunity_identity(record: Mapping[str, Any], source_name: str) -> str:
    identity = _first_text(
        record,
        (
            "opportunity_identity",
            "opportunity_id",
            "identity",
            "canonical_url",
            "url",
        ),
    )
    if identity:
        return identity
    object_id = _first_text(record, ("object_id", "auction_id", "listing_id", "id"))
    if object_id:
        return f"{source_name.lower().replace(' ', '-')}:object:{object_id}"
    title = _first_text(record, ("title", "name")) or "untitled"
    return f"{source_name.lower().replace(' ', '-')}:fallback:{title.lower()}"


def _record_status(record: Mapping[str, Any]) -> str:
    listing_status = _compact(record.get("listing_status") or record.get("status")).upper()
    lifecycle_states = {
        _compact(record.get("workflow_status")).upper(),
        _compact(record.get("opportunity_state")).upper(),
        _compact(record.get("evaluation_status")).upper(),
    }
    if lifecycle_states & HISTORICAL_LIFECYCLE_STATES or listing_status == "HISTORICAL":
        return "HISTORICAL"
    if listing_status == "ACTIVE":
        return "ACTIVE"
    if listing_status == "UPCOMING":
        return "UPCOMING"
    if listing_status in ENDED_STATES:
        return "ENDED"
    return "UNRESOLVED"


def _score(record: Mapping[str, Any]) -> float:
    for key in ("discovery_score", "opportunity_score", "score"):
        try:
            return float(record.get(key))
        except (TypeError, ValueError):
            continue
    return 0.0


def _missing_evidence(record: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("missing_information", "missing_evidence"):
        raw = record.get(key)
        if isinstance(raw, str):
            text = _compact(raw)
            if text:
                values.append(text)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            for item in raw:
                if isinstance(item, Mapping):
                    text = _first_text(
                        item,
                        ("field_name", "reason", "required_for"),
                    )
                else:
                    text = _compact(item)
                if text:
                    values.append(text)
    return values


def _analysis_missing_evidence(
    record: Mapping[str, Any],
    *,
    source_name: str,
    top5_eligible: bool,
    analysis_eligible: bool,
) -> list[str]:
    values = _missing_evidence(record)
    if (
        source_name.casefold().startswith("auksjonen")
        and top5_eligible
        and not analysis_eligible
    ):
        values.extend(AUKSJONEN_ANALYSIS_BLOCKERS)
    return sorted(set(values))


def _source_files(spec: Mapping[str, Any], root: Path) -> dict[str, Path]:
    artifact_dir = root / _compact(spec.get("artifact_dir"))
    return {
        "artifact_dir": artifact_dir,
        "execution": artifact_dir / _compact(
            spec.get("execution_status_file") or "execution-status.json"
        ),
        "report": artifact_dir / _compact(
            spec.get("report_file") or "search-run-report.json"
        ),
        "candidates": artifact_dir / _compact(
            spec.get("candidates_file") or "all-discovered-candidates.json"
        ),
        "top5": artifact_dir / _compact(
            spec.get("top5_file") or "discovery-top5.json"
        ),
        "unified": artifact_dir / _compact(
            spec.get("unified_report_file") or "unified-opportunity-report.json"
        ),
        "persistence": artifact_dir / _compact(
            spec.get("persistence_summary_file") or "unified-persistence-summary.json"
        ),
    }


def _load_source(spec: Mapping[str, Any], root: Path) -> dict[str, Any]:
    market_code = _compact(spec.get("market_code")).upper()
    source_name = _compact(spec.get("source_name") or spec.get("source"))
    currency = _compact(spec.get("currency")).upper()
    if market_code not in MARKET_CURRENCIES:
        raise CheckpointIntegrityError(f"Unsupported market in manifest: {market_code!r}")
    if currency != MARKET_CURRENCIES[market_code]:
        raise CheckpointIntegrityError(
            f"Currency mismatch for {market_code}: {currency!r} != {MARKET_CURRENCIES[market_code]!r}"
        )
    if not source_name:
        raise CheckpointIntegrityError("Every source manifest entry needs source_name")

    if spec.get("blocked") is True:
        return {
            "market_code": market_code,
            "source_name": source_name,
            "currency": currency,
            "execution_status": "BLOCKED",
            "records": [],
            "top5_records": [],
            "report": {},
            "unified": None,
            "persistence": None,
            "artifact_references": [],
            "failure": None,
            "activation_blocker": _compact(spec.get("activation_blocker")) or None,
        }

    files = _source_files(spec, root)
    execution = _read_json(files["execution"], default={}) or {}
    report = _read_json(files["report"], default=None)
    candidates = _read_json(files["candidates"], default=[])
    top5 = _read_json(files["top5"], default=[])
    unified = _read_json(files["unified"], default=None)
    persistence = _read_json(files["persistence"], default=None)

    if spec.get("report_kind") == "AUKSJONEN_LIVE":
        report = report if isinstance(report, Mapping) else None
        raw_records = _as_list((report or {}).get("listings"))
        raw_records = [
            item for item in raw_records if item.get("inventory_lot_signal") is True
        ]
        # Source-native candidates are written after exact item-page verification
        # and therefore own eligibility/evidence truth. The raw public listing
        # report remains a compatibility fallback for older artifacts/tests only.
        verified_candidates = _as_list(candidates)
        records = verified_candidates if verified_candidates else raw_records
        top5_records = _as_list(top5)
        source_success = bool((report or {}).get("scan_complete")) and not (
            (report or {}).get("errors") or []
        )
    else:
        records = _as_list(candidates)
        top5_records = _as_list(top5)
        status = _compact((report or {}).get("status")).upper()
        source_success = status in SUCCESS_STATES

    exit_code = execution.get("exit_code")
    if exit_code not in (None, 0):
        source_success = False

    failure: str | None = None
    if not source_success:
        failure = _compact(execution.get("error")) or (
            "source report missing or source execution did not complete successfully"
        )
        execution_status = "FAILURE"
    elif records:
        execution_status = "SUCCESS"
    else:
        execution_status = "VALID_ZERO_RESULT"

    conversion_performed = bool((report or {}).get("currency_conversion_performed"))
    if market_code in {"SE", "DE"} and not conversion_performed:
        for record in records:
            if record.get("price_nok") is not None or record.get("bid_price_nok") is not None:
                raise CheckpointIntegrityError(
                    f"{source_name} leaked {currency} source values into NOK fields"
                )

    if isinstance(unified, Mapping):
        unified_count = int(unified.get("record_count") or 0)
        if unified_count != len(records):
            raise CheckpointIntegrityError(
                f"{source_name} unified record count {unified_count} != candidates {len(records)}"
            )
        if int(unified.get("conversion_error_count") or 0) != 0:
            raise CheckpointIntegrityError(f"{source_name} has unified conversion errors")

    if isinstance(persistence, Mapping):
        persisted_count = int(persistence.get("persisted_record_count") or 0)
        expected_count = int((unified or {}).get("record_count") or len(records))
        if persistence.get("status") != "SUCCESS":
            raise CheckpointIntegrityError(f"{source_name} persistence did not succeed")
        if persisted_count != expected_count:
            raise CheckpointIntegrityError(
                f"{source_name} persisted count {persisted_count} != unified count {expected_count}"
            )

    refs = [
        str(path.relative_to(root))
        for key, path in files.items()
        if key != "artifact_dir" and path.exists()
    ]
    return {
        "market_code": market_code,
        "source_name": source_name,
        "currency": currency,
        "execution_status": execution_status,
        "records": records,
        "top5_records": top5_records,
        "report": dict(report or {}),
        "unified": dict(unified) if isinstance(unified, Mapping) else None,
        "persistence": dict(persistence) if isinstance(persistence, Mapping) else None,
        "artifact_references": refs,
        "failure": failure,
        "activation_blocker": _compact(spec.get("activation_blocker")) or None,
    }


def _matrix_blockers(matrix: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for market in matrix.get("markets") or []:
        if not isinstance(market, Mapping):
            continue
        market_code = _compact(market.get("market_code")).upper()
        if market_code not in MARKET_CURRENCIES:
            continue
        for source in market.get("sources") or []:
            if not isinstance(source, Mapping):
                continue
            runtime = _compact(
                source.get("runtime_activation_status") or source.get("audit_status")
            ).upper()
            blocker = _compact(
                source.get("activation_requirement") or source.get("activation_blocker")
            )
            if runtime == "BLOCKED_AUTH" or blocker:
                blockers.append(
                    {
                        "market_code": market_code,
                        "source_name": _compact(source.get("source")),
                        "runtime_status": runtime or "PLANNED",
                        "blocker": blocker or "authorized access is required",
                    }
                )
    return blockers


def _merge_records(source_runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in source_runs:
        source_name = str(source["source_name"])
        market_code = str(source["market_code"])
        currency = str(source["currency"])
        top5_ids = {
            opportunity_identity(item, source_name)
            for item in source.get("top5_records") or []
        }
        for raw in source.get("records") or []:
            record = deepcopy(dict(raw))
            identity = opportunity_identity(record, source_name)
            status = _record_status(record)
            raw_top5_eligible = bool(record.get("top5_eligible")) or identity in top5_ids
            raw_analysis_eligible = bool(record.get("analysis_eligible"))
            top5_eligible = raw_top5_eligible and status == "ACTIVE"
            analysis_eligible = raw_analysis_eligible and status == "ACTIVE"
            normalized = {
                "opportunity_identity": identity,
                "title": _first_text(record, ("title", "name")),
                "market_code": market_code,
                "currency": currency,
                "source_names": [source_name],
                "listing_status": status,
                "top5_eligible": top5_eligible,
                "analysis_eligible": analysis_eligible,
                "discovery_score": _score(record),
                "missing_evidence": _analysis_missing_evidence(
                    record,
                    source_name=source_name,
                    top5_eligible=top5_eligible,
                    analysis_eligible=analysis_eligible,
                ),
                "source_urls": list(record.get("source_urls") or []),
                "canonical_url": _first_text(record, ("canonical_url", "url")),
            }
            existing = merged.get(identity)
            if existing is None:
                merged[identity] = normalized
                continue
            existing["source_names"] = sorted(
                set(existing["source_names"]) | {source_name}
            )
            existing["top5_eligible"] = bool(
                existing["top5_eligible"] or normalized["top5_eligible"]
            )
            existing["analysis_eligible"] = bool(
                existing["analysis_eligible"] or normalized["analysis_eligible"]
            )
            existing["discovery_score"] = max(
                float(existing["discovery_score"]), normalized["discovery_score"]
            )
            existing["missing_evidence"] = sorted(
                set(existing["missing_evidence"]) | set(normalized["missing_evidence"])
            )
            if STATUS_RANK[normalized["listing_status"]] > STATUS_RANK[
                existing["listing_status"]
            ]:
                existing["listing_status"] = normalized["listing_status"]
                existing["title"] = normalized["title"] or existing["title"]
                existing["canonical_url"] = (
                    normalized["canonical_url"] or existing["canonical_url"]
                )
    return sorted(
        merged.values(),
        key=lambda item: (
            not item["top5_eligible"],
            -float(item["discovery_score"]),
            item["opportunity_identity"],
        ),
    )


def _next_action(
    records: Sequence[Mapping[str, Any]],
    source_runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    eligible = [
        item
        for item in records
        if item.get("top5_eligible") is True and item.get("listing_status") == "ACTIVE"
    ]
    if eligible:
        target = eligible[0]
        return {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": target["opportunity_identity"],
            "reason": "A verified active Top 5 eligible opportunity is available for human review.",
        }
    failures = [
        item for item in source_runs if item.get("execution_status") == "FAILURE"
    ]
    if failures:
        source = failures[0]
        return {
            "action": "REVIEW_ONE_SOURCE_FAILURE",
            "market_code": source["market_code"],
            "source_name": source["source_name"],
            "reason": source.get("failure") or "The source run failed.",
        }
    unresolved = [
        item for item in records if item.get("listing_status") == "UNRESOLVED"
    ]
    if unresolved:
        target = unresolved[0]
        return {
            "action": "VERIFY_ONE_UNRESOLVED_RECORD",
            "opportunity_identity": target["opportunity_identity"],
            "reason": "The record exists but still lacks enough verified evidence.",
        }
    return {
        "action": "NO_IMMEDIATE_ACTION",
        "reason": "No verified active Top 5 opportunity or source failure requires manual action today.",
    }


def build_multi_market_checkpoint(
    manifest: Mapping[str, Any],
    market_matrix: Mapping[str, Any],
    *,
    root: str | Path = ".",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build one deterministic read-only checkpoint from existing source artifacts."""
    root_path = Path(root)
    source_specs = manifest.get("sources")
    if not isinstance(source_specs, list) or not source_specs:
        raise CheckpointIntegrityError("Manifest must contain at least one source")

    source_runs = [_load_source(spec, root_path) for spec in source_specs]
    covered_markets = {item["market_code"] for item in source_runs}
    missing_markets = sorted(set(MARKET_CURRENCIES) - covered_markets)
    if missing_markets:
        raise CheckpointIntegrityError(
            f"Checkpoint manifest does not cover completed markets: {missing_markets}"
        )

    records = _merge_records(source_runs)
    status_counts = Counter(item["listing_status"] for item in records)
    execution_counts = Counter(item["execution_status"] for item in source_runs)
    missing_evidence = sorted(
        {
            evidence
            for item in records
            for evidence in item.get("missing_evidence") or []
            if evidence
        }
    )
    blockers = _matrix_blockers(market_matrix)
    action = _next_action(records, source_runs)

    markets = []
    for market_code in ("NO", "SE", "DE"):
        market_sources = [
            item for item in source_runs if item["market_code"] == market_code
        ]
        market_records = [
            item for item in records if item["market_code"] == market_code
        ]
        markets.append(
            {
                "market_code": market_code,
                "currency": MARKET_CURRENCIES[market_code],
                "source_count": len(market_sources),
                "source_execution_counts": dict(
                    sorted(Counter(item["execution_status"] for item in market_sources).items())
                ),
                "deduplicated_record_count": len(market_records),
                "active_count": sum(
                    item["listing_status"] == "ACTIVE" for item in market_records
                ),
                "top5_eligible_count": sum(
                    item["top5_eligible"] is True for item in market_records
                ),
            }
        )

    return {
        "schema_version": "multi-market-operator-checkpoint-1.0",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "domain": "CLOTHING_INVENTORY",
        "execution_mode": "MANUAL_READ_ONLY",
        "market_coverage": ["NO", "SE", "DE"],
        "markets": markets,
        "source_execution_counts": dict(sorted(execution_counts.items())),
        "sources": [
            {
                key: item.get(key)
                for key in (
                    "market_code",
                    "source_name",
                    "currency",
                    "execution_status",
                    "failure",
                    "activation_blocker",
                    "artifact_references",
                )
            }
            | {
                "record_count": len(item.get("records") or []),
                "top5_input_count": len(item.get("top5_records") or []),
                "persistence_status": (
                    (item.get("persistence") or {}).get("status")
                    if item.get("persistence") is not None
                    else "NOT_ENABLED"
                ),
            }
            for item in source_runs
        ],
        "deduplicated_record_count": len(records),
        "status_counts": {
            key: int(status_counts.get(key, 0))
            for key in ("ACTIVE", "UPCOMING", "HISTORICAL", "ENDED", "UNRESOLVED")
        },
        "top5_eligible_count": sum(item["top5_eligible"] is True for item in records),
        "analysis_eligible_count": sum(
            item["analysis_eligible"] is True for item in records
        ),
        "deduplicated_opportunities": records,
        "missing_evidence": missing_evidence,
        "activation_blockers": blockers,
        "next_human_action": action,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def render_phone_summary(report: Mapping[str, Any]) -> str:
    """Render a compact Arabic phone summary with exactly one next action."""
    source_counts = report.get("source_execution_counts") or {}
    status_counts = report.get("status_counts") or {}
    action = report.get("next_human_action") or {}
    lines = [
        "ملخص الأسواق الثلاثة — مخزون الملابس",
        f"الوقت: {report.get('generated_at')}",
        "التغطية: النرويج NO | السويد SE | ألمانيا DE",
        (
            "المصادر: "
            f"نجاح {source_counts.get('SUCCESS', 0)} | "
            f"صفر صحيح {source_counts.get('VALID_ZERO_RESULT', 0)} | "
            f"فشل {source_counts.get('FAILURE', 0)} | "
            f"محجوب {source_counts.get('BLOCKED', 0)}"
        ),
        (
            "السجلات: "
            f"نشط {status_counts.get('ACTIVE', 0)} | "
            f"قادم {status_counts.get('UPCOMING', 0)} | "
            f"تاريخي {status_counts.get('HISTORICAL', 0)} | "
            f"منتهٍ {status_counts.get('ENDED', 0)} | "
            f"غير محسوم {status_counts.get('UNRESOLVED', 0)}"
        ),
        (
            f"Top 5 مؤهل: {report.get('top5_eligible_count', 0)} | "
            f"مؤهل للتحليل: {report.get('analysis_eligible_count', 0)}"
        ),
        f"الإجراء البشري الوحيد: {action.get('action', 'NO_IMMEDIATE_ACTION')}",
        f"السبب: {action.get('reason', '')}",
        "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
    ]
    return "\n".join(lines) + "\n"


def write_checkpoint_artifacts(
    report: Mapping[str, Any], output_dir: str | Path
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "multi-market-daily-checkpoint.json"
    summary_path = target / "multi-market-phone-summary.txt"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(render_phone_summary(report), encoding="utf-8")
    return {"report": report_path, "phone_summary": summary_path}