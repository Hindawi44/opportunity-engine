"""Overlay helpers for learned query terms.

A PROVEN evaluation is shadow evidence, not a production authorization. These
helpers retain and rank proven terms but mark automatic activation false. The
explicit promotion gate is responsible for selecting production-active terms.

Shadow evidence is cumulative: independent holdout recoveries for the same term
must survive later runs instead of being replaced by whichever run had the best
precision score.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.market_intelligence import MarketSignalType

SCHEMA_VERSION = "learned-query-overlay-1.0"


def infer_signal_type(term: str) -> MarketSignalType:
    folded = " ".join(str(term or "").casefold().split())
    if any(fragment in folded for fragment in ("konkurs", "insolv", "liquid")):
        return MarketSignalType.INSOLVENCY_OR_LIQUIDATION
    if any(
        fragment in folded
        for fragment in (
            "lager",
            "stock",
            "restpost",
            "warehouse",
            "surplus",
        )
    ):
        return MarketSignalType.WAREHOUSE_SURPLUS
    if any(fragment in folded for fragment in ("auktion", "auction", "versteiger")):
        return MarketSignalType.AUCTION_EVENT
    return MarketSignalType.BUSINESS_CLOSURE


def _string_ids(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return sorted(
        {
            str(item).strip()
            for item in value
            if str(item).strip()
        }
    )


def _normalized_row(raw: Mapping[str, Any], term: str) -> dict[str, Any]:
    """Normalize old/new overlay rows into cumulative evidence fields."""
    row = dict(raw)
    row["term"] = term
    row["signal_type"] = str(row.get("signal_type") or infer_signal_type(term).value)
    row["precision"] = float(row.get("precision") or 0.0)
    row["source_verdict"] = str(row.get("source_verdict") or "PROVEN")

    scope = str(row.get("evaluation_scope") or "SOURCE_CASE_REPLAY").strip().upper()
    recovered = _string_ids(row.get("recovered_case_ids"))
    source_replay = _string_ids(row.get("source_replay_case_ids"))
    transfer_validation = _string_ids(row.get("transfer_validation_case_ids"))

    # Backward compatibility for rows written before cumulative evidence fields.
    if not source_replay and not transfer_validation:
        if scope == "HOLDOUT_TRANSFER":
            transfer_validation = list(recovered)
        else:
            source_replay = list(recovered)

    scopes = _string_ids(row.get("evaluation_scopes"))
    if scope and scope not in scopes:
        scopes.append(scope)
        scopes.sort()

    row["recovered_case_ids"] = sorted(
        set(recovered) | set(source_replay) | set(transfer_validation)
    )
    row["source_replay_case_ids"] = source_replay
    row["transfer_validation_case_ids"] = transfer_validation
    row["support_case_ids"] = _string_ids(row.get("support_case_ids"))
    row["evaluation_scope"] = scope
    row["evaluation_scopes"] = scopes
    row["independent_transfer_case_count"] = len(transfer_validation)
    return row


def _row_from_evaluation(item: KeywordEvaluationResult) -> dict[str, Any]:
    scope = str(item.evaluation_scope or "SOURCE_CASE_REPLAY").strip().upper()
    recovered = sorted(set(item.recovered_case_ids))
    source_replay = recovered if scope != "HOLDOUT_TRANSFER" else []
    transfer_validation = recovered if scope == "HOLDOUT_TRANSFER" else []
    return {
        "term": item.term,
        "signal_type": infer_signal_type(item.term).value,
        "precision": item.precision,
        "raw_hit_count": item.raw_hit_count,
        "verified_relevant_count": item.verified_relevant_count,
        "recovered_case_ids": recovered,
        "source_replay_case_ids": source_replay,
        "transfer_validation_case_ids": transfer_validation,
        "support_case_ids": sorted(set(item.support_case_ids)),
        "evaluation_scope": scope,
        "evaluation_scopes": [scope],
        "independent_transfer_case_count": len(transfer_validation),
        "source_verdict": item.status,
    }


def build_learned_query_overlay(
    evaluations: Sequence[KeywordEvaluationResult],
    *,
    max_terms_per_market: int = 5,
) -> dict[str, Any]:
    """Build a bounded shadow overlay from PROVEN evaluations only."""
    if max_terms_per_market < 1:
        raise ValueError("max_terms_per_market must be >= 1")

    by_market: dict[str, list[KeywordEvaluationResult]] = defaultdict(list)
    for item in evaluations:
        if item.status != "PROVEN":
            continue
        by_market[item.market_code.upper()].append(item)

    markets: dict[str, list[dict[str, Any]]] = {}
    for market_code, rows in sorted(by_market.items()):
        ranked = sorted(rows, key=lambda item: (-item.precision, item.term))
        markets[market_code] = [
            _row_from_evaluation(item)
            for item in ranked[:max_terms_per_market]
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "markets": markets,
        "max_terms_per_market": max_terms_per_market,
        "active_term_count": sum(len(items) for items in markets.values()),
        "automatic_query_activation": False,
        "automatic_financial_action": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def merge_learned_query_overlays(
    existing: Mapping[str, Any] | None,
    learned: Mapping[str, Any] | None,
    *,
    max_terms_per_market: int = 5,
) -> dict[str, Any]:
    """Merge proven shadow learning without forgetting independent evidence.

    Ranking metrics still come from the strongest-precision observation to
    preserve previous behavior. Evidence identity is cumulative: source replay
    IDs, hidden transfer IDs, support IDs, and evaluation scopes are unioned.
    Re-observing the same holdout therefore cannot impersonate independent
    replication.
    """
    if max_terms_per_market < 1:
        raise ValueError("max_terms_per_market must be >= 1")

    by_market: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for overlay in (existing, learned):
        if not isinstance(overlay, Mapping):
            continue
        markets = overlay.get("markets")
        if not isinstance(markets, Mapping):
            continue
        for raw_market, raw_rows in markets.items():
            market = str(raw_market or "").strip().upper()
            if not market or not isinstance(raw_rows, list):
                continue
            for raw in raw_rows:
                if not isinstance(raw, Mapping):
                    continue
                term = " ".join(str(raw.get("term") or "").casefold().split()).strip()
                if not term:
                    continue
                row = _normalized_row(raw, term)
                current = by_market[market].get(term)
                if current is None:
                    by_market[market][term] = row
                    continue

                current = _normalized_row(current, term)
                stronger = (
                    row
                    if float(row.get("precision") or 0.0)
                    > float(current.get("precision") or 0.0)
                    else current
                )
                merged = dict(stronger)
                merged["recovered_case_ids"] = sorted(
                    set(current.get("recovered_case_ids") or [])
                    | set(row.get("recovered_case_ids") or [])
                )
                merged["source_replay_case_ids"] = sorted(
                    set(current.get("source_replay_case_ids") or [])
                    | set(row.get("source_replay_case_ids") or [])
                )
                merged["transfer_validation_case_ids"] = sorted(
                    set(current.get("transfer_validation_case_ids") or [])
                    | set(row.get("transfer_validation_case_ids") or [])
                )
                merged["support_case_ids"] = sorted(
                    set(current.get("support_case_ids") or [])
                    | set(row.get("support_case_ids") or [])
                )
                merged["evaluation_scopes"] = sorted(
                    set(current.get("evaluation_scopes") or [])
                    | set(row.get("evaluation_scopes") or [])
                )
                merged["independent_transfer_case_count"] = len(
                    merged["transfer_validation_case_ids"]
                )
                by_market[market][term] = merged

    markets: dict[str, list[dict[str, Any]]] = {}
    for market, rows_by_term in sorted(by_market.items()):
        rows = sorted(
            rows_by_term.values(),
            key=lambda item: (-float(item.get("precision") or 0.0), str(item["term"])),
        )[:max_terms_per_market]
        markets[market] = rows

    return {
        "schema_version": SCHEMA_VERSION,
        "markets": markets,
        "max_terms_per_market": max_terms_per_market,
        "active_term_count": sum(len(rows) for rows in markets.values()),
        "automatic_query_activation": False,
        "automatic_financial_action": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def save_learned_query_overlay(path: str | Path, overlay: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(overlay)
    payload["schema_version"] = SCHEMA_VERSION
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def load_learned_query_overlay(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return build_learned_query_overlay([])
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("learned query overlay must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported learned query overlay schema")
    markets = payload.get("markets")
    if not isinstance(markets, Mapping):
        raise ValueError("learned query overlay markets must be an object")
    return dict(payload)


def learned_terms_for_market(
    overlay: Mapping[str, Any] | None,
    market_code: str,
) -> dict[str, MarketSignalType]:
    if not isinstance(overlay, Mapping):
        return {}
    markets = overlay.get("markets")
    if not isinstance(markets, Mapping):
        return {}
    rows = markets.get(market_code.upper())
    if not isinstance(rows, list):
        return {}

    terms: dict[str, MarketSignalType] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        term = " ".join(str(row.get("term") or "").casefold().split()).strip()
        if not term:
            continue
        raw_type = str(row.get("signal_type") or "").strip()
        try:
            signal_type = MarketSignalType(raw_type)
        except ValueError:
            signal_type = infer_signal_type(term)
        terms[term] = signal_type
    return terms


def augment_market_query(query: Any, terms: Sequence[str]) -> Any:
    """Insert explicitly selected terms into the first OR group without adding a request."""
    cleaned = sorted(
        {
            " ".join(str(term or "").casefold().split()).strip()
            for term in terms
            if str(term or "").strip()
        }
    )
    if not cleaned:
        return query

    raw_query = str(query.query)
    close = raw_query.find(")")
    if close < 0:
        return query
    additions = "".join(f' OR "{term.replace(chr(34), "")}"' for term in cleaned)
    augmented = raw_query[:close] + additions + raw_query[close:]
    return type(query)(query.query_id, augmented)
