"""Decode the compact historical Production Search Outcome seed."""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.production_search_outcome_bridge_v1 import MARKETS, PROVIDER
from opportunity_engine.production_search_outcome_history_seed_v1 import (
    DEFAULT_SEED_PATH,
    SCHEMA_VERSION,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


_RUN_FIELDS = (
    "sample_date",
    "generated_at",
    "source_run_id",
    "source_artifact_id",
    "resolution_schema_version",
    "query_outcome_count",
    "hits_received",
    "fresh_strict_exact_lot_count",
    "recovery_strict_exact_lot_count",
)
_RECORD_FIELDS = (
    "source_run_index",
    "market_code",
    "query_stage",
    "query",
    "hits_received",
    "fresh_strict_exact_lot_count",
    "fresh_identity_hashes",
)
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


def _day(value: object) -> str:
    text = _text(value)
    return text[:10] if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-" else ""


def _outcome_id(*, day: str, market: str, stage: str, query: str) -> str:
    identity = f"{day}|{market}|{PROVIDER}|{stage}|{query}"
    return "production-search-history:" + sha256(identity.encode("utf-8")).hexdigest()[:24]


def load_compact_historical_query_outcome_seed(
    path: str | Path = DEFAULT_SEED_PATH,
) -> dict[str, Any]:
    """Expand and reconcile the compact versioned history seed."""
    seed_path = Path(path)
    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical query seed {seed_path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("historical query seed root must be an object")
    if _text(raw.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported historical query seed schema")
    if _text(raw.get("project_domain")).upper() != CLOTHING_INVENTORY:
        raise ValueError("historical query seed escaped CLOTHING_INVENTORY")
    if _text(raw.get("provider")).lower() != PROVIDER:
        raise ValueError("historical query seed provider is not Exa")
    coverage = [_text(value).upper() for value in raw.get("market_coverage") or []]
    if coverage != list(MARKETS):
        raise ValueError("historical query seed must preserve exactly six markets")
    if tuple(raw.get("source_run_fields") or ()) != _RUN_FIELDS:
        raise ValueError("historical source-run compact contract changed")
    if tuple(raw.get("record_fields") or ()) != _RECORD_FIELDS:
        raise ValueError("historical record compact contract changed")
    for field in _SAFETY_FALSE_FIELDS:
        if raw.get(field) is not False:
            raise ValueError(f"historical query seed changed safety field {field}")
    if raw.get("recovery_query_credit_blocked") is not True:
        raise ValueError("historical Recovery query credit must remain blocked")

    source_runs: list[dict[str, Any]] = []
    days: set[str] = set()
    for values in raw.get("source_runs") or []:
        if not isinstance(values, list) or len(values) != len(_RUN_FIELDS):
            raise ValueError("malformed compact source-run row")
        run = dict(zip(_RUN_FIELDS, values))
        day = _day(run["sample_date"])
        if not day or _day(run["generated_at"]) != day or day in days:
            raise ValueError("historical source runs must be one valid checkpoint per UTC day")
        days.add(day)
        run["unattributed_fresh_exact_lot_count"] = 0
        source_runs.append(run)

    records: list[dict[str, Any]] = []
    identities: set[str] = set()
    per_run: dict[int, dict[str, int]] = defaultdict(
        lambda: {"queries": 0, "hits": 0, "fresh": 0}
    )
    daily_keys: set[tuple[str, str, str, str]] = set()
    for values in raw.get("records") or []:
        if not isinstance(values, list) or len(values) != len(_RECORD_FIELDS):
            raise ValueError("malformed compact historical query row")
        row = dict(zip(_RECORD_FIELDS, values))
        run_index = row.pop("source_run_index")
        if not isinstance(run_index, int) or not 0 <= run_index < len(source_runs):
            raise ValueError("historical record source_run_index is invalid")
        run = source_runs[run_index]
        day = _day(run["sample_date"])
        market = _text(row.get("market_code")).upper()
        stage = _text(row.get("query_stage")).upper()
        query = _text(row.get("query"))
        if market not in MARKETS or not stage or not query:
            raise ValueError("historical record lost market/query/stage identity")
        fresh_hashes = sorted(
            {
                _text(value)
                for value in row.get("fresh_identity_hashes") or []
                if _text(value)
            }
        )
        fresh = int(row.get("fresh_strict_exact_lot_count") or 0)
        if fresh != len(fresh_hashes):
            raise ValueError("historical Fresh count does not reconcile to identity hashes")
        key = (day, market, stage, query)
        if key in daily_keys:
            raise ValueError("historical seed duplicated a query within one UTC day")
        daily_keys.add(key)
        identities.update(fresh_hashes)
        per_run[run_index]["queries"] += 1
        per_run[run_index]["hits"] += int(row.get("hits_received") or 0)
        per_run[run_index]["fresh"] += fresh
        row["market_code"] = market
        row["query_stage"] = stage
        row["query"] = query
        row["fresh_identity_hashes"] = fresh_hashes
        row["source_run_id"] = _text(run["source_run_id"])
        row["outcome_id"] = _outcome_id(day=day, market=market, stage=stage, query=query)
        records.append(row)

    for index, run in enumerate(source_runs):
        counts = per_run[index]
        if int(run["query_outcome_count"]) != counts["queries"]:
            raise ValueError("historical source-run query count does not reconcile")
        if int(run["hits_received"]) != counts["hits"]:
            raise ValueError("historical source-run hits do not reconcile")
        if int(run["fresh_strict_exact_lot_count"]) != counts["fresh"]:
            raise ValueError("historical source-run Fresh count does not reconcile")
        run["search_request_count"] = counts["queries"]

    counts = raw.get("counts") if isinstance(raw.get("counts"), Mapping) else {}
    totals = {
        "days": len(days),
        "runs": len(source_runs),
        "queries": len(records),
        "requests": len(records),
        "hits": sum(int(row.get("hits_received") or 0) for row in records),
        "fresh": sum(int(row.get("fresh_strict_exact_lot_count") or 0) for row in records),
        "unique_fresh": len(identities),
        "recovery": sum(int(run["recovery_strict_exact_lot_count"]) for run in source_runs),
        "unattributed_fresh": 0,
    }
    if {key: int(counts.get(key) or 0) for key in totals} != totals:
        raise ValueError("historical compact seed totals do not reconcile")

    window = raw.get("window") or []
    if not isinstance(window, list) or len(window) != 2:
        raise ValueError("historical seed window is malformed")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "project_domain": CLOTHING_INVENTORY,
        "provider": PROVIDER,
        "market_coverage": list(MARKETS),
        "selection_policy": _text(raw.get("selection_policy")),
        "window_start": _text(window[0]),
        "window_end": _text(window[1]),
        "independent_checkpoint_day_count": totals["days"],
        "source_run_count": totals["runs"],
        "source_runs": source_runs,
        "query_outcome_count": totals["queries"],
        "search_request_count": totals["requests"],
        "hits_received": totals["hits"],
        "fresh_strict_exact_lot_count": totals["fresh"],
        "unique_fresh_strict_exact_lot_count": totals["unique_fresh"],
        "recovery_strict_exact_lot_count": totals["recovery"],
        "unattributed_fresh_exact_lot_count": 0,
        "recovery_query_credit_blocked": True,
        "records": records,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }
