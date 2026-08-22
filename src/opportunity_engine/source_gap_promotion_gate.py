"""Explicit promotion gate for SOURCE_GAP adaptive follow-up.

A verified SOURCE_GAP remains shadow evidence until the exact missed-opportunity
case is explicitly PROMOTED. DISABLED rolls back its production follow-up while
preserving the durable missed-opportunity record.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from opportunity_engine.missed_opportunity_learning import MissedOpportunityCase

SCHEMA_VERSION = "source-gap-promotion-gate-1.0"
_ALLOWED_STATUSES = {"PROMOTED", "DISABLED"}


def load_source_gap_promotion_decisions(
    path: str | Path,
) -> dict[str, str]:
    """Load auditable exact-case promotion decisions; missing means none."""
    target = Path(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("source gap promotion config must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported source gap promotion gate schema")
    rows = payload.get("decisions") or []
    if not isinstance(rows, list):
        raise ValueError("source gap promotion decisions must be a list")

    decisions: dict[str, str] = {}
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"source gap promotion decision #{index + 1} must be an object"
            )
        case_id = str(raw.get("case_id") or "").strip()
        status = str(raw.get("status") or "").strip().upper()
        reason = str(raw.get("reason") or "").strip()
        approved_at = str(raw.get("approved_at") or "").strip()
        if not case_id:
            raise ValueError(
                f"source gap promotion decision #{index + 1} requires case_id"
            )
        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"source gap promotion decision #{index + 1} status must be PROMOTED or DISABLED"
            )
        if not reason or not approved_at:
            raise ValueError(
                f"source gap promotion decision #{index + 1} requires reason and approved_at"
            )
        decisions[case_id] = status
    return decisions


def select_promoted_source_gap_cases(
    cases: Sequence[MissedOpportunityCase],
    promotion_decisions: Mapping[str, str] | None,
) -> list[MissedOpportunityCase]:
    """Return only existing exact cases with a PROMOTED decision."""
    decisions = promotion_decisions or {}
    return [case for case in cases if decisions.get(case.case_id) == "PROMOTED"]
