"""Explicit promotion gate for learned PARSER_GAP rescue terms.

A parser term proven by verified missed-opportunity evidence remains shadow
knowledge until an exact, auditable PROMOTED decision exists. DISABLED removes
the term from runtime use without deleting the underlying proof.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Any

SCHEMA_VERSION = "parser-promotion-gate-1.0"
_ALLOWED_STATUSES = {"PROMOTED", "DISABLED"}
_PROVEN_STATUS = "PROVEN_BY_VERIFIED_PARSER_GAP"


def _term(value: object) -> str:
    return " ".join(str(value or "").casefold().split()).strip()


def _source(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def load_parser_promotion_decisions(
    path: str | Path,
) -> dict[tuple[str, str], str]:
    """Load explicit parser promotion/rollback decisions; missing means none."""
    target = Path(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("parser promotion config must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported parser promotion gate schema")
    rows = payload.get("decisions") or []
    if not isinstance(rows, list):
        raise ValueError("parser promotion decisions must be a list")

    decisions: dict[tuple[str, str], str] = {}
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise ValueError(f"parser promotion decision #{index + 1} must be an object")
        source = _source(raw.get("source"))
        term = _term(raw.get("term"))
        status = str(raw.get("status") or "").strip().upper()
        reason = str(raw.get("reason") or "").strip()
        approved_at = str(raw.get("approved_at") or "").strip()
        if not source or not term:
            raise ValueError(
                f"parser promotion decision #{index + 1} requires source and term"
            )
        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"parser promotion decision #{index + 1} status must be PROMOTED or DISABLED"
            )
        if not reason or not approved_at:
            raise ValueError(
                f"parser promotion decision #{index + 1} requires reason and approved_at"
            )
        decisions[(source, term)] = status
    return decisions


def select_promoted_parser_terms(
    shadow_overlay: Mapping[str, Any] | None,
    promotion_decisions: Mapping[tuple[str, str], str] | None,
    source_name: str,
) -> tuple[str, ...]:
    """Select only exact PROMOTED terms already proven in shadow evidence."""
    source = _source(source_name)
    if not source or not isinstance(shadow_overlay, Mapping):
        return ()
    sources = shadow_overlay.get("sources")
    if not isinstance(sources, Mapping):
        return ()
    rows = sources.get(source)
    if not isinstance(rows, list):
        return ()
    decisions = promotion_decisions or {}

    selected: list[str] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        term = _term(raw.get("term"))
        status = str(raw.get("status") or "").strip().upper()
        if not term or status != _PROVEN_STATUS:
            continue
        if decisions.get((source, term)) != "PROMOTED":
            continue
        selected.append(term)
    return tuple(dict.fromkeys(selected))
