"""Review-only learning over per-anchor Exact-Lot outcome evidence.

This layer consumes the truthful ``commercial_anchor_outcome_evidence`` emitted by
the existing unified Exa Exact-Lot checkpoint. It learns the *combination* that
worked:

    market + project domain + provider + anchor type/value + query family + route

The anchor name remains discovery context only. It never becomes qualification
evidence and this module never activates queries, providers, sources, or code.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)

SCHEMA_VERSION = "commercial-anchor-outcome-learning-1.0"
MEMORY_SCHEMA_VERSION = "commercial-anchor-outcome-memory-1.0"
MEMORY_FILENAME = "commercial-anchor-outcome-memory-v1.json"
OUTPUT_FILENAME = "commercial-anchor-outcome-learning-v1.json"

MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}
_ALLOWED_OUTCOMES = {"STRICT_EXACT_LOT_SUCCESS", "NO_NEW_STRICT_EXACT_LOT"}
_MAX_RUN_HISTORY = 90
_MAX_PATTERN_OBSERVATIONS = 90

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


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _hash_id(prefix: str, identity: str) -> str:
    digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


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


def _query_family(query: object, anchor_value: object) -> str:
    text = _text(query)
    anchor = _text(anchor_value)
    if not text:
        return ""
    if not anchor:
        return text
    return re.sub(re.escape(anchor), "{ANCHOR}", text, flags=re.IGNORECASE)


def _resolution_route_index(resolution: Mapping[str, Any]) -> dict[str, str]:
    routes: dict[str, str] = {}
    verification = _mapping(resolution.get("verification"))
    for row in _rows(verification.get("verified_pages")):
        url = _text(row.get("final_url") or row.get("url"))
        if url:
            routes[url] = "DIRECT_SEARCH_RESULT"

    multihop = _mapping(resolution.get("multihop"))
    for row in _rows(multihop.get("exact_lots")):
        url = _text(row.get("final_url") or row.get("url"))
        if url:
            routes[url] = "MULTI_HOP"
    return routes


def _validate_resolution(resolution: Mapping[str, Any]) -> None:
    schema = _text(resolution.get("schema_version"))
    if not schema.startswith("exa-exact-lot-checkpoint-resolution-"):
        raise ValueError("commercial anchor learning requires Exa Exact-Lot resolution evidence")
    if resolution.get("production_mutation") not in {None, False}:
        raise ValueError("resolution changed production_mutation safety")

    domain = _upper(resolution.get("project_domain"))
    if domain not in _ALLOWED_DOMAINS:
        raise ValueError(f"out-of-domain resolution refused: {domain or 'UNKNOWN'}")

    evidence = _mapping(resolution.get("commercial_anchor_outcome_evidence"))
    if not evidence:
        return
    if evidence.get("anchor_is_qualification_evidence") is not False:
        raise ValueError("anchor outcome evidence must keep anchor_is_qualification_evidence=False")
    if evidence.get("learning_evidence_only") is not True:
        raise ValueError("anchor outcome evidence must remain learning_evidence_only=True")
    for field in (
        "automatic_query_activation",
        "automatic_source_promotion",
        "production_query_mutation",
        "production_mutation",
    ):
        if evidence.get(field) is not False:
            raise ValueError(f"anchor outcome evidence changed safety field {field}")


def _observations_from_resolution(
    resolution: Mapping[str, Any],
    *,
    run_id: str,
    source_path: str,
) -> list[dict[str, Any]]:
    _validate_resolution(resolution)
    evidence = _mapping(resolution.get("commercial_anchor_outcome_evidence"))
    if not evidence:
        return []

    market = _upper(resolution.get("market") or evidence.get("market_code"))
    project_domain = _upper(
        resolution.get("project_domain") or evidence.get("project_domain")
    )
    provider = _text(resolution.get("provider") or evidence.get("provider")).lower()
    generated_at = _text(resolution.get("generated_at"))
    route_index = _resolution_route_index(resolution)
    output: list[dict[str, Any]] = []

    for row in _rows(evidence.get("outcomes")):
        outcome = _upper(row.get("outcome"))
        if outcome not in _ALLOWED_OUTCOMES:
            continue
        anchor_type = _upper(row.get("anchor_type"))
        anchor_value = _text(row.get("anchor_value"))
        anchor_origin = _upper(row.get("anchor_origin"))
        query = _text(row.get("query"))
        query_family = _query_family(query, anchor_value)
        urls = sorted(
            {
                _text(url)
                for url in (row.get("strict_exact_lot_urls") or [])
                if _text(url)
            }
        )

        if outcome == "STRICT_EXACT_LOT_SUCCESS":
            by_route: dict[str, list[str]] = {}
            for url in urls:
                route = route_index.get(url, "UNATTRIBUTED_ROUTE")
                by_route.setdefault(route, []).append(url)
            if not by_route:
                by_route["UNATTRIBUTED_ROUTE"] = []
        else:
            by_route = {"NO_EXACT_LOT_ROUTE": []}

        for route, route_urls in sorted(by_route.items()):
            eligible = outcome != "STRICT_EXACT_LOT_SUCCESS" or route != "UNATTRIBUTED_ROUTE"
            identity = "|".join(
                (
                    market,
                    project_domain,
                    provider,
                    anchor_type,
                    anchor_value.casefold(),
                    query_family.casefold(),
                    route,
                    outcome,
                )
            )
            output.append(
                {
                    "observation_id": _hash_id(
                        "anchor-outcome-observation",
                        f"{run_id}|{source_path}|{identity}",
                    ),
                    "run_id": run_id,
                    "checkpoint_day": _checkpoint_day(generated_at),
                    "generated_at": generated_at or None,
                    "market_code": market,
                    "project_domain": project_domain,
                    "provider": provider or None,
                    "anchor_type": anchor_type or None,
                    "anchor_value": anchor_value or None,
                    "anchor_origin": anchor_origin or None,
                    "query": query or None,
                    "query_family": query_family or None,
                    "route": route,
                    "outcome": outcome,
                    "strict_exact_lot_added_count": len(route_urls),
                    "strict_exact_lot_urls": route_urls,
                    "route_attribution_complete": route != "UNATTRIBUTED_ROUTE",
                    "eligible_for_success_learning": eligible,
                    "source_path": source_path,
                    "anchor_is_qualification_evidence": False,
                    "learning_evidence_only": True,
                    **{field: False for field in _SAFETY_FALSE_FIELDS},
                }
            )
    return output


def _pattern_key(observation: Mapping[str, Any]) -> str:
    return "|".join(
        (
            "ANCHOR_QUERY_ROUTE",
            _upper(observation.get("market_code")),
            _upper(observation.get("project_domain")),
            _text(observation.get("provider")).lower(),
            _upper(observation.get("anchor_type")),
            _text(observation.get("anchor_value")).casefold(),
            _text(observation.get("query_family")).casefold(),
            _upper(observation.get("route")),
        )
    )


def _pattern_from_observations(
    pattern_key: str,
    observations: list[Mapping[str, Any]],
) -> dict[str, Any]:
    run_ids = sorted({_text(row.get("run_id")) for row in observations if _text(row.get("run_id"))})
    days = sorted(
        {_text(row.get("checkpoint_day")) for row in observations if _text(row.get("checkpoint_day"))}
    )
    success_rows = [
        row
        for row in observations
        if _upper(row.get("outcome")) == "STRICT_EXACT_LOT_SUCCESS"
        and row.get("eligible_for_success_learning") is True
    ]
    zero_rows = [
        row
        for row in observations
        if _upper(row.get("outcome")) == "NO_NEW_STRICT_EXACT_LOT"
    ]
    urls = sorted(
        {
            _text(url)
            for row in success_rows
            for url in (row.get("strict_exact_lot_urls") or [])
            if _text(url)
        }
    )

    if success_rows:
        success_days = {
            _text(row.get("checkpoint_day"))
            for row in success_rows
            if _text(row.get("checkpoint_day"))
        }
        status = "PROVEN_SUCCESS" if len(success_days) >= 2 else "CANDIDATE_SUCCESS"
    elif zero_rows:
        zero_days = {
            _text(row.get("checkpoint_day"))
            for row in zero_rows
            if _text(row.get("checkpoint_day"))
        }
        status = "REPEATED_ZERO" if len(zero_days) >= 2 else "OBSERVED_ZERO"
    else:
        status = "UNATTRIBUTED"

    first = observations[0]
    return {
        "pattern_id": _hash_id("anchor-outcome-pattern", pattern_key),
        "pattern_key": pattern_key,
        "pattern_type": "COMMERCIAL_ANCHOR_QUERY_ROUTE_OUTCOME",
        "pattern_status": status,
        "market_code": _upper(first.get("market_code")),
        "project_domain": _upper(first.get("project_domain")),
        "provider": _text(first.get("provider")).lower() or None,
        "anchor_type": _upper(first.get("anchor_type")) or None,
        "anchor_value": _text(first.get("anchor_value")) or None,
        "anchor_origin": _upper(first.get("anchor_origin")) or None,
        "query_family": _text(first.get("query_family")) or None,
        "route": _upper(first.get("route")) or None,
        "observation_count": len(observations),
        "checkpoint_run_count": len(run_ids),
        "checkpoint_day_count": len(days),
        "checkpoint_days": days,
        "successful_observation_count": len(success_rows),
        "zero_observation_count": len(zero_rows),
        "verified_exact_lot_url_count": len(urls),
        "verified_exact_lot_urls": urls,
        "review_status": (
            "READY_FOR_HUMAN_REVIEW"
            if status == "PROVEN_SUCCESS"
            else "NO_AUTOMATIC_ACTION"
        ),
        "anchor_is_qualification_evidence": False,
        "learning_evidence_only": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }


def build_commercial_anchor_outcome_learning(
    *,
    existing_memory: Mapping[str, Any] | None,
    current_resolutions: Mapping[str, Mapping[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    run = _text(run_id)
    if not run:
        raise ValueError("run_id is required")

    prior = _mapping(existing_memory)
    if prior and _text(prior.get("schema_version")) != MEMORY_SCHEMA_VERSION:
        raise ValueError("unsupported commercial anchor outcome memory schema")
    for field in _SAFETY_FALSE_FIELDS:
        if prior and prior.get(field) is not False:
            raise ValueError(f"stored commercial anchor memory changed safety field {field}")

    observations_by_id: dict[str, dict[str, Any]] = {
        _text(row.get("observation_id")): dict(row)
        for row in _rows(prior.get("observations"))
        if _text(row.get("observation_id"))
    }
    current_observations: list[dict[str, Any]] = []
    input_status: dict[str, str] = {}

    for source_path, resolution in sorted(current_resolutions.items()):
        if not resolution:
            input_status[source_path] = "MISSING_OR_EMPTY"
            continue
        rows = _observations_from_resolution(
            resolution,
            run_id=run,
            source_path=source_path,
        )
        input_status[source_path] = "OBSERVED" if rows else "VALID_ZERO"
        current_observations.extend(rows)
        for row in rows:
            observations_by_id[row["observation_id"]] = row

    observations = sorted(
        observations_by_id.values(),
        key=lambda row: (
            _upper(row.get("market_code")),
            _text(row.get("anchor_value")).casefold(),
            _text(row.get("query_family")).casefold(),
            _upper(row.get("route")),
            _text(row.get("run_id")),
        ),
    )

    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in observations:
        key = _pattern_key(row)
        groups.setdefault(key, []).append(row)

    patterns = sorted(
        (_pattern_from_observations(key, rows) for key, rows in groups.items()),
        key=lambda row: (
            _upper(row.get("market_code")),
            _text(row.get("anchor_value")).casefold(),
            _text(row.get("query_family")).casefold(),
            _upper(row.get("route")),
        ),
    )
    proven = [row for row in patterns if row["pattern_status"] == "PROVEN_SUCCESS"]
    candidates = [row for row in patterns if row["pattern_status"] == "CANDIDATE_SUCCESS"]
    repeated_zero = [row for row in patterns if row["pattern_status"] == "REPEATED_ZERO"]

    prior_history = [
        dict(row)
        for row in _rows(prior.get("run_history"))
        if _text(row.get("run_id")) != run
    ]
    generated_candidates = [
        _text(row.get("generated_at"))
        for row in current_observations
        if _text(row.get("generated_at"))
    ]
    run_history = (
        prior_history
        + [
            {
                "run_id": run,
                "generated_at": max(generated_candidates) if generated_candidates else None,
                "current_observation_count": len(current_observations),
                "input_status": input_status,
            }
        ]
    )[-_MAX_RUN_HISTORY:]

    outcome_counts = Counter(
        _upper(row.get("outcome"))
        for row in current_observations
        if _upper(row.get("outcome"))
    )
    return {
        "schema_version": MEMORY_SCHEMA_VERSION,
        "status": "SUCCESS" if observations else "VALID_ZERO",
        "current_run_id": run,
        "run_history": run_history,
        "observation_count": len(observations),
        "current_run_observation_count": len(current_observations),
        "observations": observations[-(_MAX_PATTERN_OBSERVATIONS * max(1, len(patterns))):],
        "pattern_count": len(patterns),
        "patterns": patterns,
        "candidate_success_pattern_count": len(candidates),
        "candidate_success_pattern_ids": [row["pattern_id"] for row in candidates],
        "proven_success_pattern_count": len(proven),
        "proven_success_patterns": proven,
        "repeated_zero_pattern_count": len(repeated_zero),
        "repeated_zero_patterns": repeated_zero,
        "current_run_outcome_counts": dict(sorted(outcome_counts.items())),
        "input_status": input_status,
        "learning_contract": (
            "Commercial anchor outcome evidence -> review-only combination learning. "
            "Learning credits market + domain + provider + anchor + query family + verified route; "
            "the anchor name alone is never a success rule."
        ),
        "project_domain_gate_enforced": True,
        "anchor_is_qualification_evidence": False,
        "learning_evidence_only": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }


def _resolution_paths(input_root: Path) -> dict[str, Path]:
    return {
        market: input_root / f"{market.casefold()}-exa-exact-lot" / "exa-exact-lot-resolution.json"
        for market in MARKETS
    }


def write_commercial_anchor_outcome_learning(
    *,
    input_root: str | Path,
    output_dir: str | Path,
    run_id: str,
) -> dict[str, Any]:
    root = Path(input_root)
    output = Path(output_dir)
    memory_path = root / "learning" / MEMORY_FILENAME

    current_resolutions = {
        path.relative_to(root).as_posix(): _read_json(path)
        for path in _resolution_paths(root).values()
    }
    memory = build_commercial_anchor_outcome_learning(
        existing_memory=_read_json(memory_path),
        current_resolutions=current_resolutions,
        run_id=run_id,
    )
    _write_json(memory_path, memory)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": memory["status"],
        "current_run_id": memory["current_run_id"],
        "current_run_observation_count": memory["current_run_observation_count"],
        "current_run_outcome_counts": memory["current_run_outcome_counts"],
        "pattern_count": memory["pattern_count"],
        "candidate_success_pattern_count": memory["candidate_success_pattern_count"],
        "proven_success_pattern_count": memory["proven_success_pattern_count"],
        "proven_success_patterns": memory["proven_success_patterns"],
        "repeated_zero_pattern_count": memory["repeated_zero_pattern_count"],
        "repeated_zero_patterns": memory["repeated_zero_patterns"],
        "input_status": memory["input_status"],
        "memory_file": MEMORY_FILENAME,
        "project_domain_gate_enforced": True,
        "anchor_is_qualification_evidence": False,
        "learning_evidence_only": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }
    _write_json(output / OUTPUT_FILENAME, report)
    return report
