"""Versioned historical production Exact-Lot query evidence.

The seed contains only evidence already produced by successful GitHub Actions
checkpoints. One complete compatible checkpoint is retained per UTC day, so
manual reruns cannot inflate search learning.

This module performs no search, no page fetch, no provider/source activation and
no production mutation. Recovery remains market-level context and never receives
query credit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.production_search_outcome_bridge_v1 import (
    EVIDENCE_KIND,
    MARKETS,
    PROVIDER,
    SCHEMA_VERSION as LIVE_BRIDGE_SCHEMA,
    install_unified_memory_query_outcome_metrics,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


SCHEMA_VERSION = "production-search-outcome-history-seed-1.0"
DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "learning"
    / "production-search-outcome-history-seed-v1.json"
)
_MEMORY_PATCH_INSTALLED = False
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


def _checkpoint_day(value: object) -> str:
    text = _text(value)
    if (
        len(text) >= 10
        and text[4:5] == "-"
        and text[7:8] == "-"
        and text[:4].isdigit()
        and text[5:7].isdigit()
        and text[8:10].isdigit()
    ):
        return text[:10]
    return ""


def _validate_safety(payload: Mapping[str, Any], *, label: str) -> None:
    for field in _SAFETY_FALSE_FIELDS:
        if payload.get(field) is not False:
            raise ValueError(f"{label} changed safety field {field}")


def _source_run_index(seed: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(row.get("source_run_id")): row
        for row in _rows(seed.get("source_runs"))
        if _text(row.get("source_run_id"))
    }


def load_historical_query_outcome_seed(
    path: str | Path = DEFAULT_SEED_PATH,
) -> dict[str, Any]:
    """Load and fully reconcile the one-checkpoint-per-day evidence seed."""
    seed_path = Path(path)
    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical query outcome seed {seed_path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("historical query outcome seed root must be an object")
    seed = dict(payload)

    if _text(seed.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported historical query outcome seed schema")
    if _upper(seed.get("project_domain")) != CLOTHING_INVENTORY:
        raise ValueError("historical query outcome seed escaped CLOTHING_INVENTORY")
    if _text(seed.get("provider")).lower() != PROVIDER:
        raise ValueError("historical query outcome seed provider is not Exa")
    coverage = [_upper(value) for value in seed.get("market_coverage") or [] if _upper(value)]
    if coverage != list(MARKETS):
        raise ValueError("historical query outcome seed must preserve the fixed six-market identity")
    _validate_safety(seed, label="historical query outcome seed")
    if seed.get("recovery_query_credit_blocked") is not True:
        raise ValueError("historical Recovery query credit must remain blocked")
    if int(seed.get("unattributed_fresh_exact_lot_count") or 0) != 0:
        raise ValueError("historical seed contains unattributed Fresh Exact-Lots")

    source_runs = _rows(seed.get("source_runs"))
    run_index: dict[str, Mapping[str, Any]] = {}
    day_index: dict[str, str] = {}
    for run in source_runs:
        run_id = _text(run.get("source_run_id"))
        day = _checkpoint_day(run.get("sample_date") or run.get("generated_at"))
        if not run_id or not day:
            raise ValueError("historical source run is missing run identity or UTC day")
        if run_id in run_index:
            raise ValueError(f"duplicate historical source run: {run_id}")
        if day in day_index:
            raise ValueError(f"multiple historical checkpoints selected for UTC day {day}")
        if _checkpoint_day(run.get("generated_at")) != day:
            raise ValueError(f"historical source run {run_id} generated_at/day mismatch")
        if int(run.get("unattributed_fresh_exact_lot_count") or 0) != 0:
            raise ValueError(f"historical source run {run_id} has unattributed Fresh Exact-Lots")
        run_index[run_id] = run
        day_index[day] = run_id

    if int(seed.get("source_run_count") or 0) != len(source_runs):
        raise ValueError("historical source_run_count does not reconcile")
    if int(seed.get("independent_checkpoint_day_count") or 0) != len(day_index):
        raise ValueError("historical independent day count does not reconcile")

    records = _rows(seed.get("records"))
    ids: set[str] = set()
    per_day_query_keys: set[tuple[str, str, str, str]] = set()
    unique_urls: set[str] = set()
    requests = hits = fresh = 0
    per_run_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"queries": 0, "hits": 0, "fresh": 0}
    )
    for row in records:
        outcome_id = _text(row.get("outcome_id"))
        market = _upper(row.get("market_code"))
        query = _text(row.get("query"))
        stage = _upper(row.get("query_stage"))
        run_id = _text(row.get("source_run_id"))
        source_run = _mapping(run_index.get(run_id))
        day = _checkpoint_day(source_run.get("sample_date") or source_run.get("generated_at"))
        if not outcome_id or outcome_id in ids:
            raise ValueError("historical record outcome_id must be present and unique")
        ids.add(outcome_id)
        if market not in MARKETS:
            raise ValueError(f"historical record added unsupported market {market}")
        if not query or not stage:
            raise ValueError("historical record is missing exact query text or query stage")
        if not source_run or not day:
            raise ValueError("historical record does not reconcile to a selected source run")
        key = (day, market, stage, query)
        if key in per_day_query_keys:
            raise ValueError("historical seed duplicated a query within one UTC checkpoint")
        per_day_query_keys.add(key)

        urls = sorted({_text(url) for url in row.get("fresh_strict_exact_lot_urls") or [] if _text(url)})
        fresh_count = int(row.get("fresh_strict_exact_lot_count") or 0)
        if fresh_count != len(urls):
            raise ValueError("historical Fresh count does not reconcile to unique row URLs")
        hit_count = int(row.get("hits_received") or 0)
        requests += 1
        hits += hit_count
        fresh += fresh_count
        unique_urls.update(urls)
        per_run_counts[run_id]["queries"] += 1
        per_run_counts[run_id]["hits"] += hit_count
        per_run_counts[run_id]["fresh"] += fresh_count

    for run_id, run in run_index.items():
        counts = per_run_counts[run_id]
        if int(run.get("query_outcome_count") or 0) != counts["queries"]:
            raise ValueError(f"historical source run {run_id} query count does not reconcile")
        if int(run.get("search_request_count") or 0) != counts["queries"]:
            raise ValueError(f"historical source run {run_id} request count does not reconcile")
        if int(run.get("hits_received") or 0) != counts["hits"]:
            raise ValueError(f"historical source run {run_id} hit count does not reconcile")
        if int(run.get("fresh_strict_exact_lot_count") or 0) != counts["fresh"]:
            raise ValueError(f"historical source run {run_id} Fresh count does not reconcile")

    if int(seed.get("query_outcome_count") or 0) != len(records):
        raise ValueError("historical query_outcome_count does not reconcile")
    if int(seed.get("search_request_count") or 0) != requests:
        raise ValueError("historical search_request_count does not reconcile")
    if int(seed.get("hits_received") or 0) != hits:
        raise ValueError("historical hits_received does not reconcile")
    if int(seed.get("fresh_strict_exact_lot_count") or 0) != fresh:
        raise ValueError("historical Fresh Exact-Lot count does not reconcile")
    if int(seed.get("unique_fresh_strict_exact_lot_count") or 0) != len(unique_urls):
        raise ValueError("historical unique Fresh Exact-Lot count does not reconcile")
    if int(seed.get("recovery_strict_exact_lot_count") or 0) != sum(
        int(row.get("recovery_strict_exact_lot_count") or 0) for row in source_runs
    ):
        raise ValueError("historical Recovery count does not reconcile")

    return seed


def _complete_six_market_live_bridge(bridge: Mapping[str, Any]) -> bool:
    if _text(bridge.get("schema_version")) != LIVE_BRIDGE_SCHEMA:
        return False
    market_status = _mapping(bridge.get("market_status"))
    for market in MARKETS:
        status = _mapping(market_status.get(market))
        if not (
            status.get("resolution") is True
            and status.get("candidates") is True
            and status.get("search_report") is True
        ):
            return False
    return True


def _historical_spine_record(
    row: Mapping[str, Any],
    *,
    source_run: Mapping[str, Any],
) -> dict[str, Any]:
    market = _upper(row.get("market_code"))
    query = _text(row.get("query"))
    stage = _upper(row.get("query_stage"))
    run_id = _text(source_run.get("source_run_id"))
    generated_at = _text(source_run.get("generated_at"))
    sample_date = _checkpoint_day(source_run.get("sample_date") or generated_at)
    urls = sorted({_text(url) for url in row.get("fresh_strict_exact_lot_urls") or [] if _text(url)})
    fresh = int(row.get("fresh_strict_exact_lot_count") or 0)
    source_path = (
        f"historical-seed/run-{run_id}/"
        f"{market.casefold()}-exa-exact-lot/exa-exact-lot-resolution.json"
    )
    return {
        "learning_evidence_id": _text(row.get("outcome_id")),
        "evidence_kind": EVIDENCE_KIND,
        "market_code": market,
        "project_domain": CLOTHING_INVENTORY,
        "source_name": f"Exa Exact-Lot {market}",
        "provider": PROVIDER,
        "query": query,
        "url": urls[0] if urls else None,
        "result_type": "PRODUCTION_QUERY_OUTCOME_HISTORY",
        "outcome": "FRESH_SUCCESS" if fresh else "FRESH_ZERO",
        "miss_reason": None,
        "route": stage,
        "source_identity": source_path,
        "observed_at": generated_at or None,
        "supporting_run_ids": [run_id],
        "metadata": {
            "historical_seed": True,
            "sample_date": sample_date,
            "source_run_id": run_id,
            "source_artifact_id": source_run.get("source_artifact_id"),
            "source_resolution_schema_version": _text(
                source_run.get("resolution_schema_version")
            )
            or None,
            "query_stage": stage,
            "search_request_count": 1,
            "hits_received": int(row.get("hits_received") or 0),
            "fresh_strict_exact_lot_count": fresh,
            "fresh_strict_exact_lot_urls": urls,
            "recovery_exact_lot_count": 0,
            "fresh_yield_per_request": float(fresh),
            "recovery_query_credit_blocked": True,
            "source_path": source_path,
        },
    }


def augment_unified_learning_spine_with_history(
    spine: Mapping[str, Any],
    historical_seed: Mapping[str, Any],
    *,
    live_bridge: Mapping[str, Any],
) -> dict[str, Any]:
    """Add one historical observation per query/day and suppress same-day live duplicates."""
    output = dict(spine)
    if not _text(output.get("schema_version")).startswith("unified-learning-spine-1."):
        raise ValueError("historical query outcomes require Unified Learning Spine V1")
    seed = dict(historical_seed)
    if _text(seed.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported historical query outcome seed")
    _validate_safety(seed, label="historical query outcome seed")

    if not _complete_six_market_live_bridge(live_bridge):
        output["production_search_outcome_history_seed"] = {
            "status": "SKIPPED_INCOMPLETE_LIVE_MARKET_SET",
            "schema_version": SCHEMA_VERSION,
            "records_added": 0,
            "search_requests_added": 0,
        }
        return output

    run_index = _source_run_index(seed)
    seed_days = {
        _checkpoint_day(run.get("sample_date") or run.get("generated_at"))
        for run in run_index.values()
    }
    seed_days.discard("")

    records = [dict(row) for row in _rows(output.get("records"))]
    retained: list[dict[str, Any]] = []
    suppressed_live = 0
    suppressed_dates: set[str] = set()
    for record in records:
        if _upper(record.get("evidence_kind")) == EVIDENCE_KIND:
            metadata = _mapping(record.get("metadata"))
            is_history = metadata.get("historical_seed") is True
            day = _checkpoint_day(record.get("observed_at"))
            if not is_history and day and day in seed_days:
                suppressed_live += 1
                suppressed_dates.add(day)
                continue
        retained.append(record)

    by_id = {
        _text(row.get("learning_evidence_id")): row
        for row in retained
        if _text(row.get("learning_evidence_id"))
    }
    added = 0
    for raw in _rows(seed.get("records")):
        source_run = _mapping(run_index.get(_text(raw.get("source_run_id"))))
        record = _historical_spine_record(raw, source_run=source_run)
        evidence_id = _text(record.get("learning_evidence_id"))
        if not evidence_id:
            raise ValueError("historical learning evidence id is required")
        if evidence_id not in by_id:
            added += 1
        by_id[evidence_id] = record

    merged = sorted(
        by_id.values(),
        key=lambda row: (
            _upper(row.get("market_code")),
            _upper(row.get("evidence_kind")),
            _text(row.get("source_identity")),
            _text(row.get("learning_evidence_id")),
        ),
    )
    evidence_kind_counts = Counter(
        _upper(row.get("evidence_kind")) for row in merged if _upper(row.get("evidence_kind"))
    )
    market_counts = Counter(
        _upper(row.get("market_code")) for row in merged if _upper(row.get("market_code"))
    )
    output.update(
        {
            "status": "SUCCESS" if merged else "VALID_ZERO",
            "records": merged,
            "evidence_record_count": len(merged),
            "evidence_kind_counts": dict(sorted(evidence_kind_counts.items())),
            "market_counts": dict(sorted(market_counts.items())),
            "production_search_outcome_history_seed": {
                "status": "APPLIED",
                "schema_version": SCHEMA_VERSION,
                "selection_policy": _text(seed.get("selection_policy")),
                "window_start": _text(seed.get("window_start")),
                "window_end": _text(seed.get("window_end")),
                "independent_checkpoint_day_count": int(
                    seed.get("independent_checkpoint_day_count") or 0
                ),
                "source_run_count": int(seed.get("source_run_count") or 0),
                "historical_record_count": int(seed.get("query_outcome_count") or 0),
                "historical_search_request_count": int(seed.get("search_request_count") or 0),
                "historical_fresh_strict_exact_lot_count": int(
                    seed.get("fresh_strict_exact_lot_count") or 0
                ),
                "historical_unique_fresh_strict_exact_lot_count": int(
                    seed.get("unique_fresh_strict_exact_lot_count") or 0
                ),
                "historical_recovery_strict_exact_lot_count": int(
                    seed.get("recovery_strict_exact_lot_count") or 0
                ),
                "records_added": added,
                "live_same_day_records_suppressed": suppressed_live,
                "suppressed_live_same_day_dates": sorted(suppressed_dates),
                "search_requests_added": 0,
                "recovery_query_credit_blocked": True,
            },
        }
    )
    return output


def install_historical_query_outcome_memory_metrics() -> None:
    """Persist history idempotently and expose raw + unique query yield."""
    global _MEMORY_PATCH_INSTALLED
    if _MEMORY_PATCH_INSTALLED:
        return

    install_unified_memory_query_outcome_metrics()

    import opportunity_engine.unified_memory_v2 as memory_v2

    original_run_observation = memory_v2._run_observation
    original_merge_evidence_row = memory_v2._merge_evidence_row
    original_query_memory = memory_v2._query_memory

    def run_observation(record: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        observation = original_run_observation(record, run_id)
        if _upper(record.get("evidence_kind")) != EVIDENCE_KIND:
            return observation
        metadata = _mapping(record.get("metadata"))
        historical = metadata.get("historical_seed") is True
        source_run_id = _text(metadata.get("source_run_id")) if historical else ""
        day = _checkpoint_day(metadata.get("sample_date") or record.get("observed_at"))
        observation.update(
            {
                "checkpoint_day": day or None,
                "historical_seed": historical,
                "source_run_id": source_run_id or run_id,
            }
        )
        return observation

    def merge_evidence_row(
        prior: Mapping[str, Any] | None,
        record: Mapping[str, Any],
        *,
        run_id: str,
    ) -> dict[str, Any]:
        metadata = _mapping(record.get("metadata"))
        effective_run_id = (
            _text(metadata.get("source_run_id"))
            if (
                _upper(record.get("evidence_kind")) == EVIDENCE_KIND
                and metadata.get("historical_seed") is True
            )
            else ""
        ) or run_id
        return original_merge_evidence_row(prior, record, run_id=effective_run_id)

    def query_memory(evidence_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        output = original_query_memory(evidence_rows)
        metrics: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "days": set(),
                "historical_observations": 0,
                "stage": defaultdict(
                    lambda: {
                        "requests": 0,
                        "fresh": 0,
                        "days": set(),
                        "urls": set(),
                    }
                ),
            }
        )
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
            bucket = metrics[key]
            for observation in _rows(row.get("run_observations")):
                requests = int(observation.get("search_request_count") or 0)
                fresh = int(observation.get("fresh_strict_exact_lot_count") or 0)
                stage = _upper(observation.get("query_stage")) or "UNKNOWN"
                day = _checkpoint_day(
                    observation.get("checkpoint_day") or observation.get("observed_at")
                )
                if day:
                    bucket["days"].add(day)
                    bucket["stage"][stage]["days"].add(day)
                if observation.get("historical_seed") is True:
                    bucket["historical_observations"] += 1
                stage_bucket = bucket["stage"][stage]
                stage_bucket["requests"] += requests
                stage_bucket["fresh"] += fresh
                stage_bucket["urls"].update(
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
            requests = int(row.get("production_search_request_count") or 0)
            unique_count = int(row.get("fresh_exact_lot_url_count") or 0)
            row.update(
                {
                    "independent_checkpoint_day_count": len(metric["days"]),
                    "checkpoint_days": sorted(metric["days"]),
                    "historical_seed_observation_count": int(metric["historical_observations"]),
                    "unique_fresh_yield_per_request": (
                        unique_count / requests if requests else 0.0
                    ),
                    "query_stage_metrics": {
                        stage: {
                            "search_request_count": int(stage_metric["requests"]),
                            "fresh_strict_exact_lot_count": int(stage_metric["fresh"]),
                            "unique_fresh_strict_exact_lot_count": len(stage_metric["urls"]),
                            "fresh_yield_per_request": (
                                stage_metric["fresh"] / stage_metric["requests"]
                                if stage_metric["requests"]
                                else 0.0
                            ),
                            "unique_fresh_yield_per_request": (
                                len(stage_metric["urls"]) / stage_metric["requests"]
                                if stage_metric["requests"]
                                else 0.0
                            ),
                            "independent_checkpoint_day_count": len(stage_metric["days"]),
                            "checkpoint_days": sorted(stage_metric["days"]),
                        }
                        for stage, stage_metric in sorted(metric["stage"].items())
                    },
                }
            )
        return output

    memory_v2._run_observation = run_observation
    memory_v2._merge_evidence_row = merge_evidence_row
    memory_v2._query_memory = query_memory
    _MEMORY_PATCH_INSTALLED = True
