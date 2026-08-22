"""Stabilize Brave signals and apply a bounded learned-query runtime overlay.

The radar report may expose query/rank diagnostics for operators, but those
values must not create a changed SQLite observation when the underlying public
page title, snippet, URL, classification, or status did not change.

A proven learned-query overlay may extend the existing radar OR groups and
classification vocabulary for one collection call. The overlay is temporary,
bounded, and restored in ``finally`` so learned runtime state cannot leak into
unrelated tests or collectors.

When the scheduled pre-checkpoint promoted-learning source already consumed a
Norway Brave request, this wrapper displaces the same number of overlapping NO
radar requests (bounded by the normal NO radar budget). The combined learned +
radar request budget therefore does not increase.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping

from opportunity_engine.cost_guard import manual_paid_brave_block_reason
from opportunity_engine.discovery import brave_market_signal_radar as _radar
from opportunity_engine.discovery.brave_market_signal_radar import (
    ProviderFactory,
    SUPPORTED_MARKETS,
    collect_manifest_brave_market_signals as _collect_raw_brave_market_signals,
)
from opportunity_engine.learned_query_overlay import (
    augment_market_query,
    learned_terms_for_market,
    load_learned_query_overlay,
)
from opportunity_engine.market_intelligence import MarketSignalType


_VOLATILE_SIGNAL_METADATA = {"query_id", "query", "source_rank"}
_VOLATILE_EVIDENCE_METADATA = {"query_id", "source_rank"}
_OVERLAY_ENV = "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH"
_DEFAULT_OVERLAY_RELATIVE_PATH = Path("learning") / "active-keyword-overlay.json"
_PRECHECKPOINT_LEARNED_REPORT = (
    Path("artifacts")
    / "multi-market-inputs"
    / "no-learned-core"
    / "search-run-report.json"
)


def stabilize_brave_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    """Return a persistence-safe Brave signal with stable semantic state."""
    payload = deepcopy(dict(signal))
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        payload["metadata"] = {
            key: deepcopy(value)
            for key, value in metadata.items()
            if key not in _VOLATILE_SIGNAL_METADATA
        }

    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        stable_evidence: list[dict[str, Any]] = []
        for raw in evidence:
            if not isinstance(raw, Mapping):
                continue
            item = deepcopy(dict(raw))
            item["captured_at"] = None
            evidence_metadata = item.get("metadata")
            if isinstance(evidence_metadata, Mapping):
                item["metadata"] = {
                    key: deepcopy(value)
                    for key, value in evidence_metadata.items()
                    if key not in _VOLATILE_EVIDENCE_METADATA
                }
            stable_evidence.append(item)
        payload["evidence"] = stable_evidence
    return payload


def _rewrite_artifact(path: Path, stable_by_id: Mapping[str, Mapping[str, Any]]) -> None:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        return

    rewritten: list[Any] = []
    for raw in payload["signals"]:
        if not isinstance(raw, Mapping):
            rewritten.append(raw)
            continue
        signal_id = str(raw.get("signal_id") or "").strip()
        rewritten.append(deepcopy(stable_by_id.get(signal_id, raw)))
    payload["signals"] = rewritten

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _term_table(signal_type: MarketSignalType) -> dict[str, tuple[str, ...]]:
    if signal_type == MarketSignalType.INSOLVENCY_OR_LIQUIDATION:
        return _radar._INSOLVENCY_TERMS
    if signal_type == MarketSignalType.WAREHOUSE_SURPLUS:
        return _radar._SURPLUS_TERMS
    if signal_type == MarketSignalType.AUCTION_EVENT:
        return _radar._AUCTION_TERMS
    return _radar._CLOSURE_TERMS


@contextmanager
def learned_radar_overlay(
    overlay: Mapping[str, Any] | None,
) -> Iterator[dict[str, dict[str, MarketSignalType]]]:
    """Temporarily apply proven learned terms to the existing radar.

    Existing query count and provider-call count are unchanged here. Learned
    terms are appended to the first OR group of each existing query and to the
    corresponding event-classification vocabulary. All mutable globals are
    restored exactly after the collection call.
    """

    original_queries = {
        market: tuple(_radar.MARKET_QUERIES[market]) for market in SUPPORTED_MARKETS
    }
    tables = (
        _radar._INSOLVENCY_TERMS,
        _radar._CLOSURE_TERMS,
        _radar._SURPLUS_TERMS,
        _radar._AUCTION_TERMS,
    )
    original_tables = [
        {market: tuple(table[market]) for market in SUPPORTED_MARKETS}
        for table in tables
    ]
    active_by_market: dict[str, dict[str, MarketSignalType]] = {}

    try:
        for market in SUPPORTED_MARKETS:
            learned = learned_terms_for_market(overlay, market)
            active_by_market[market] = learned
            if not learned:
                continue

            _radar.MARKET_QUERIES[market] = tuple(
                augment_market_query(query, list(learned))
                for query in original_queries[market]
            )
            for term, signal_type in learned.items():
                table = _term_table(signal_type)
                existing = table[market]
                if term.casefold() not in {item.casefold() for item in existing}:
                    table[market] = (*existing, term)
        yield active_by_market
    finally:
        for market, queries in original_queries.items():
            _radar.MARKET_QUERIES[market] = queries
        for table, snapshot in zip(tables, original_tables):
            for market, terms in snapshot.items():
                table[market] = terms


@contextmanager
def _displace_no_radar_queries(count: int) -> Iterator[int]:
    """Temporarily remove NO radar slots already spent by promoted Core search."""
    original = tuple(_radar.MARKET_QUERIES["NO"])
    displaced = min(max(0, int(count)), len(original))
    try:
        if displaced:
            _radar.MARKET_QUERIES["NO"] = original[displaced:]
        yield displaced
    finally:
        _radar.MARKET_QUERIES["NO"] = original


def _precheckpoint_learned_request_count(root: str | Path) -> tuple[int, Path, str | None]:
    path = Path(root) / _PRECHECKPOINT_LEARNED_REPORT
    if not path.exists():
        return 0, path, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return 0, path, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, Mapping):
        return 0, path, "PRECHECKPOINT_LEARNED_REPORT_NOT_OBJECT"
    try:
        request_count = int(payload.get("request_count") or 0)
    except (TypeError, ValueError):
        return 0, path, "PRECHECKPOINT_LEARNED_REQUEST_COUNT_INVALID"
    if request_count < 0:
        return 0, path, "PRECHECKPOINT_LEARNED_REQUEST_COUNT_INVALID"
    return request_count, path, None


def _runtime_overlay(
    root: str | Path,
    environment: Mapping[str, str] | None,
) -> tuple[dict[str, Any], Path, str | None]:
    env = environment if environment is not None else os.environ
    configured = str(env.get(_OVERLAY_ENV) or "").strip()
    path = Path(configured) if configured else Path(root) / _DEFAULT_OVERLAY_RELATIVE_PATH
    try:
        return load_learned_query_overlay(path), path, None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # A corrupt learning overlay must never take the core radar down. Fail
        # closed to the static query pack and surface the reason in diagnostics.
        return {"schema_version": "learned-query-overlay-1.0", "markets": {}}, path, (
            f"{type(exc).__name__}: {exc}"
        )


def _manual_cost_guard_report(
    *,
    observed_at,
    environment,
    queries_per_market: int,
    results_per_query: int,
    freshness: str | None,
    block_reason: str,
) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    generated_at = now.isoformat()

    sources = []
    for market_code in SUPPORTED_MARKETS:
        sources.append(
            {
                "schema_version": "brave-market-signal-radar-1.0",
                "source": "Brave Search market signal radar",
                "source_country": market_code,
                "freshness": freshness,
                "query_budget": queries_per_market,
                "results_per_query": results_per_query,
                "queries_attempted": 0,
                "queries_succeeded": 0,
                "accepted_signal_count": 0,
                "rejected_result_count": 0,
                "duplicate_result_count": 0,
                "signals": [],
                "errors": [],
                "status": "SKIPPED_COST_GUARD",
                "block_reason": block_reason,
                "automatic_contact": False,
                "automatic_bid": False,
                "automatic_purchase": False,
                "automatic_payment": False,
            }
        )

    return {
        "schema_version": "brave-market-signal-radar-1.0",
        "generated_at": generated_at,
        "retrieval_transport": "BRAVE_SEARCH",
        "market_coverage": list(SUPPORTED_MARKETS),
        "market_count": len(sources),
        "query_budget_total": len(SUPPORTED_MARKETS) * queries_per_market,
        "requests_made": 0,
        "results_per_query": results_per_query,
        "freshness": freshness,
        "status_counts": {"SKIPPED_COST_GUARD": len(sources)},
        "sources": sources,
        "signal_count": 0,
        "cost_guard": {
            "manual_workflow": True,
            "paid_brave_requests_blocked": True,
            "block_reason": block_reason,
        },
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def collect_manifest_brave_market_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at=None,
    environment=None,
    provider_factory: ProviderFactory | None = None,
    queries_per_market: int = 2,
    results_per_query: int = 10,
    freshness: str | None = "pm",
) -> dict[str, Any]:
    """Run the bounded radar with optional proven learned-query overlay."""
    block_reason = manual_paid_brave_block_reason(environment)
    if block_reason is not None:
        return _manual_cost_guard_report(
            observed_at=observed_at,
            environment=environment,
            queries_per_market=queries_per_market,
            results_per_query=results_per_query,
            freshness=freshness,
            block_reason=block_reason,
        )

    overlay, overlay_path, overlay_error = _runtime_overlay(root, environment)
    prelearned_requests, prelearned_path, prelearned_error = (
        _precheckpoint_learned_request_count(root)
    )
    baseline_radar_budget = len(SUPPORTED_MARKETS) * queries_per_market
    no_displacement_requested = min(max(0, prelearned_requests), queries_per_market)

    kwargs: dict[str, Any] = {
        "root": root,
        "observed_at": observed_at,
        "environment": environment,
        "queries_per_market": queries_per_market,
        "results_per_query": results_per_query,
        "freshness": freshness,
    }
    if provider_factory is not None:
        kwargs["provider_factory"] = provider_factory

    with learned_radar_overlay(overlay) as learned_by_market:
        with _displace_no_radar_queries(no_displacement_requested) as displaced:
            report = _collect_raw_brave_market_signals(manifest, **kwargs)

    # Raw radar metadata describes its configured per-market cap. Once one or
    # more NO slots were intentionally displaced, expose the actual bounded
    # request budget so operators can reconcile the combined spend exactly.
    if displaced:
        for source in report.get("sources") or []:
            if not isinstance(source, dict):
                continue
            attempted = source.get("queries_attempted")
            if isinstance(attempted, int) and attempted >= 0:
                source["query_budget"] = attempted
        report["query_budget_total"] = sum(
            int(source.get("query_budget") or 0)
            for source in report.get("sources") or []
            if isinstance(source, Mapping)
        )

    radar_requests = int(report.get("requests_made") or 0)
    combined_requests = prelearned_requests + radar_requests
    report["learned_query_overlay"] = {
        "path": overlay_path.as_posix(),
        "load_error": overlay_error,
        "active_term_count": sum(len(terms) for terms in learned_by_market.values()),
        "active_terms_by_market": {
            market: sorted(terms) for market, terms in learned_by_market.items() if terms
        },
        "extra_search_requests": 0,
        "query_budget_unchanged": True,
        "precheckpoint_learned_report_path": prelearned_path.as_posix(),
        "precheckpoint_learned_report_error": prelearned_error,
        "precheckpoint_learned_request_count": prelearned_requests,
        "radar_requests_displaced": displaced,
        "baseline_radar_request_budget": baseline_radar_budget,
        "radar_request_count_after_displacement": radar_requests,
        "combined_learned_plus_radar_request_count": combined_requests,
        "combined_request_budget_unchanged": combined_requests <= baseline_radar_budget,
    }

    root_path = Path(root)
    stable_by_id: dict[str, dict[str, Any]] = {}
    for source in report.get("sources") or []:
        if not isinstance(source, dict):
            continue
        market = str(source.get("source_country") or "").strip().upper()
        learned_terms = set(learned_by_market.get(market, {}))
        stable_signals: list[dict[str, Any]] = []
        for raw in source.get("signals") or []:
            if not isinstance(raw, Mapping):
                continue
            stable = stabilize_brave_signal(raw)
            metadata = stable.get("metadata")
            if isinstance(metadata, dict) and learned_terms:
                event_terms = {
                    str(term).casefold() for term in metadata.get("event_terms") or []
                }
                matched = sorted(
                    term for term in learned_terms if term.casefold() in event_terms
                )
                if matched:
                    metadata["learned_term_match"] = True
                    metadata["learned_terms"] = matched
            signal_id = str(stable.get("signal_id") or "").strip()
            if signal_id:
                stable_by_id[signal_id] = stable
            stable_signals.append(stable)
        source["signals"] = stable_signals

        artifact_path = str(source.get("artifact_path") or "").strip()
        if artifact_path:
            path = Path(artifact_path)
            if not path.is_absolute():
                path = root_path / path
            _rewrite_artifact(path, stable_by_id)

    report["stable_replay_fields_removed"] = {
        "signal_metadata": sorted(_VOLATILE_SIGNAL_METADATA),
        "evidence_metadata": sorted(_VOLATILE_EVIDENCE_METADATA),
        "evidence_captured_at": True,
    }
    return report
