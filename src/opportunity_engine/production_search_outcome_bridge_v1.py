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

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


SCHEMA_VERSION = "production-search-outcome-bridge-1.0"
OUTPUT_FILENAME = "production-search-outcome-bridge-v1.json"
EVIDENCE_KIND = "PRODUCTION_SEARCH_QUERY_OUTCOME"
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
_MEMORY_PATCH_INSTALLED = False


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
        candidate.get("retrieval_provenance") or candidate.get("exact_lot_origin")
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
    if report.get("queries_submitted") is not None and int(
        report.get("queries_submitted") or 0
    ) != query_count:
        raise ValueError(f"{market} query ledger does not reconcile with search report")
    if report.get("strict_exact_lot_count") is not None and int(
        report.get("strict_exact_lot_count") or 0
    ) != candidate_count:
        raise ValueError(f"{market} strict Exact-Lot candidates do not reconcile with report")
    if report.get("current_exa_discovery_strict_exact_lot_count") is not None and int(
        report.get("current_exa_discovery_strict_exact_lot_count") or 0
    ) != fresh_count:
        raise ValueError(f"{market} fresh Exact-Lot provenance does not reconcile with report")
    if report.get("freshly_reverified_recovery_exact_lot_count") is not None and int(
        report.get("freshly_reverified_recovery_exact_lot_count") or 0
    ) != recovery_count:
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
        (recovery_candidates if _is_recovery(candidate) else fresh_candidates).append(candidate)

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
                "search_request_count": 1,
                "hits_received": row["hits_received"],
                "fresh_strict_exact_lot_count": fresh_count,
                "fresh_strict_exact_lot_urls": urls,
                "recovery_exact_lot_count": 0,
                "fresh_yield_per_request": float(fresh_count),
                "outcome": "FRESH_SUCCESS" if fresh_count else "FRESH_ZERO",
                "generated_at": generated_at,
                "source_path": source_path,
                "recovery_query_credit_blocked": True,
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


def build_production_search_outcome_bridge(*, input_root: str | Path) -> dict[str, Any]:
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

        resolution = _mapping(_read_payload(resolution_path))
        candidate_payload = _read_payload(candidates_path)
        report = _mapping(_read_payload(report_path))
        if not isinstance(candidate_payload, list):
            raise ValueError(f"{market} all-discovered-candidates root must be a list")
        candidates = [row for row in candidate_payload if isinstance(row, Mapping)]
        current, summary = _market_outcomes(
            market=market,
            resolution=resolution,
            candidates=candidates,
            report=report,
            source_path=resolution_path.relative_to(root).as_posix(),
        )
        records.extend(current)
        market_status[market] = {**presence, **summary}

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if records else "VALID_ZERO",
        "project_domain": CLOTHING_INVENTORY,
        "provider": PROVIDER,
        "market_coverage": list(MARKETS),
        "query_outcome_count": len(records),
        "search_request_count": sum(int(row["search_request_count"]) for row in records),
        "hits_received": sum(int(row["hits_received"]) for row in records),
        "fresh_strict_exact_lot_count": sum(
            int(row.get("fresh_strict_exact_lot_count") or 0) for row in market_status.values()
        ),
        "recovery_strict_exact_lot_count": sum(
            int(row.get("recovery_strict_exact_lot_count") or 0) for row in market_status.values()
        ),
        "unattributed_fresh_exact_lot_count": sum(
            int(row.get("unattributed_fresh_exact_lot_count") or 0) for row in market_status.values()
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


def _spine_record(row: Mapping[str, Any]) -> dict[str, Any]:
    urls = [_text(url) for url in row.get("fresh_strict_exact_lot_urls") or [] if _text(url)]
    return {
        "learning_evidence_id": _text(row.get("outcome_id")),
        "evidence_kind": EVIDENCE_KIND,
        "market_code": _upper(row.get("market_code")),
        "project_domain": CLOTHING_INVENTORY,
        "source_name": f"Exa Exact-Lot {_upper(row.get('market_code'))}",
        "provider": PROVIDER,
        "query": _text(row.get("query")) or None,
        "url": urls[0] if urls else None,
        "result_type": "PRODUCTION_QUERY_OUTCOME",
        "outcome": _upper(row.get("outcome")) or None,
        "miss_reason": None,
        "route": _upper(row.get("query_stage")) or None,
        "source_identity": _text(row.get("source_path")) or None,
        "observed_at": _text(row.get("generated_at")) or None,
        "supporting_run_ids": [],
        "metadata": {
            "query_stage": _upper(row.get("query_stage")) or None,
            "search_request_count": int(row.get("search_request_count") or 0),
            "hits_received": int(row.get("hits_received") or 0),
            "fresh_strict_exact_lot_count": int(row.get("fresh_strict_exact_lot_count") or 0),
            "fresh_strict_exact_lot_urls": urls,
            "recovery_exact_lot_count": 0,
            "fresh_yield_per_request": float(row.get("fresh_yield_per_request") or 0.0),
            "recovery_query_credit_blocked": True,
            "source_path": _text(row.get("source_path")) or None,
        },
    }


def augment_unified_learning_spine(
    spine: Mapping[str, Any],
    bridge: Mapping[str, Any],
) -> dict[str, Any]:
    """Append truthful production query outcomes to an already-built Spine V1."""
    output = dict(spine)
    if not _text(output.get("schema_version")).startswith("unified-learning-spine-1."):
        raise ValueError("production search outcomes require Unified Learning Spine V1")
    if _text(bridge.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported production search outcome bridge schema")
    for field in _SAFETY_FALSE_FIELDS:
        if bridge.get(field) is not False:
            raise ValueError(f"production search outcome bridge changed safety field {field}")

    by_id: dict[str, dict[str, Any]] = {
        _text(row.get("learning_evidence_id")): dict(row)
        for row in _rows(output.get("records"))
        if _text(row.get("learning_evidence_id"))
    }
    for raw in _rows(bridge.get("records")):
        record = _spine_record(raw)
        if not record["learning_evidence_id"]:
            raise ValueError("production search outcome is missing a stable evidence id")
        by_id[record["learning_evidence_id"]] = record

    records = sorted(
        by_id.values(),
        key=lambda row: (
            _upper(row.get("market_code")),
            _upper(row.get("evidence_kind")),
            _text(row.get("source_identity")),
            _text(row.get("learning_evidence_id")),
        ),
    )
    output["records"] = records
    output["evidence_record_count"] = len(records)
    output["market_counts"] = dict(
        sorted(Counter(_upper(row.get("market_code")) for row in records if _upper(row.get("market_code"))).items())
    )
    output["domain_counts"] = dict(
        sorted(Counter(_upper(row.get("project_domain")) for row in records if _upper(row.get("project_domain"))).items())
    )
    output["evidence_kind_counts"] = dict(
        sorted(Counter(_upper(row.get("evidence_kind")) for row in records if _upper(row.get("evidence_kind"))).items())
    )
    presence = dict(_mapping(output.get("input_presence")))
    presence["production_search_outcome_bridge"] = True
    output["input_presence"] = presence
    output["production_search_outcome_bridge"] = {
        "schema_version": bridge.get("schema_version"),
        "status": bridge.get("status"),
        "query_outcome_count": bridge.get("query_outcome_count", 0),
        "search_request_count": bridge.get("search_request_count", 0),
        "fresh_strict_exact_lot_count": bridge.get("fresh_strict_exact_lot_count", 0),
        "recovery_strict_exact_lot_count": bridge.get("recovery_strict_exact_lot_count", 0),
        "unattributed_fresh_exact_lot_count": bridge.get("unattributed_fresh_exact_lot_count", 0),
        "recovery_query_credit_blocked": True,
        "production_mutation": False,
    }
    if records:
        output["status"] = "SUCCESS"
    output["learning_contract"] = (
        "Source artifacts -> Unified Market Intelligence River + Production Search Outcome Bridge "
        "-> Unified Learning Spine. Fresh Exact-Lot query yield is learning evidence only; "
        "recovery never receives live-query credit."
    )
    return output


def install_unified_memory_query_outcome_metrics() -> None:
    """Teach Memory V2 to persist per-run fresh query-yield observations.

    This is an additive compatibility patch. It changes no search decision and
    keeps the existing Memory V2 schema/version and safety contract.
    """
    global _MEMORY_PATCH_INSTALLED
    if _MEMORY_PATCH_INSTALLED:
        return

    import opportunity_engine.unified_memory_v2 as memory_v2

    original_run_observation = memory_v2._run_observation
    original_query_memory = memory_v2._query_memory

    def run_observation(record: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        observation = original_run_observation(record, run_id)
        if _upper(record.get("evidence_kind")) != EVIDENCE_KIND:
            return observation
        metadata = _mapping(record.get("metadata"))
        observation.update(
            {
                "query_stage": _upper(metadata.get("query_stage") or record.get("route")) or None,
                "search_request_count": int(metadata.get("search_request_count") or 0),
                "hits_received": int(metadata.get("hits_received") or 0),
                "fresh_strict_exact_lot_count": int(
                    metadata.get("fresh_strict_exact_lot_count") or 0
                ),
                "fresh_strict_exact_lot_urls": [
                    _text(url)
                    for url in metadata.get("fresh_strict_exact_lot_urls") or []
                    if _text(url)
                ],
                "recovery_exact_lot_count": 0,
                "recovery_query_credit_blocked": True,
            }
        )
        return observation

    def query_memory(evidence_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        output = original_query_memory(evidence_rows)
        metrics: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in evidence_rows:
            if _upper(row.get("evidence_kind")) != EVIDENCE_KIND:
                continue
            query = _text(row.get("query"))
            if not query:
                continue
            key = (
                _upper(row.get("market_code")),
                _text(row.get("provider")).lower(),
                query,
            )
            bucket = metrics.setdefault(
                key,
                {
                    "search_request_count": 0,
                    "hits_received": 0,
                    "fresh_strict_exact_lot_count": 0,
                    "fresh_success_run_count": 0,
                    "fresh_zero_run_count": 0,
                    "query_stage_counts": Counter(),
                    "fresh_exact_lot_urls": set(),
                },
            )
            for observation in _rows(row.get("run_observations")):
                requests = int(observation.get("search_request_count") or 0)
                if requests <= 0:
                    continue
                fresh = int(observation.get("fresh_strict_exact_lot_count") or 0)
                bucket["search_request_count"] += requests
                bucket["hits_received"] += int(observation.get("hits_received") or 0)
                bucket["fresh_strict_exact_lot_count"] += fresh
                bucket["fresh_success_run_count"] += int(fresh > 0)
                bucket["fresh_zero_run_count"] += int(fresh == 0)
                stage = _upper(observation.get("query_stage"))
                if stage:
                    bucket["query_stage_counts"][stage] += requests
                bucket["fresh_exact_lot_urls"].update(
                    _text(url)
                    for url in observation.get("fresh_strict_exact_lot_urls") or []
                    if _text(url)
                )

        for row in output:
            key = (
                _upper(row.get("market_code")),
                _text(row.get("provider")).lower(),
                _text(row.get("query")),
            )
            metric = metrics.get(key)
            if not metric:
                continue
            requests = int(metric["search_request_count"])
            fresh = int(metric["fresh_strict_exact_lot_count"])
            row.update(
                {
                    "production_search_request_count": requests,
                    "production_hits_received": int(metric["hits_received"]),
                    "fresh_strict_exact_lot_count": fresh,
                    "fresh_yield_per_request": (fresh / requests) if requests else 0.0,
                    "fresh_success_run_count": int(metric["fresh_success_run_count"]),
                    "fresh_zero_run_count": int(metric["fresh_zero_run_count"]),
                    "query_stage_counts": dict(sorted(metric["query_stage_counts"].items())),
                    "fresh_exact_lot_url_count": len(metric["fresh_exact_lot_urls"]),
                    "fresh_exact_lot_urls": sorted(metric["fresh_exact_lot_urls"]),
                    "recovery_exact_lot_query_credit": 0,
                    "recovery_query_credit_blocked": True,
                }
            )
        return output

    memory_v2._run_observation = run_observation
    memory_v2._query_memory = query_memory
    _MEMORY_PATCH_INSTALLED = True
