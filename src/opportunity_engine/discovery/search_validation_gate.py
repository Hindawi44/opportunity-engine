"""Offline proof gate for search/discovery quality.

This module reads already-produced JSON artifacts only. It never calls Brave,
OpenAI, a source website, or any other network service. Its purpose is to keep
workflow success separate from search-quality proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "search-validation-gate-1.0"
ENGINE_VERSION = "SEARCH_VALIDATION_GATE_V1"
VERDICTS = {"PROVEN", "NOT_PROVEN", "INSUFFICIENT_EVIDENCE"}
CORE_MARKETS = ("NO", "SE", "DE")

_SUCCESS_STATUSES = {"PASS", "SUCCESS", "VALID_ZERO", "PARTIAL_RETRIEVAL"}


@dataclass(frozen=True, slots=True)
class SearchValidationPolicy:
    min_live_runs: int = 3
    min_retrieval_success_rate: float = 0.80
    min_productive_run_rate: float = 0.50
    min_verified_active_runs: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SearchObservation:
    run_label: str
    artifact_path: str
    observed_at: str | None
    market_code: str
    source_name: str
    execution_status: str
    queries_attempted: int | None
    queries_succeeded: int | None
    paid_search: bool | None
    paid_requests_made: int | None
    raw_hits: int | None
    accepted_leads: int
    rejected_results: int | None
    ended_or_historical: int
    verified_active_leads: int
    actionable_leads: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return int(value)


def _first_int(*values: object) -> int | None:
    for value in values:
        number = _int(value)
        if number is not None:
            return number
    return None


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _market(payload: Mapping[str, Any], fallback: str = "") -> str:
    for key in ("market_code", "source_country", "market"):
        value = _compact(payload.get(key)).upper()
        if len(value) == 2:
            return value
    return fallback.upper()


def _status(payload: Mapping[str, Any]) -> str:
    return (
        _compact(payload.get("execution_status"))
        or _compact(payload.get("status"))
        or "UNKNOWN"
    ).upper()


def _time(payload: Mapping[str, Any]) -> str | None:
    for key in ("generated_at", "captured_at", "executed_at", "observed_at"):
        value = _compact(payload.get(key))
        if value:
            return value
    return None


def _query_success_from_diagnostics(
    payload: Mapping[str, Any],
) -> tuple[int | None, int | None]:
    diagnostics = _list(payload.get("query_diagnostics")) or _list(
        payload.get("query_stats")
    )
    if diagnostics:
        attempted = len(diagnostics)
        succeeded = sum(
            1
            for row in diagnostics
            if _compact(
                _dict(row).get("status") or _dict(row).get("search_status")
            ).upper()
            in {"SUCCESS", "PASS"}
        )
        return attempted, succeeded
    return None, None


def _source_name(payload: Mapping[str, Any], path: Path) -> str:
    for key in (
        "source_target",
        "source_name",
        "source",
        "feed_family",
        "query_pack",
        "source_mode",
    ):
        value = _compact(payload.get(key))
        if value:
            return value
    return path.parent.name or path.stem


def _search_run_observation(
    payload: Mapping[str, Any], path: Path, run_label: str
) -> SearchObservation | None:
    market = _market(payload)
    if not market:
        return None
    source_diag = _dict(payload.get("source_diagnostics"))
    q_attempted, q_succeeded = _query_success_from_diagnostics(source_diag)
    q_attempted = _first_int(
        q_attempted, payload.get("queries_submitted"), payload.get("queries_attempted")
    )
    q_succeeded = _first_int(q_succeeded, payload.get("queries_succeeded"))
    if (
        q_succeeded is None
        and q_attempted is not None
        and _status(payload) in _SUCCESS_STATUSES
    ):
        q_succeeded = q_attempted

    paid_flag = payload.get("paid_search_used")
    if not isinstance(paid_flag, bool):
        paid_flag = True if _int(source_diag.get("requests_made")) is not None else None
    paid_requests = _first_int(
        source_diag.get("requests_made"), payload.get("requests_made")
    )
    if paid_flag is False:
        paid_requests = 0

    accepted = _first_int(
        payload.get("strong_leads_requiring_verification"),
        payload.get("merged_candidates"),
        source_diag.get("accepted_hits"),
    ) or 0
    confirmed = _first_int(
        payload.get("confirmed_sales"), payload.get("verified_active_count")
    ) or 0
    accepted = max(accepted, confirmed)
    actionable = max(
        _first_int(payload.get("analysis_eligible_count")) or 0,
        _first_int(payload.get("top5_count")) or 0,
    )
    return SearchObservation(
        run_label=run_label,
        artifact_path=path.as_posix(),
        observed_at=_time(payload),
        market_code=market,
        source_name=_source_name(payload, path),
        execution_status=_status(payload),
        queries_attempted=q_attempted,
        queries_succeeded=q_succeeded,
        paid_search=paid_flag,
        paid_requests_made=paid_requests,
        raw_hits=_first_int(
            source_diag.get("raw_hits"), payload.get("hits_received"), payload.get("raw_hits")
        ),
        accepted_leads=accepted,
        rejected_results=_first_int(
            source_diag.get("rejected_hits"),
            payload.get("rejected_results"),
            payload.get("rejected_result_count"),
        ),
        ended_or_historical=_first_int(
            payload.get("ended_or_historical"),
            source_diag.get("historical_item_count"),
            source_diag.get("historical_listing_count"),
        )
        or 0,
        verified_active_leads=confirmed,
        actionable_leads=actionable,
    )


def _market_discovery_observation(
    payload: Mapping[str, Any], path: Path, run_label: str
) -> SearchObservation | None:
    market = _market(payload)
    if not market:
        return None
    attempted, succeeded = _query_success_from_diagnostics(payload)
    attempted = _first_int(
        payload.get("queries_attempted"), attempted, payload.get("query_budget")
    )
    succeeded = _first_int(payload.get("queries_succeeded"), succeeded)
    accepted = _first_int(
        payload.get("accepted_signal_count"), payload.get("signal_count")
    ) or 0
    rejected = _first_int(payload.get("rejected_result_count"))
    duplicates = _first_int(payload.get("duplicate_result_count")) or 0
    raw = None if rejected is None else accepted + rejected + duplicates
    requests = _first_int(payload.get("requests_made"), attempted)
    return SearchObservation(
        run_label=run_label,
        artifact_path=path.as_posix(),
        observed_at=_time(payload),
        market_code=market,
        source_name=_source_name(payload, path),
        execution_status=_status(payload),
        queries_attempted=attempted,
        queries_succeeded=succeeded,
        paid_search=True,
        paid_requests_made=requests,
        raw_hits=raw,
        accepted_leads=accepted,
        rejected_results=rejected,
        ended_or_historical=0,
        verified_active_leads=_first_int(
            payload.get("verified_active_exact_lot_lead_count"),
            payload.get("confirmed_sales"),
        )
        or 0,
        actionable_leads=max(
            _first_int(payload.get("analysis_eligible_count")) or 0,
            _first_int(payload.get("top5_count")) or 0,
        ),
    )


def _auksjonen_observation(
    payload: Mapping[str, Any], path: Path, run_label: str
) -> SearchObservation | None:
    if not path.name.startswith("auksjonen-live-clothing-listings"):
        return None
    return SearchObservation(
        run_label=run_label,
        artifact_path=path.as_posix(),
        observed_at=_time(payload),
        market_code="NO",
        source_name="Auksjonen Public API",
        execution_status=(
            "SUCCESS" if not _list(payload.get("errors")) else "PARTIAL_RETRIEVAL"
        ),
        queries_attempted=None,
        queries_succeeded=None,
        paid_search=False,
        paid_requests_made=0,
        raw_hits=_first_int(payload.get("items_received"), payload.get("reported_size")),
        accepted_leads=_first_int(
            payload.get("valid_inventory_opportunity_count"),
            payload.get("inventory_lot_count"),
        )
        or 0,
        rejected_results=None,
        ended_or_historical=0,
        verified_active_leads=_first_int(payload.get("top5_count")) or 0,
        actionable_leads=_first_int(payload.get("top5_count")) or 0,
    )


def observations_from_payload(
    payload: object, path: Path, run_label: str
) -> list[SearchObservation]:
    if not isinstance(payload, Mapping):
        return []
    data = dict(payload)
    name = path.name
    if name == "search-run-report.json":
        item = _search_run_observation(data, path, run_label)
        return [item] if item else []
    if name == "auksjonen-live-clothing-listings.json":
        item = _auksjonen_observation(data, path, run_label)
        return [item] if item else []
    if "market-discovery" in name or data.get("feed_family") in {
        "ITALY_MARKET_DISCOVERY_V1",
        "NETHERLANDS_MARKET_DISCOVERY_V1",
        "FRANCE_MARKET_DISCOVERY_V1",
    }:
        item = _market_discovery_observation(data, path, run_label)
        return [item] if item else []
    if name == "brave-market-signal-radar.json":
        rows: list[SearchObservation] = []
        for source in _list(data.get("sources")):
            source_payload = _dict(source)
            item = _market_discovery_observation(source_payload, path, run_label)
            if item:
                rows.append(item)
        return rows
    return []


def load_observations(run_dirs: Sequence[str | Path]) -> list[SearchObservation]:
    observations: list[SearchObservation] = []
    seen: set[tuple[Any, ...]] = set()
    for raw in run_dirs:
        root = Path(raw)
        run_label = root.name
        candidates = [root] if root.is_file() else sorted(root.rglob("*.json"))
        for path in candidates:
            if (
                path.name
                not in {
                    "search-run-report.json",
                    "auksjonen-live-clothing-listings.json",
                    "brave-market-signal-radar.json",
                }
                and "market-discovery" not in path.name
            ):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for item in observations_from_payload(payload, path, run_label):
                key = (
                    item.run_label,
                    item.market_code,
                    item.source_name,
                    item.observed_at,
                    item.raw_hits,
                    item.accepted_leads,
                    item.verified_active_leads,
                )
                if key in seen:
                    continue
                seen.add(key)
                observations.append(item)
    return observations


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator <= 0 else round(numerator / denominator, 6)


def _source_verdict(
    rows: Sequence[SearchObservation], policy: SearchValidationPolicy
) -> dict[str, Any]:
    run_labels = sorted({row.run_label for row in rows})
    productive_runs = sorted(
        {row.run_label for row in rows if row.accepted_leads > 0}
    )
    verified_runs = sorted(
        {row.run_label for row in rows if row.verified_active_leads > 0}
    )
    queries_attempted = sum(row.queries_attempted or 0 for row in rows)
    queries_succeeded = sum(row.queries_succeeded or 0 for row in rows)
    retrieval_rate = _rate(queries_succeeded, queries_attempted)
    if retrieval_rate is None:
        retrieval_rate = _rate(
            sum(
                1
                for label in run_labels
                if any(
                    row.run_label == label
                    and row.execution_status in _SUCCESS_STATUSES
                    for row in rows
                )
            ),
            len(run_labels),
        )
    paid_rows = [row for row in rows if row.paid_search is True]
    request_accounting_complete = all(
        row.paid_requests_made is not None for row in paid_rows
    )
    paid_requests = sum(row.paid_requests_made or 0 for row in paid_rows)
    verified_active = sum(row.verified_active_leads for row in rows)
    accepted = sum(row.accepted_leads for row in rows)
    rejected = sum(row.rejected_results or 0 for row in rows)

    reasons: list[str] = []
    if len(run_labels) < policy.min_live_runs:
        reasons.append("MIN_LIVE_RUNS_NOT_MET")
    if not request_accounting_complete:
        reasons.append("PAID_REQUEST_ACCOUNTING_INCOMPLETE")

    enough_evidence = not reasons
    if enough_evidence:
        if (
            retrieval_rate is None
            or retrieval_rate < policy.min_retrieval_success_rate
        ):
            reasons.append("RETRIEVAL_SUCCESS_RATE_BELOW_THRESHOLD")
        productive_rate = _rate(len(productive_runs), len(run_labels)) or 0.0
        if productive_rate < policy.min_productive_run_rate:
            reasons.append("PRODUCTIVE_RUN_RATE_BELOW_THRESHOLD")
        if len(verified_runs) < policy.min_verified_active_runs:
            reasons.append("REPEATED_VERIFIED_ACTIVE_LEADS_NOT_PROVEN")
        verdict = "PROVEN" if not reasons else "NOT_PROVEN"
    else:
        productive_rate = _rate(len(productive_runs), len(run_labels))
        verdict = "INSUFFICIENT_EVIDENCE"

    assert verdict in VERDICTS
    return {
        "verdict": verdict,
        "reasons": reasons,
        "run_count": len(run_labels),
        "run_labels": run_labels,
        "productive_run_count": len(productive_runs),
        "productive_run_rate": productive_rate,
        "verified_active_run_count": len(verified_runs),
        "verified_active_lead_count": verified_active,
        "accepted_lead_count": accepted,
        "rejected_result_count": rejected,
        "retrieval_success_rate": retrieval_rate,
        "paid_request_accounting_complete": request_accounting_complete,
        "paid_requests_made": paid_requests,
        "paid_requests_per_verified_active_lead": _rate(
            paid_requests, verified_active
        ),
        "verification_conversion_rate": _rate(verified_active, accepted),
        "actionable_lead_count": sum(row.actionable_leads for row in rows),
        "ended_or_historical_count": sum(row.ended_or_historical for row in rows),
    }


def build_search_validation_report(
    observations: Sequence[SearchObservation],
    *,
    policy: SearchValidationPolicy | None = None,
    required_markets: Sequence[str] = CORE_MARKETS,
) -> dict[str, Any]:
    policy = policy or SearchValidationPolicy()
    grouped: dict[tuple[str, str], list[SearchObservation]] = {}
    for row in observations:
        grouped.setdefault((row.market_code, row.source_name), []).append(row)

    sources: list[dict[str, Any]] = []
    by_market_sources: dict[str, list[dict[str, Any]]] = {}
    for (market, source), rows in sorted(grouped.items()):
        result = {
            "market_code": market,
            "source_name": source,
            **_source_verdict(rows, policy),
            "observations": [row.to_dict() for row in rows],
        }
        sources.append(result)
        by_market_sources.setdefault(market, []).append(result)

    markets: list[dict[str, Any]] = []
    market_verdicts: dict[str, str] = {}
    all_markets = sorted(
        set(by_market_sources) | {market.upper() for market in required_markets}
    )
    for market in all_markets:
        source_rows = by_market_sources.get(market, [])
        verdicts = [row["verdict"] for row in source_rows]
        if any(verdict == "PROVEN" for verdict in verdicts):
            verdict = "PROVEN"
        elif source_rows and all(verdict == "NOT_PROVEN" for verdict in verdicts):
            verdict = "NOT_PROVEN"
        else:
            verdict = "INSUFFICIENT_EVIDENCE"
        market_verdicts[market] = verdict
        markets.append(
            {
                "market_code": market,
                "verdict": verdict,
                "proven_source_count": sum(
                    item == "PROVEN" for item in verdicts
                ),
                "source_count": len(source_rows),
            }
        )

    required = [market.upper() for market in required_markets]
    required_statuses = [
        market_verdicts.get(market, "INSUFFICIENT_EVIDENCE")
        for market in required
    ]
    if all(verdict == "PROVEN" for verdict in required_statuses):
        overall = "PROVEN"
    elif any(verdict == "NOT_PROVEN" for verdict in required_statuses):
        overall = "NOT_PROVEN"
    else:
        overall = "INSUFFICIENT_EVIDENCE"

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "offline_artifacts_only": True,
            "external_api_calls": False,
            "brave_requests": 0,
            "decision_influence": "PROGRESSION_GATE_ONLY",
            "workflow_success_is_not_search_proof": True,
        },
        "policy": policy.to_dict(),
        "required_markets": required,
        "overall_verdict": overall,
        "progression_gate_open": overall == "PROVEN",
        "next_stage_authorized": (
            "MEMORY_FOLLOW_UP" if overall == "PROVEN" else None
        ),
        "downstream_progression_authorized": {
            "new_memory_follow_up_work": overall == "PROVEN",
            "verification_expansion": False,
            "new_math_work": False,
            "language_logic": False,
            "probability_law": False,
        },
        "markets": markets,
        "sources": sources,
        "observation_count": len(observations),
    }
