"""Explicit promotion gate between proven shadow learning and production queries.

A learned term may be PROVEN by shadow replay without becoming active. Production
activation requires an exact, auditable PROMOTED decision. DISABLED decisions
remove the term from the active overlay while preserving shadow evidence.

For transfer-only proof, an explicit decision is necessary but not sufficient:
Production also requires repeated recovery across the minimum number of unique
independent hidden holdouts. This keeps the activation gate aligned with the
safe-learning proof contract instead of trusting a single transfer success.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.learned_query_overlay import SCHEMA_VERSION as OVERLAY_SCHEMA_VERSION
from opportunity_engine.safe_learning_proof import DEFAULT_MIN_INDEPENDENT_TRANSFER_CASES

SCHEMA_VERSION = "query-promotion-gate-1.0"
_ALLOWED_STATUSES = {"PROMOTED", "DISABLED"}


def _fold(value: object) -> str:
    return " ".join(str(value or "").casefold().split()).strip()


def _ids(value: object) -> set[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    return {
        str(item).strip()
        for item in value
        if str(item).strip()
    }


def _promotion_evidence_ready(row: Mapping[str, Any]) -> bool:
    """Return whether proven Shadow evidence is mature enough for Production.

    Direct source-case replay preserves the existing promotion contract. A term
    proven only through HOLDOUT_TRANSFER must have repeated independent transfer
    evidence before even an explicit PROMOTED decision can activate it.

    Old overlay rows are handled fail-closed: when the row is explicitly marked
    HOLDOUT_TRANSFER but predates cumulative evidence fields, recovered_case_ids
    are treated as the transfer validation identities. Stored count fields are
    never trusted without those concrete unique identities.
    """
    scope = str(row.get("evaluation_scope") or "SOURCE_CASE_REPLAY").strip().upper()
    scopes = {
        str(item).strip().upper()
        for item in (row.get("evaluation_scopes") or [])
        if str(item).strip()
    } if isinstance(row.get("evaluation_scopes"), (list, tuple, set, frozenset)) else set()
    if scope:
        scopes.add(scope)

    source_replay_ids = _ids(row.get("source_replay_case_ids"))
    transfer_validation_ids = _ids(row.get("transfer_validation_case_ids"))
    recovered_ids = _ids(row.get("recovered_case_ids"))

    if not source_replay_ids and not transfer_validation_ids:
        if scope == "HOLDOUT_TRANSFER":
            transfer_validation_ids = recovered_ids
        else:
            source_replay_ids = recovered_ids

    if source_replay_ids or "SOURCE_CASE_REPLAY" in scopes and "HOLDOUT_TRANSFER" not in scopes:
        return True

    has_transfer_evidence = bool(transfer_validation_ids) or "HOLDOUT_TRANSFER" in scopes
    if not has_transfer_evidence:
        return True

    return len(transfer_validation_ids) >= DEFAULT_MIN_INDEPENDENT_TRANSFER_CASES


def load_query_promotion_decisions(path: str | Path) -> dict[tuple[str, str], str]:
    """Load exact promotion/rollback decisions from a versioned JSON config.

    Missing config is fail-closed: no learned term is promoted.
    """
    target = Path(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("query promotion config must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported query promotion gate schema")
    rows = payload.get("decisions") or []
    if not isinstance(rows, list):
        raise ValueError("query promotion decisions must be a list")

    decisions: dict[tuple[str, str], str] = {}
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise ValueError(f"query promotion decision #{index + 1} must be an object")
        market = str(raw.get("market_code") or "").strip().upper()
        term = _fold(raw.get("term"))
        status = str(raw.get("status") or "").strip().upper()
        reason = str(raw.get("reason") or "").strip()
        approved_at = str(raw.get("approved_at") or "").strip()
        if not market or not term:
            raise ValueError(f"query promotion decision #{index + 1} requires market_code and term")
        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"query promotion decision #{index + 1} status must be PROMOTED or DISABLED"
            )
        if not reason or not approved_at:
            raise ValueError(
                f"query promotion decision #{index + 1} requires reason and approved_at"
            )
        decisions[(market, term)] = status
    return decisions


def select_promoted_query_overlay(
    shadow_overlay: Mapping[str, Any] | None,
    promotion_decisions: Mapping[tuple[str, str], str] | None,
    *,
    max_terms_per_market: int = 5,
) -> dict[str, Any]:
    """Return explicitly promoted terms whose proven Shadow evidence is eligible."""
    if max_terms_per_market < 1:
        raise ValueError("max_terms_per_market must be >= 1")
    decisions = promotion_decisions or {}
    markets = shadow_overlay.get("markets") if isinstance(shadow_overlay, Mapping) else None
    active_markets: dict[str, list[dict[str, Any]]] = {}

    if isinstance(markets, Mapping):
        for raw_market, raw_rows in sorted(markets.items()):
            market = str(raw_market or "").strip().upper()
            if not market or not isinstance(raw_rows, list):
                continue
            selected: list[dict[str, Any]] = []
            for raw in raw_rows:
                if not isinstance(raw, Mapping):
                    continue
                term = _fold(raw.get("term"))
                if not term or decisions.get((market, term)) != "PROMOTED":
                    continue
                # A config decision alone can never create a production term. The
                # term must already be present in the proven shadow overlay.
                if str(raw.get("source_verdict") or "").strip().upper() != "PROVEN":
                    continue
                # Transfer-only evidence has a second fail-closed gate: a single
                # hidden recovery cannot be promoted even by explicit config.
                if not _promotion_evidence_ready(raw):
                    continue
                row = dict(raw)
                row["term"] = term
                row["promotion_status"] = "PROMOTED"
                row["activation_source"] = "EXPLICIT_PROMOTION"
                selected.append(row)
            if selected:
                selected.sort(
                    key=lambda item: (-float(item.get("precision") or 0.0), str(item["term"]))
                )
                active_markets[market] = selected[:max_terms_per_market]

    return {
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "markets": active_markets,
        "max_terms_per_market": max_terms_per_market,
        "active_term_count": sum(len(rows) for rows in active_markets.values()),
        "automatic_query_activation": False,
        "promotion_gate_enforced": True,
        "activation_source": "EXPLICIT_PROMOTION",
        "automatic_financial_action": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
