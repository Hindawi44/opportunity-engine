"""Bridge live Exa Exact-Lot query outcomes into review-only learning evidence.

The bridge consumes artifacts already emitted by the six-market production
Exact-Lot runtime. It performs no network search and does not re-run the Exact-Lot
qualification gate. ``all-discovered-candidates.json`` is treated as the final
strict Exact-Lot truth, while ``exa-exact-lot-resolution.json`` supplies the
executed query/stage ledger.

Recovery navigation memory is intentionally never credited to a live query.
Only fresh current-search Exact-Lots contribute to query yield.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


SCHEMA_VERSION = "production-search-outcome-bridge-1.0"
OUTPUT_FILENAME = "production-search-outcome-bridge-v1.json"
MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
PROVIDER = "exa"

_SAFETY_FALSE_FIELDS = (
    "automatic_query_activation",
    "automatic_provider_activation",
    "automatic_source_promotion",
    "automatic_code_change",
    "production_query_mutation",
    "production_mutation",
    "automatic_contact",
    "automatic_bid",
    "automatic_reservation",
    "automatic_purchase",
    "automatic_payment",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _read_payload(path: Path) -> object:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON artifact {path.as_posix()}: {exc}") from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _candidate_url(candidate: Mapping[str, Any]) -> str:
    for field in ("canonical_urls", "source_urls"):
        values = candidate.get(field)
        if isinstance(values, list):
            for value in values:
                clean = _text(value)
                if clean:
                    return clean
    return _text(candidate.get("opportunity_identity"))


def _is_recovery(candidate: Mapping[str, Any]) -> bool:
    provenance = _upper(
        candidate.get("retrieval_provenance")
        or candidate.get("exact_lot_origin")
    )
    return bool(
        provenance == "PROVEN_ROUTE_RECOVERY"
        or candidate.get("route_memory_reverified") is True
    )


def _found_queries(candidate: Mapping[str, Any]) -> list[str]:
    values = candidate.get("found_by_queries")
    if not isinstance(values, list):
        return []
    return [_text(value) for value in values if _text(value)]


def _record_id(*, market: str, query: str, stage: str) -> str:
    digest = sha256(
        f"{market}|{PROVIDER}|{stage}|{query}".encode("utf-8")
    ).hexdigest()[:24]
    return f"production-search-outcome:{digest}"


def _validate_resolution(resolution: Mapping[str, Any], *, market: str) -> None:
    schema = _text(resolution.get("schema_version"))
    if not schema.startswith("exa-exact-lot-checkpoint-resolution-"):
        raise ValueError(f"{market} resolution has unsupported schema: {schema or 'MISSING'}")
    if _upper(resolution.get("market")) != market:
        raise ValueError(f"{market} resolution market identity mismatch")
    if _upper(resolution.get("project_domain")) != CLOTHING_INVENTORY:
        raise ValueError(f"{market} resolution escaped CLOTHING_INVENTORY")
    if _text(resolution.get("provider")).lower() != PROVIDER:
        raise ValueError(f"{market} resolution provider is not Exa")
    if resolution.get("production_mutation") not in {None, False}:
        raise ValueError(f"{market} resolution changed production_mutation safety")


def _validate_report(
    report: Mapping[str, Any],
    *,
    market: str,
    query_count: int,
    candidate_count: int,
    fresh_count: int,
    recovery_count: int,
) -> None:
    if _upper(report.get("market_code")) not in {"", market}:
        raise ValueError(f"{market} search report market identity mismatch")

    if report.get("queries_submitted") is not None:
        if int(report.get("queries_submitted") or 0) != query_count:
            raise ValueError(f"{market} query ledger does not reconcile with search report")

    if report.get("strict_exact_lot_count") is not None:
        if int(report.get("strict_exact_lot_count") or 0) != candidate_count:
            raise ValueError(f"{market} strict Exact-Lot candidates do not reconcile with report")

    if report.get("current_exa_discovery_strict_exact_lot_count") is not None:
        if int(report.get("current_exa_discovery_strict_exact_lot_count") or 0) != fresh_count:
            raise ValueError(f"{market} fresh Exact-Lot provenance does not reconcile with report")

    if report.get("freshly_reverified_recovery_exact_lot_count") is not None:
        if int(report.get("freshly_reverified_recovery_exact_lot_count") or 0) != recovery_count:
            raise ValueError(f"{market} recovery Exact-Lot provenance does not reconcile with report")


def _market_outcomes(
    *,
    market: str,
    resolution: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
    report: Mapping[str, Any],
    source_path: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _validate_resolution(resolution, market=market)
    query_rows = _rows(resolution.get("queries"))

    executed: list[dict[str, Any]] = []
    query_to_indexes: dict[str, list[int]] = {}
    for raw in query_rows:
        query = _text(raw.get("query"))
        stage = _upper(raw.get("query_stage"))
        if not query or not stage:
            raise ValueError(f"{market} production query row is missing query or query_stage")
        index = len(executed)
        executed.append(
            {
                "query": query,
                "query_stage": stage,
                "hits_received": len(_rows(raw.get("hits"))),
                "fresh_urls": [],
            }
        )
        query_to_indexes.setdefault(query, []).append(index)

    fresh_candidates: list[Mapping[str, Any]] = []
    recovery_candidates: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if _is_recovery(candidate):
            recovery_candidates.append(candidate)
        else:
            fresh_candidates.append(candidate)

    _validate_report(
        report,
        market=market,
        query_count=len(executed),
        candidate_count=len(candidates),
        fresh_count=len(fresh_candidates),
        recovery_count=len(recovery_candidates),
    )

    attributed_urls: set[str] = set()
    unattributed_urls: set[str] = set()
    ambiguous_query_identity_count = 0

    for candidate in fresh_candidates:
        url = _candidate_url(candidate)
        matches: list[int] = []
        for found_query in _found_queries(candidate):
            matches.extend(query_to_indexes.get(found_query, []))
        matches = sorted(set(matches))
        if not matches:
            if url:
                unattributed_urls.add(url)
            continue
        if len(matches) > 1:
            ambiguous_query_identity_count += 1
        chosen = matches[0]
        if url:
            executed[chosen]["fresh_urls"].append(url)
            attributed_urls.add(url)

    records: list[dict[str, Any]] = []
    generated_at = _text(resolution.get("generated_at")) or None
    for row in executed:
        urls = sorted(set(row.pop("fresh_urls")))
        fresh_count = len(urls)
        request_count = 1
        records.append(
            {
                "outcome_id": _record_id(
                    market=market,
                    query=row["query"],
                    stage=row["query_stage"],
                ),
                "market_code": market,
                "project_domain": CLOTHING_INVENTORY,
                "provider": PROVIDER,
                "query": row["query"],
                "query_stage": row["query_stage"],
                "search_request_count": request_count,
                "hits_received": row["hits_received"],
                "fresh_strict_exact_lot_count": fresh_count,
                "fresh_strict_exact_lot_urls": urls,
                "recovery_exact_lot_count": 0,
                "fresh_yield_per_request": fresh_count / request_count,
                "outcome": "FRESH_SUCCESS" if fresh_count else "FRESH_ZERO",
                "generated_at": generated_at,
                "source_path": source_path,
                "recovery_query_credit_blocked": True,
                "attribution_complete_for_record": True,
                **{field: False for field in _SAFETY_FALSE_FIELDS},
            }
        )

    fresh_urls = {_candidate_url(row) for row in fresh_candidates if _candidate_url(row)}
    recovery_urls = {_candidate_url(row) for row in recovery_candidates if _candidate_url(row)}
    summary = {
        "status": "SUCCESS" if records else "VALID_ZERO_NO_EXECUTED_QUERIES",
        "query_outcome_count": len(records),
        "search_request_count": len(records),
        "hits_received": sum(int(row["hits_received"]) for row in records),
        "strict_exact_lot_count": len(candidates),
        "fresh_strict_exact_lot_count": len(fresh_candidates),
        "recovery_strict_exact_lot_count": len(recovery_candidates),
        "attributed_fresh_exact_lot_count": len(attributed_urls),
        "unattributed_fresh_exact_lot_count": len(unattributed_urls),
        "unattributed_fresh_exact_lot_urls": sorted(unattributed_urls),
        "fresh_exact_lot_urls": sorted(fresh_urls),
        "recovery_exact_lot_urls": sorted(recovery_urls),
        "fresh_attribution_complete": len(unattributed_urls) == 0,
        "ambiguous_query_identity_count": ambiguous_query_identity_count,
        "recovery_query_credit_blocked": True,
    }
    return records, summary


def build_production_search_outcome_bridge(
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    """Build query-level production outcomes without executing any search."""
    root = Path(input_root)
    records: list[dict[str, Any]] = []
    market_status: dict[str, dict[str, Any]] = {}

    for market in MARKETS:
        source_dir = root / f"{market.casefold()}-exa-exact-lot"
        resolution_path = source_dir / "exa-exact-lot-resolution.json"
        candidates_path = source_dir / "all-discovered-candidates.json"
        report_path = source_dir / "search-run-report.json"
        presence = {
            "resolution": resolution_path.exists(),
            "candidates": candidates_path.exists(),
            "search_report": report_path.exists(),
        }
        if not any(presence.values()):
            market_status[market] = {"status": "MISSING", **presence}
            continue
        if not all(presence.values()):
            market_status[market] = {"status": "INCOMPLETE_ARTIFACT_SET", **presence}
            continue

        resolution_payload = _read_payload(resolution_path)
        candidate_payload = _read_payload(candidates_path)
        report_payload = _read_payload(report_path)
        resolution = _mapping(resolution_payload)
        report = _mapping(report_payload)
        if not isinstance(candidate_payload, list):
            raise ValueError(f"{market} all-discovered-candidates root must be a list")
        candidates = [row for row in candidate_payload if isinstance(row, Mapping)]

        source_path = resolution_path.relative_to(root).as_posix()
        current, summary = _market_outcomes(
            market=market,
            resolution=resolution,
            candidates=candidates,
            report=report,
            source_path=source_path,
        )
        records.extend(current)
        market_status[market] = {**presence, **summary}

    status = "SUCCESS" if records else "VALID_ZERO"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "project_domain": CLOTHING_INVENTORY,
        "provider": PROVIDER,
        "market_coverage": list(MARKETS),
        "query_outcome_count": len(records),
        "search_request_count": sum(int(row["search_request_count"]) for row in records),
        "hits_received": sum(int(row["hits_received"]) for row in records),
        "fresh_strict_exact_lot_count": sum(
            int(row["fresh_strict_exact_lot_count"]) for row in market_status.values()
        ),
        "recovery_strict_exact_lot_count": sum(
            int(row["recovery_strict_exact_lot_count"])
            for row in market_status.values()
            if "recovery_strict_exact_lot_count" in row
        ),
        "unattributed_fresh_exact_lot_count": sum(
            int(row["unattributed_fresh_exact_lot_count"])
            for row in market_status.values()
            if "unattributed_fresh_exact_lot_count" in row
        ),
        "market_status": market_status,
        "records": records,
        "search_requests_added": 0,
        "page_fetches_added": 0,
        "providers_added": 0,
        "sources_added": 0,
        "markets_added": 0,
        "recovery_query_credit_blocked": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }


def write_production_search_outcome_bridge(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    report = build_production_search_outcome_bridge(input_root=input_root)
    _write_json(Path(output_dir) / OUTPUT_FILENAME, report)
    return report
