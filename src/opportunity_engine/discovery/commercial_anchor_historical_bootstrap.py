"""Bounded historical bootstrap for Commercial Anchor Outcome Learning V1.

The bootstrap is not a search source and does not replay network discovery. It
merges only explicitly reviewed historical observations into the existing
commercial-anchor memory before normal current-run learning rebuilds patterns.

V1 intentionally carries one corrected live observation from checkpoint #334:
Salzmann Restwaren introduced the Salzmann domain when primary queries did not,
then Multi-Hop resolved item-specific Exact-Lots. Aggregate ``/products/`` pages
later rejected by stricter category guards are not retained.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.commercial_anchor_outcome_learning import (
    MEMORY_FILENAME,
    MEMORY_SCHEMA_VERSION,
)
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)

SCHEMA_VERSION = "commercial-anchor-outcome-bootstrap-1.0"
DEFAULT_BOOTSTRAP_PATH = Path("config/learning/commercial-anchor-outcome-bootstrap-v1.json")

_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}
_ALLOWED_ROUTES = {"DIRECT_SEARCH_RESULT", "MULTI_HOP"}
_ALLOWED_OUTCOMES = {"STRICT_EXACT_LOT_SUCCESS"}

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


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON artifact {path.as_posix()}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"artifact root must be an object: {path.as_posix()}")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _validate_safety(payload: Mapping[str, Any], *, label: str) -> None:
    if payload.get("anchor_is_qualification_evidence") is not False:
        raise ValueError(f"{label} must keep anchor_is_qualification_evidence=False")
    if payload.get("learning_evidence_only") is not True:
        raise ValueError(f"{label} must keep learning_evidence_only=True")
    for field in _SAFETY_FALSE_FIELDS:
        if payload.get(field) is not False:
            raise ValueError(f"{label} changed safety field {field}")


def _validate_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    _validate_safety(row, label="historical bootstrap observation")
    if row.get("historical_corrected_evidence") is not True:
        raise ValueError("historical bootstrap observation must be corrected evidence")
    if _upper(row.get("project_domain")) not in _ALLOWED_DOMAINS:
        raise ValueError("historical bootstrap observation escaped project domain")
    if _upper(row.get("outcome")) not in _ALLOWED_OUTCOMES:
        raise ValueError("historical bootstrap observation must be a strict Exact-Lot success")
    if _upper(row.get("route")) not in _ALLOWED_ROUTES:
        raise ValueError("historical bootstrap observation requires a verified route")
    if row.get("eligible_for_success_learning") is not True:
        raise ValueError("historical bootstrap observation must explicitly allow success learning")
    if row.get("route_attribution_complete") is not True:
        raise ValueError("historical bootstrap route attribution must be complete")

    required_text = (
        "observation_id",
        "run_id",
        "checkpoint_day",
        "market_code",
        "provider",
        "anchor_type",
        "anchor_value",
        "query_family",
        "source_path",
    )
    for field in required_text:
        if not _text(row.get(field)):
            raise ValueError(f"historical bootstrap observation missing {field}")

    if "{anchor}" not in _text(row.get("query_family")).casefold():
        raise ValueError("historical bootstrap query family must normalize the anchor")

    urls = sorted({_text(url) for url in (row.get("strict_exact_lot_urls") or []) if _text(url)})
    if not urls:
        raise ValueError("historical bootstrap requires verified Exact-Lot URLs")
    if int(row.get("strict_exact_lot_added_count") or 0) != len(urls):
        raise ValueError("historical bootstrap Exact-Lot count does not match URL evidence")

    provenance = row.get("historical_evidence_provenance") or {}
    if not isinstance(provenance, Mapping):
        raise ValueError("historical bootstrap provenance must be an object")
    for field in (
        "source_run_id",
        "source_run_number",
        "source_head_sha",
        "source_artifact_id",
        "source_artifact_digest",
        "source_resolution_schema",
        "derivation",
    ):
        if not provenance.get(field):
            raise ValueError(f"historical bootstrap provenance missing {field}")

    reported = int(provenance.get("reported_anchor_added_exact_lot_count") or 0)
    retained = int(provenance.get("retained_corrected_item_specific_count") or 0)
    excluded = int(provenance.get("excluded_aggregate_category_count") or 0)
    if retained != len(urls) or reported != retained + excluded:
        raise ValueError("historical correction counts do not reconcile")

    # V1's reviewed correction deliberately excludes the aggregate/category
    # shapes that later guards rejected. Do not let them re-enter via bootstrap.
    if any("/products/" in url for url in urls):
        raise ValueError("historical bootstrap refuses aggregate /products/ URLs")
    if not all("/product/" in url for url in urls):
        raise ValueError("historical bootstrap V1 accepts item-specific /product/ URLs only")

    return dict(row)


def load_historical_anchor_bootstrap(
    path: str | Path = DEFAULT_BOOTSTRAP_PATH,
) -> list[dict[str, Any]]:
    bootstrap_path = Path(path)
    payload = _read_json(bootstrap_path)
    if not payload:
        return []
    if _text(payload.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported commercial anchor historical bootstrap schema")
    if payload.get("project_domain_gate_enforced") is not True:
        raise ValueError("historical bootstrap lost its project-domain gate")
    _validate_safety(payload, label="historical bootstrap")
    return [_validate_observation(row) for row in _rows(payload.get("observations"))]


def apply_commercial_anchor_historical_bootstrap(
    *,
    input_root: str | Path,
    bootstrap_path: str | Path = DEFAULT_BOOTSTRAP_PATH,
) -> dict[str, Any]:
    """Merge reviewed historical observations into durable memory without searching."""
    root = Path(input_root)
    path = Path(bootstrap_path)
    if not path.exists():
        return {
            "status": "SKIPPED_NO_BOOTSTRAP",
            "bootstrap_path": path.as_posix(),
            "observation_count": 0,
            "new_observation_count": 0,
            "search_requests": 0,
            **{field: False for field in _SAFETY_FALSE_FIELDS},
        }

    bootstrap_rows = load_historical_anchor_bootstrap(path)
    memory_path = root / "learning" / MEMORY_FILENAME
    memory = _read_json(memory_path)
    if memory:
        if _text(memory.get("schema_version")) != MEMORY_SCHEMA_VERSION:
            raise ValueError("unsupported commercial anchor outcome memory schema")
        for field in _SAFETY_FALSE_FIELDS:
            if memory.get(field) is not False:
                raise ValueError(f"stored commercial anchor memory changed safety field {field}")
    else:
        memory = {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "status": "VALID_ZERO",
            "run_history": [],
            "observations": [],
            "project_domain_gate_enforced": True,
            "anchor_is_qualification_evidence": False,
            "learning_evidence_only": True,
            **{field: False for field in _SAFETY_FALSE_FIELDS},
        }

    by_id = {
        _text(row.get("observation_id")): dict(row)
        for row in _rows(memory.get("observations"))
        if _text(row.get("observation_id"))
    }
    new_count = 0
    for row in bootstrap_rows:
        observation_id = _text(row.get("observation_id"))
        prior = by_id.get(observation_id)
        if prior is not None and prior != row:
            raise ValueError("historical bootstrap observation id conflicts with durable memory")
        if prior is None:
            by_id[observation_id] = row
            new_count += 1

    memory["observations"] = sorted(
        by_id.values(),
        key=lambda row: (
            _upper(row.get("market_code")),
            _text(row.get("anchor_value")).casefold(),
            _text(row.get("checkpoint_day")),
            _text(row.get("run_id")),
        ),
    )
    _write_json(memory_path, memory)
    return {
        "status": "MERGED" if new_count else "ALREADY_PRESENT",
        "bootstrap_path": path.as_posix(),
        "observation_count": len(bootstrap_rows),
        "new_observation_count": new_count,
        "source_run_ids": sorted({_text(row.get("run_id")) for row in bootstrap_rows}),
        "search_requests": 0,
        "anchor_is_qualification_evidence": False,
        "learning_evidence_only": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }
