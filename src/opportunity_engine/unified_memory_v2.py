"""Persistent cross-run memory over Unified Learning Spine V1.

UNIFIED_MEMORY_V2 consumes only already-domain-gated evidence from the Unified
Learning Spine. It remembers evidence, search queries, repeated routes, failure
causes, and deterministic pattern state across daily checkpoints.

The layer is intentionally review-only:
- no provider/source/query activation,
- no production mutation,
- no automatic code changes,
- no commercial actions,
- no AI call.

Fixed-rule conversion is explicit. A pattern is marked converted only when an
ACTIVE entry exists in the optional fixed-rule registry.

Pattern proof is intentionally conservative. Distinct GitHub Actions run IDs
from the same UTC checkpoint day are not treated as independent Memory V2 proof.
A manual rerun minutes later may re-observe evidence, but it cannot by itself
promote a SOURCE_OUTCOME, MISS_REASON, or fallback ROUTE_SUCCESS pattern to
PROVEN. Search Success Learning's explicit replicated/independent-run evidence
remains authoritative for route proof.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)

SCHEMA_VERSION = "unified-memory-2.0"
RULE_REGISTRY_SCHEMA_VERSION = "unified-memory-rule-registry-2.0"
MEMORY_FILENAME = "unified-memory-v2.json"
SUMMARY_FILENAME = "unified-memory-v2-summary.json"
SPINE_FILENAME = "unified-learning-spine.json"
DEFAULT_RULE_REGISTRY_PATH = Path("config/learning/unified-memory-rule-registry-v2.json")

_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}
_ALLOWED_SPINE_STATUSES = {"SUCCESS", "VALID_ZERO"}
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
_MAX_RUN_HISTORY = 90
_MAX_EVIDENCE_RUN_OBSERVATIONS = 90


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _hash_id(prefix: str, identity: str) -> str:
    digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


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
    if payload.get("project_domain_gate_enforced") is not True:
        raise ValueError(f"{label} must keep project_domain_gate_enforced=True")
    for field in _SAFETY_FALSE_FIELDS:
        if payload.get(field) not in {None, False}:
            raise ValueError(f"{label} changed safety field {field}")


def _validate_spine(spine: Mapping[str, Any]) -> None:
    schema = _text(spine.get("schema_version"))
    if not schema.startswith("unified-learning-spine-1."):
        raise ValueError("Unified Memory V2 requires Unified Learning Spine V1")
    if _upper(spine.get("status")) not in _ALLOWED_SPINE_STATUSES:
        raise ValueError("Unified Learning Spine must be SUCCESS or VALID_ZERO")
    _validate_safety(spine, label="Unified Learning Spine")
    for record in _rows(spine.get("records")):
        evidence_id = _text(record.get("learning_evidence_id"))
        if not evidence_id:
            raise ValueError("learning evidence id is required")
        if _upper(record.get("project_domain")) not in _ALLOWED_DOMAINS:
            raise ValueError("Unified Memory V2 refuses out-of-domain evidence")


def _validate_existing_memory(memory: Mapping[str, Any]) -> None:
    if not memory:
        return
    if _text(memory.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported Unified Memory schema")
    if memory.get("project_domain_gate_enforced") is not True:
        raise ValueError("stored Unified Memory lost its project-domain gate")
    for field in _SAFETY_FALSE_FIELDS:
        if memory.get(field) is not False:
            raise ValueError(f"stored Unified Memory changed safety field {field}")


def _rule_index(rule_registry: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    registry = _mapping(rule_registry)
    if not registry:
        return {}
    if _text(registry.get("schema_version")) not in {"", RULE_REGISTRY_SCHEMA_VERSION}:
        raise ValueError("unsupported Unified Memory rule registry schema")
    for field in _SAFETY_FALSE_FIELDS:
        if registry.get(field) not in {None, False}:
            raise ValueError(f"rule registry changed safety field {field}")
    index: dict[str, dict[str, Any]] = {}
    for raw in _rows(registry.get("rules")):
        if _upper(raw.get("status")) != "ACTIVE":
            continue
        pattern_key = _text(raw.get("pattern_key"))
        rule_id = _text(raw.get("rule_id"))
        if not pattern_key or not rule_id:
            continue
        index[pattern_key] = {
            "rule_id": rule_id,
            "implemented_in": _text(raw.get("implemented_in")) or None,
            "status": "ACTIVE",
        }
    return index


def _run_observation(record: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "observed_at": _text(record.get("observed_at")) or None,
        "outcome": _upper(record.get("outcome")) or None,
        "miss_reason": _upper(record.get("miss_reason")) or None,
    }


def _merge_evidence_row(
    prior: Mapping[str, Any] | None,
    record: Mapping[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    old = _mapping(prior)
    observations = [
        dict(row)
        for row in _rows(old.get("run_observations"))
        if _text(row.get("run_id")) != run_id
    ]
    observations.append(_run_observation(record, run_id))
    observations = observations[-_MAX_EVIDENCE_RUN_OBSERVATIONS:]

    supporting = set(_string_list(old.get("supporting_run_ids")))
    supporting.update(_string_list(record.get("supporting_run_ids")))

    first_seen_run_id = (
        _text(old.get("first_seen_run_id"))
        or _text(observations[0].get("run_id"))
        or run_id
    )
    latest_metadata = dict(_mapping(record.get("metadata")))

    return {
        "learning_evidence_id": _text(record.get("learning_evidence_id")),
        "evidence_kind": _upper(record.get("evidence_kind")),
        "market_code": _upper(record.get("market_code")),
        "project_domain": _upper(record.get("project_domain")),
        "source_name": _text(record.get("source_name")) or None,
        "provider": _text(record.get("provider")).lower() or None,
        "query": _text(record.get("query")) or None,
        "url": _text(record.get("url")) or None,
        "result_type": _upper(record.get("result_type")) or None,
        "latest_outcome": _upper(record.get("outcome")) or None,
        "latest_miss_reason": _upper(record.get("miss_reason")) or None,
        "route": _upper(record.get("route")) or None,
        "source_identity": _text(record.get("source_identity")) or None,
        "first_seen_run_id": first_seen_run_id,
        "last_seen_run_id": run_id,
        "seen_checkpoint_run_count": len(observations),
        "run_observations": observations,
        "supporting_run_ids": sorted(supporting),
        "latest_metadata": latest_metadata,
    }


def _evidence_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _upper(row.get("market_code")),
        _upper(row.get("evidence_kind")),
        _text(row.get("source_identity")),
        _text(row.get("learning_evidence_id")),
    )


def _checkpoint_run_ids(rows: list[Mapping[str, Any]]) -> set[str]:
    run_ids: set[str] = set()
    for row in rows:
        for observation in _rows(row.get("run_observations")):
            value = _text(observation.get("run_id"))
            if value:
                run_ids.add(value)
    return run_ids


def _checkpoint_day(value: object) -> str:
    """Return a stable UTC calendar-day key from an ISO checkpoint timestamp."""
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


def _checkpoint_day_ids(
    rows: list[Mapping[str, Any]],
    *,
    run_history: list[Mapping[str, Any]],
) -> set[str]:
    """Map observed run IDs to independent checkpoint days.

    This intentionally collapses multiple GitHub Actions runs generated on the
    same UTC date. Existing Memory V2 state created before this guard is handled
    without migration because its run_history already records generated_at.
    """
    observed_run_ids = _checkpoint_run_ids(rows)
    generated_at_by_run = {
        _text(history.get("run_id")): _text(history.get("generated_at"))
        for history in run_history
        if _text(history.get("run_id"))
    }
    return {
        day
        for run_id in observed_run_ids
        if (day := _checkpoint_day(generated_at_by_run.get(run_id)))
    }


def _apply_rule_state(
    pattern: dict[str, Any],
    *,
    rules: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    rule = _mapping(rules.get(_text(pattern.get("pattern_key"))))
    converted = bool(rule)
    status = _upper(pattern.get("pattern_status"))
    if converted:
        review_status = "FIXED_RULE_ACTIVE"
        ai_still_needed = False
        ai_role = "FIXED_RULE_HANDLES_PATTERN"
    elif status == "PROVEN":
        review_status = "READY_FOR_RULE_REVIEW"
        ai_still_needed = True
        ai_role = "AI_OPTIONAL_FOR_RULE_DESIGN"
    else:
        review_status = "NOT_PROVEN"
        ai_still_needed = True
        ai_role = "AI_USEFUL_FOR_NOVEL_OR_UNPROVEN_CASE"

    pattern.update(
        {
            "converted_to_rule": converted,
            "rule_id": _text(rule.get("rule_id")) or None,
            "rule_implemented_in": _text(rule.get("implemented_in")) or None,
            "rule_review_status": review_status,
            "ai_still_needed": ai_still_needed,
            "ai_role": ai_role,
            "automatic_code_change": False,
        }
    )
    return pattern


def _route_patterns(
    evidence_rows: list[Mapping[str, Any]],
    *,
    rules: Mapping[str, Mapping[str, Any]],
    run_history: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        if _upper(row.get("evidence_kind")) != "SEARCH_ROUTE_SUCCESS":
            continue
        key = "|".join(
            (
                "ROUTE_SUCCESS",
                _upper(row.get("market_code")),
                _upper(row.get("project_domain")),
                _text(row.get("provider")).lower(),
                _upper(row.get("route")),
                _text(row.get("source_identity")).lower(),
            )
        )
        groups[key].append(row)

    patterns: list[dict[str, Any]] = []
    for pattern_key, rows in groups.items():
        checkpoint_runs = _checkpoint_run_ids(rows)
        checkpoint_days = _checkpoint_day_ids(rows, run_history=run_history)
        supporting_runs: set[str] = set()
        queries: set[str] = set()
        urls: set[str] = set()
        max_independent_runs = 0
        replicated = False
        for row in rows:
            supporting_runs.update(_string_list(row.get("supporting_run_ids")))
            query = _text(row.get("query"))
            if query:
                queries.add(query)
            url = _text(row.get("url"))
            if url:
                urls.add(url)
            metadata = _mapping(row.get("latest_metadata"))
            urls.update(_string_list(metadata.get("verified_exact_lot_urls")))
            max_independent_runs = max(
                max_independent_runs,
                _int(metadata.get("independent_run_count")),
            )
            if _upper(row.get("latest_outcome")) == "REPLICATED_FOR_REVIEW":
                replicated = True

        # Search Success Learning may already provide a stronger independent-run
        # proof. Memory V2 trusts that explicit contract. Its own fallback proof,
        # however, requires independent checkpoint days rather than raw run IDs.
        independent_run_count = max(max_independent_runs, len(checkpoint_days))
        status = "PROVEN" if replicated or independent_run_count >= 2 else "CANDIDATE"
        first = rows[0]
        pattern = {
            "pattern_id": _hash_id("memory-pattern", pattern_key),
            "pattern_key": pattern_key,
            "pattern_type": "ROUTE_SUCCESS",
            "pattern_status": status,
            "market_code": _upper(first.get("market_code")),
            "project_domain": _upper(first.get("project_domain")),
            "provider": _text(first.get("provider")).lower() or None,
            "route": _upper(first.get("route")) or None,
            "source_identity": _text(first.get("source_identity")) or None,
            "distinct_evidence_count": len(rows),
            "checkpoint_run_count": len(checkpoint_runs),
            "checkpoint_day_count": len(checkpoint_days),
            "checkpoint_days": sorted(checkpoint_days),
            "independent_run_count": independent_run_count,
            "supporting_run_ids": sorted(supporting_runs or checkpoint_runs),
            "queries": sorted(queries),
            "verified_urls": sorted(urls),
        }
        patterns.append(_apply_rule_state(pattern, rules=rules))
    return patterns


def _failure_patterns(
    evidence_rows: list[Mapping[str, Any]],
    *,
    rules: Mapping[str, Mapping[str, Any]],
    run_history: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        if _upper(row.get("evidence_kind")) != "MISSED_OPPORTUNITY":
            continue
        reason = _upper(row.get("latest_miss_reason")) or "UNDIAGNOSED"
        key = "|".join(
            (
                "MISS_REASON",
                _upper(row.get("market_code")),
                _upper(row.get("project_domain")),
                reason,
            )
        )
        groups[key].append(row)

    patterns: list[dict[str, Any]] = []
    for pattern_key, rows in groups.items():
        checkpoint_runs = _checkpoint_run_ids(rows)
        checkpoint_days = _checkpoint_day_ids(rows, run_history=run_history)
        distinct = len(rows)
        if distinct >= 2 and len(checkpoint_days) >= 2:
            status = "PROVEN"
        elif distinct >= 2 or len(checkpoint_days) >= 2:
            status = "REPEATED"
        else:
            status = "OBSERVED"
        first = rows[0]
        pattern = {
            "pattern_id": _hash_id("memory-pattern", pattern_key),
            "pattern_key": pattern_key,
            "pattern_type": "MISS_REASON",
            "pattern_status": status,
            "market_code": _upper(first.get("market_code")),
            "project_domain": _upper(first.get("project_domain")),
            "miss_reason": _upper(first.get("latest_miss_reason")) or "UNDIAGNOSED",
            "distinct_evidence_count": distinct,
            "checkpoint_run_count": len(checkpoint_runs),
            "checkpoint_day_count": len(checkpoint_days),
            "checkpoint_days": sorted(checkpoint_days),
            "case_ids": sorted(
                _text(row.get("source_identity"))
                for row in rows
                if _text(row.get("source_identity"))
            ),
        }
        patterns.append(_apply_rule_state(pattern, rules=rules))
    return patterns


def _source_patterns(
    evidence_rows: list[Mapping[str, Any]],
    *,
    rules: Mapping[str, Mapping[str, Any]],
    run_history: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        if _upper(row.get("evidence_kind")) != "MARKET_OBSERVATION":
            continue
        key = "|".join(
            (
                "SOURCE_OUTCOME",
                _upper(row.get("market_code")),
                _upper(row.get("project_domain")),
                _text(row.get("source_name")).lower(),
                _upper(row.get("result_type")),
                _upper(row.get("latest_outcome")),
            )
        )
        groups[key].append(row)

    patterns: list[dict[str, Any]] = []
    for pattern_key, rows in groups.items():
        checkpoint_runs = _checkpoint_run_ids(rows)
        checkpoint_days = _checkpoint_day_ids(rows, run_history=run_history)
        distinct = len(rows)
        if distinct >= 2 and len(checkpoint_days) >= 2:
            status = "PROVEN"
        elif distinct >= 2 or len(checkpoint_days) >= 2:
            status = "REPEATED"
        else:
            status = "OBSERVED"
        first = rows[0]
        pattern = {
            "pattern_id": _hash_id("memory-pattern", pattern_key),
            "pattern_key": pattern_key,
            "pattern_type": "SOURCE_OUTCOME",
            "pattern_status": status,
            "market_code": _upper(first.get("market_code")),
            "project_domain": _upper(first.get("project_domain")),
            "source_name": _text(first.get("source_name")) or None,
            "result_type": _upper(first.get("result_type")) or None,
            "outcome": _upper(first.get("latest_outcome")) or None,
            "distinct_evidence_count": distinct,
            "checkpoint_run_count": len(checkpoint_runs),
            "checkpoint_day_count": len(checkpoint_days),
            "checkpoint_days": sorted(checkpoint_days),
            "evidence_ids": sorted(_text(row.get("learning_evidence_id")) for row in rows),
        }
        patterns.append(_apply_rule_state(pattern, rules=rules))
    return patterns


def _query_memory(evidence_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        query = _text(row.get("query"))
        if not query:
            continue
        groups[
            (
                _upper(row.get("market_code")),
                _text(row.get("provider")).lower(),
                query,
            )
        ].append(row)

    output: list[dict[str, Any]] = []
    for (market, provider, query), rows in groups.items():
        run_ids = _checkpoint_run_ids(rows)
        routes = sorted({_upper(row.get("route")) for row in rows if _upper(row.get("route"))})
        sources = sorted(
            {
                _text(row.get("source_identity"))
                for row in rows
                if _text(row.get("source_identity"))
            }
        )
        outcomes = Counter(
            _upper(row.get("latest_outcome"))
            for row in rows
            if _upper(row.get("latest_outcome"))
        )
        output.append(
            {
                "query_id": _hash_id("memory-query", f"{market}|{provider}|{query}"),
                "market_code": market,
                "provider": provider or None,
                "query": query,
                "checkpoint_run_count": len(run_ids),
                "evidence_count": len(rows),
                "routes": routes,
                "source_identities": sources,
                "latest_outcome_counts": dict(sorted(outcomes.items())),
            }
        )
    return sorted(output, key=lambda row: (row["market_code"], row["provider"] or "", row["query"]))


def _memory_summary(memory: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": memory.get("schema_version"),
        "status": memory.get("status"),
        "current_run_id": memory.get("current_run_id"),
        "memory_source": memory.get("memory_source"),
        "memory_run_count": memory.get("memory_run_count", 0),
        "evidence_memory_count": memory.get("evidence_memory_count", 0),
        "new_evidence_count": memory.get("new_evidence_count", 0),
        "reobserved_evidence_count": memory.get("reobserved_evidence_count", 0),
        "query_memory_count": memory.get("query_memory_count", 0),
        "pattern_count": memory.get("pattern_count", 0),
        "proven_pattern_count": memory.get("proven_pattern_count", 0),
        "repeated_success_route_count": memory.get("repeated_success_route_count", 0),
        "failure_pattern_count": memory.get("failure_pattern_count", 0),
        "rule_review_candidate_count": memory.get("rule_review_candidate_count", 0),
        "fixed_rule_pattern_count": memory.get("fixed_rule_pattern_count", 0),
        "ai_still_needed_pattern_count": memory.get("ai_still_needed_pattern_count", 0),
        "project_domain_gate_enforced": True,
        "automatic_code_change": False,
        "production_mutation": False,
    }


def _build_run_history(
    prior: Mapping[str, Any],
    spine: Mapping[str, Any],
    *,
    run: str,
    current_ids: set[str],
    new_ids: list[str],
    reobserved_ids: list[str],
) -> list[dict[str, Any]]:
    run_history = [
        dict(row)
        for row in _rows(prior.get("run_history"))
        if _text(row.get("run_id")) != run
    ]
    run_history.append(
        {
            "run_id": run,
            "generated_at": _text(spine.get("generated_at")) or None,
            "spine_status": _upper(spine.get("status")),
            "current_evidence_count": len(current_ids),
            "new_evidence_count": len(new_ids),
            "reobserved_evidence_count": len(reobserved_ids),
            "market_counts": dict(_mapping(spine.get("market_counts"))),
            "domain_counts": dict(_mapping(spine.get("domain_counts"))),
            "evidence_kind_counts": dict(_mapping(spine.get("evidence_kind_counts"))),
        }
    )
    return run_history[-_MAX_RUN_HISTORY:]


def build_unified_memory_v2(
    *,
    existing_memory: Mapping[str, Any] | None,
    unified_learning_spine: Mapping[str, Any],
    run_id: str,
    rule_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge one daily spine into durable, bounded, deterministic memory."""
    run = _text(run_id)
    if not run:
        raise ValueError("run_id is required")
    spine = _mapping(unified_learning_spine)
    prior = _mapping(existing_memory)
    _validate_spine(spine)
    _validate_existing_memory(prior)
    rules = _rule_index(rule_registry)

    prior_rows = {
        _text(row.get("learning_evidence_id")): dict(row)
        for row in _rows(prior.get("evidence_memory"))
        if _text(row.get("learning_evidence_id"))
    }
    current_records_by_id: dict[str, Mapping[str, Any]] = {}
    for record in _rows(spine.get("records")):
        current_records_by_id[_text(record.get("learning_evidence_id"))] = record

    for evidence_id, record in current_records_by_id.items():
        prior_rows[evidence_id] = _merge_evidence_row(
            prior_rows.get(evidence_id),
            record,
            run_id=run,
        )

    evidence_rows = sorted(prior_rows.values(), key=_evidence_sort_key)
    current_ids = set(current_records_by_id)
    new_ids = sorted(
        evidence_id
        for evidence_id in current_ids
        if _text(prior_rows[evidence_id].get("first_seen_run_id")) == run
    )
    reobserved_ids = sorted(current_ids - set(new_ids))

    # Build run history before pattern evaluation so same-day prior/current run IDs
    # can be collapsed into one independent proof day, including existing V2 state.
    run_history = _build_run_history(
        prior,
        spine,
        run=run,
        current_ids=current_ids,
        new_ids=new_ids,
        reobserved_ids=reobserved_ids,
    )

    route_patterns = _route_patterns(evidence_rows, rules=rules, run_history=run_history)
    failure_patterns = _failure_patterns(evidence_rows, rules=rules, run_history=run_history)
    source_patterns = _source_patterns(evidence_rows, rules=rules, run_history=run_history)
    patterns = sorted(
        [*route_patterns, *failure_patterns, *source_patterns],
        key=lambda row: (
            _text(row.get("pattern_type")),
            _upper(row.get("market_code")),
            _text(row.get("pattern_key")),
        ),
    )
    queries = _query_memory(evidence_rows)

    failure_reason_counts = Counter(
        _upper(row.get("latest_miss_reason")) or "UNDIAGNOSED"
        for row in evidence_rows
        if _upper(row.get("evidence_kind")) == "MISSED_OPPORTUNITY"
    )
    latest_outcome_counts = Counter(
        _upper(row.get("latest_outcome"))
        for row in evidence_rows
        if _upper(row.get("latest_outcome"))
    )
    proven = [row for row in patterns if _upper(row.get("pattern_status")) == "PROVEN"]
    repeated_routes = [
        row
        for row in route_patterns
        if _upper(row.get("pattern_status")) == "PROVEN"
    ]
    rule_candidates = [
        row
        for row in proven
        if row.get("converted_to_rule") is not True
    ]
    fixed_rules = [row for row in patterns if row.get("converted_to_rule") is True]
    ai_needed = [row for row in patterns if row.get("ai_still_needed") is True]

    status = "SUCCESS" if evidence_rows else "VALID_ZERO"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "updated_at": _text(spine.get("generated_at")) or None,
        "current_run_id": run,
        "memory_source": "RESTORED_DAILY_MEMORY" if prior else "EMPTY_FIRST_RUN_MEMORY",
        "memory_run_count": len(run_history),
        "run_history": run_history,
        "evidence_memory_count": len(evidence_rows),
        "evidence_memory": evidence_rows,
        "current_run_evidence_count": len(current_ids),
        "new_evidence_count": len(new_ids),
        "new_evidence_ids": new_ids,
        "reobserved_evidence_count": len(reobserved_ids),
        "reobserved_evidence_ids": reobserved_ids,
        "query_memory_count": len(queries),
        "query_memory": queries,
        "pattern_count": len(patterns),
        "patterns": patterns,
        "proven_pattern_count": len(proven),
        "proven_pattern_ids": [row["pattern_id"] for row in proven],
        "repeated_success_route_count": len(repeated_routes),
        "repeated_success_routes": repeated_routes,
        "failure_pattern_count": len(failure_patterns),
        "failure_patterns": failure_patterns,
        "why_failed_counts": dict(sorted(failure_reason_counts.items())),
        "latest_outcome_counts": dict(sorted(latest_outcome_counts.items())),
        "rule_review_candidate_count": len(rule_candidates),
        "rule_review_candidate_ids": [row["pattern_id"] for row in rule_candidates],
        "fixed_rule_pattern_count": len(fixed_rules),
        "fixed_rule_pattern_ids": [row["pattern_id"] for row in fixed_rules],
        "ai_still_needed_pattern_count": len(ai_needed),
        "ai_still_needed_pattern_ids": [row["pattern_id"] for row in ai_needed],
        "memory_contract": (
            "Unified Learning Spine -> persistent Unified Memory V2 -> review. "
            "Memory records facts and repeated patterns; fixed-rule conversion remains explicit."
        ),
        "project_domain_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _attach_summary(output_dir: Path, memory: Mapping[str, Any]) -> None:
    summary = _memory_summary(memory)
    _write_json(output_dir / SUMMARY_FILENAME, summary)

    brief_path = output_dir / "domain-market-intelligence-brief.json"
    if brief_path.exists():
        brief = _read_json(brief_path)
        brief["unified_memory_v2"] = summary
        _write_json(brief_path, brief)

    phone_path = output_dir / "multi-market-phone-summary.txt"
    if phone_path.exists():
        current = phone_path.read_text(encoding="utf-8")
        marker = "UNIFIED MEMORY V2:"
        if marker in current:
            current = current.split(marker, 1)[0].rstrip() + "\n"
        text = (
            "UNIFIED MEMORY V2:\n"
            f"memory source: {memory.get('memory_source')}\n"
            f"memory runs: {memory.get('memory_run_count', 0)}\n"
            f"evidence remembered: {memory.get('evidence_memory_count', 0)}\n"
            f"new evidence: {memory.get('new_evidence_count', 0)}\n"
            f"proven patterns: {memory.get('proven_pattern_count', 0)}\n"
            f"repeated success routes: {memory.get('repeated_success_route_count', 0)}\n"
            f"fixed-rule patterns: {memory.get('fixed_rule_pattern_count', 0)}\n"
            f"AI still needed patterns: {memory.get('ai_still_needed_pattern_count', 0)}\n"
            "production mutation: disabled\n"
        )
        phone_path.write_text(current.rstrip() + "\n\n" + text, encoding="utf-8")


def write_unified_memory_v2(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    run_id: str,
    rule_registry_path: str | Path | None = DEFAULT_RULE_REGISTRY_PATH,
) -> dict[str, Any]:
    """Read current Spine + prior memory, persist Memory V2, and emit a compact summary."""
    output = Path(output_dir)
    root = Path(input_root)
    memory_path = root / "learning" / MEMORY_FILENAME
    registry_path = Path(rule_registry_path) if rule_registry_path else None

    memory = build_unified_memory_v2(
        existing_memory=_read_json(memory_path),
        unified_learning_spine=_read_json(output / SPINE_FILENAME),
        run_id=run_id,
        rule_registry=_read_json(registry_path) if registry_path and registry_path.exists() else {},
    )
    _write_json(memory_path, memory)
    _attach_summary(output, memory)
    return memory
