"""Runtime overlay for search terms proven by missed-opportunity replay.

This module is the bridge between offline learning and live discovery.  It
accepts only keyword evaluations whose verdict is PROVEN, bounds the number of
active learned terms per market, and augments an existing OR group instead of
creating extra search requests.
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


def build_learned_query_overlay(
    evaluations: Sequence[KeywordEvaluationResult],
    *,
    max_terms_per_market: int = 5,
) -> dict[str, Any]:
    """Build a bounded activation overlay from PROVEN evaluations only."""
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
            {
                "term": item.term,
                "signal_type": infer_signal_type(item.term).value,
                "precision": item.precision,
                "recovered_case_ids": list(item.recovered_case_ids),
                "source_verdict": item.status,
            }
            for item in ranked[:max_terms_per_market]
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "markets": markets,
        "max_terms_per_market": max_terms_per_market,
        "active_term_count": sum(len(items) for items in markets.values()),
        "automatic_query_activation": True,
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
    """Insert learned terms into the first OR group without adding a request."""
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
