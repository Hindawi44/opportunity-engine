"""Deterministic route-diversity portfolio over Unified Memory V2."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)

SCHEMA_VERSION = "market-route-portfolio-1.0"
OUTPUT_FILENAME = "market-route-portfolio-v1.json"
TEXT_FILENAME = "market-route-portfolio-v1.txt"
DEFAULT_CONFIG_PATH = Path("config/learning/market-route-portfolio-v1.json")

_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}
_PROOF_STATUSES = {"PROVEN", "FIXED_RULE_ACTIVE"}
_STATUS_RANK = {
    "GAP": 0,
    "TRACKED_NO_ROUTE_PROOF": 1,
    "OBSERVED_NO_ROUTE_PROOF": 2,
    "CANDIDATE": 3,
    "PROVEN": 4,
    "FIXED_RULE_ACTIVE": 5,
}
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


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON root must be an object: {path.as_posix()}")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validate_config(config: Mapping[str, Any]) -> None:
    if _text(config.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported Market Route Portfolio config schema")
    markets = [_upper(item) for item in config.get("markets") or [] if _upper(item)]
    if len(markets) != len(set(markets)) or not markets:
        raise ValueError("portfolio markets must be non-empty and unique")
    slots = _rows(config.get("route_slots"))
    slot_ids = [_upper(slot.get("slot_id")) for slot in slots]
    if len(slot_ids) != len(set(slot_ids)) or not all(slot_ids):
        raise ValueError("route slot ids must be non-empty and unique")
    for slot in slots:
        if _upper(slot.get("project_domain")) not in _ALLOWED_DOMAINS:
            raise ValueError("route slot escaped project domain")
        if _upper(slot.get("axis")) not in {"COMMERCIAL_ROUTE", "DISCOVERY_CHANNEL"}:
            raise ValueError("route slot axis is invalid")
    market_routes = _mapping(config.get("market_routes"))
    for market in markets:
        if market not in market_routes:
            raise ValueError(f"market route plan missing: {market}")
        planned = _mapping(market_routes.get(market))
        missing = [slot_id for slot_id in slot_ids if slot_id not in planned]
        if missing:
            raise ValueError(f"market {market} missing route slots: {missing}")
    if config.get("project_domain_gate_enforced") is not True:
        raise ValueError("portfolio config must enforce the project-domain gate")
    for field in _SAFETY_FALSE_FIELDS:
        if config.get(field) is not False:
            raise ValueError(f"portfolio config changed safety field {field}")


def _validate_memory(memory: Mapping[str, Any]) -> None:
    if not _text(memory.get("schema_version")).startswith("unified-memory-2."):
        raise ValueError("Market Route Portfolio V1 requires Unified Memory V2")
    if _upper(memory.get("status")) not in {"SUCCESS", "VALID_ZERO"}:
        raise ValueError("Unified Memory V2 must be successful")
    if memory.get("project_domain_gate_enforced") is not True:
        raise ValueError("Unified Memory V2 lost project-domain gate")
    for field in _SAFETY_FALSE_FIELDS:
        if memory.get(field) not in {None, False}:
            raise ValueError(f"Unified Memory V2 changed safety field {field}")


def _pattern_status(pattern: Mapping[str, Any]) -> str:
    status = _upper(pattern.get("pattern_status"))
    if status == "PROVEN" and pattern.get("converted_to_rule") is True:
        return "FIXED_RULE_ACTIVE"
    if status == "PROVEN":
        return "PROVEN"
    if status == "CANDIDATE":
        return "CANDIDATE"
    return ""


def _fabric_source_outcome_patterns(
    *,
    market: str,
    domain: str,
    slot_id: str,
    source_patterns: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Return only independently-proven verified fabric procurement outcomes.

    Unified Memory V2 already requires at least two independent checkpoint days
    plus distinct evidence before SOURCE_OUTCOME becomes PROVEN. The portfolio
    may therefore reuse that proof for the single FABRIC_PROCUREMENT route slot
    without inventing a parallel search route or hard-coding a supplier domain.
    """
    if slot_id != "FABRIC_PROCUREMENT" or domain != FABRIC_PROCUREMENT:
        return []
    return [
        row
        for row in source_patterns
        if _upper(row.get("market_code")) == market
        and _upper(row.get("project_domain")) == FABRIC_PROCUREMENT
        and _upper(row.get("result_type")) == "FABRIC_PROCUREMENT_ITEM"
        and _upper(row.get("outcome")) == "VERIFIED_COMMERCIAL_FABRIC_PAGE"
        and _pattern_status(row) in _PROOF_STATUSES
    ]


def _slot_status(
    *,
    market: str,
    domain: str,
    slot_id: str,
    plan: Mapping[str, Any],
    patterns: list[Mapping[str, Any]],
    source_patterns: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
) -> dict[str, Any]:
    pattern_keys = {
        _text(item) for item in plan.get("pattern_keys") or [] if _text(item)
    }
    matching_patterns = [
        row
        for row in patterns
        if _upper(row.get("market_code")) == market
        and _upper(row.get("project_domain")) == domain
        and _text(row.get("pattern_key")) in pattern_keys
    ]
    fabric_source_patterns = _fabric_source_outcome_patterns(
        market=market,
        domain=domain,
        slot_id=slot_id,
        source_patterns=source_patterns,
    )
    proof_patterns = [*matching_patterns, *fabric_source_patterns]
    proof_statuses = [_pattern_status(row) for row in proof_patterns]
    proof_statuses = [status for status in proof_statuses if status]
    status = (
        max(proof_statuses, key=lambda value: _STATUS_RANK[value])
        if proof_statuses
        else ""
    )

    terms = [
        _text(item).casefold()
        for item in plan.get("evidence_source_terms") or []
        if _text(item)
    ]
    evidence_matches: list[Mapping[str, Any]] = []
    if terms:
        for row in evidence:
            if (
                _upper(row.get("market_code")) != market
                or _upper(row.get("project_domain")) != domain
            ):
                continue
            haystack = " | ".join(
                (
                    _text(row.get("source_name")),
                    _text(row.get("provider")),
                    _text(row.get("source_identity")),
                )
            ).casefold()
            if any(term in haystack for term in terms):
                evidence_matches.append(row)

    tracked_targets = [
        _text(item) for item in plan.get("tracked_targets") or [] if _text(item)
    ]
    if not status:
        if evidence_matches:
            status = "OBSERVED_NO_ROUTE_PROOF"
        elif tracked_targets:
            status = "TRACKED_NO_ROUTE_PROOF"
        else:
            status = "GAP"

    return {
        "status": status,
        "tracked_targets": tracked_targets,
        "proof_pattern_count": len(proof_patterns),
        "proof_pattern_ids": sorted(
            _text(row.get("pattern_id"))
            for row in proof_patterns
            if _text(row.get("pattern_id"))
        ),
        "proof_pattern_keys": sorted(
            _text(row.get("pattern_key"))
            for row in proof_patterns
            if _text(row.get("pattern_key"))
        ),
        "fabric_source_outcome_proof_count": len(fabric_source_patterns),
        "evidence_observation_count": len(evidence_matches),
        "evidence_ids": sorted(
            _text(row.get("learning_evidence_id"))
            for row in evidence_matches
            if _text(row.get("learning_evidence_id"))
        ),
    }


def build_market_route_portfolio_v1(
    *,
    unified_memory: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a review-only portfolio that prevents single-route market closure."""
    memory = _mapping(unified_memory)
    cfg = _mapping(config)
    _validate_memory(memory)
    _validate_config(cfg)

    patterns = _rows(memory.get("patterns"))
    evidence = _rows(memory.get("evidence_memory"))
    route_patterns = [
        row for row in patterns if _upper(row.get("pattern_type")) == "ROUTE_SUCCESS"
    ]
    source_patterns = [
        row for row in patterns if _upper(row.get("pattern_type")) == "SOURCE_OUTCOME"
    ]
    slot_defs = {
        _upper(slot.get("slot_id")): dict(slot)
        for slot in _rows(cfg.get("route_slots"))
    }
    markets = [_upper(item) for item in cfg.get("markets") or [] if _upper(item)]
    plans = _mapping(cfg.get("market_routes"))
    gate = _mapping(cfg.get("completion_gate"))
    min_clothing = int(
        gate.get("minimum_proven_clothing_commercial_route_families") or 2
    )
    min_fabric = int(
        gate.get("minimum_proven_fabric_procurement_route_families") or 1
    )

    market_rows: list[dict[str, Any]] = []
    for market in markets:
        route_rows: list[dict[str, Any]] = []
        market_plan = _mapping(plans.get(market))
        matched_pattern_keys: set[str] = set()
        for slot_id, slot_def in slot_defs.items():
            domain = _upper(slot_def.get("project_domain"))
            axis = _upper(slot_def.get("axis"))
            resolved = _slot_status(
                market=market,
                domain=domain,
                slot_id=slot_id,
                plan=_mapping(market_plan.get(slot_id)),
                patterns=route_patterns,
                source_patterns=source_patterns,
                evidence=evidence,
            )
            matched_pattern_keys.update(
                key
                for key in resolved["proof_pattern_keys"]
                if key.startswith("ROUTE_SUCCESS|")
            )
            route_rows.append(
                {
                    "slot_id": slot_id,
                    "axis": axis,
                    "project_domain": domain,
                    **resolved,
                }
            )

        unclassified = [
            row
            for row in route_patterns
            if _upper(row.get("market_code")) == market
            and _text(row.get("pattern_key")) not in matched_pattern_keys
        ]
        clothing_proven = [
            row
            for row in route_rows
            if row["axis"] == "COMMERCIAL_ROUTE"
            and row["project_domain"] == CLOTHING_INVENTORY
            and row["status"] in _PROOF_STATUSES
        ]
        fabric_proven = [
            row
            for row in route_rows
            if row["axis"] == "COMMERCIAL_ROUTE"
            and row["project_domain"] == FABRIC_PROCUREMENT
            and row["status"] in _PROOF_STATUSES
        ]
        commercial_candidate_or_better = [
            row
            for row in route_rows
            if row["axis"] == "COMMERCIAL_ROUTE"
            and _STATUS_RANK[row["status"]] >= _STATUS_RANK["CANDIDATE"]
        ]
        complete = (
            len(clothing_proven) >= min_clothing
            and len(fabric_proven) >= min_fabric
            and not unclassified
        )
        if complete:
            portfolio_status = "DIVERSIFIED_ROUTE_PORTFOLIO"
        elif clothing_proven:
            portfolio_status = "SINGLE_PROVEN_CLOTHING_ROUTE"
        elif commercial_candidate_or_better:
            portfolio_status = "ROUTES_UNDER_PROOF"
        else:
            portfolio_status = "NO_PROVEN_COMMERCIAL_ROUTE"

        gaps: list[str] = []
        if len(clothing_proven) < min_clothing:
            gaps.append(f"CLOTHING_ROUTE_DIVERSITY:{len(clothing_proven)}/{min_clothing}")
        if len(fabric_proven) < min_fabric:
            gaps.append(f"FABRIC_PROCUREMENT:{len(fabric_proven)}/{min_fabric}")
        if unclassified:
            gaps.append(f"UNCLASSIFIED_ROUTE_PATTERNS:{len(unclassified)}")

        market_rows.append(
            {
                "market_code": market,
                "portfolio_status": portfolio_status,
                "route_portfolio_complete": complete,
                "must_continue_discovery": not complete,
                "single_route_dependency": len(clothing_proven) < min_clothing,
                "proven_clothing_commercial_route_family_count": len(clothing_proven),
                "proven_fabric_procurement_route_family_count": len(fabric_proven),
                "next_priority_gaps": gaps,
                "routes": route_rows,
                "unclassified_route_pattern_count": len(unclassified),
                "unclassified_route_patterns": [
                    {
                        "pattern_id": _text(row.get("pattern_id")) or None,
                        "pattern_key": _text(row.get("pattern_key")) or None,
                        "pattern_status": _upper(row.get("pattern_status")) or None,
                    }
                    for row in unclassified
                ],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "generated_from_memory_run_id": _text(memory.get("current_run_id")) or None,
        "generated_from_memory_run_count": int(memory.get("memory_run_count") or 0),
        "market_count": len(market_rows),
        "market_route_complete_count": sum(
            1 for row in market_rows if row["route_portfolio_complete"]
        ),
        "market_must_continue_discovery_count": sum(
            1 for row in market_rows if row["must_continue_discovery"]
        ),
        "completion_gate": {
            "minimum_proven_clothing_commercial_route_families": min_clothing,
            "minimum_proven_fabric_procurement_route_families": min_fabric,
            "unclassified_route_patterns_must_be_zero": True,
        },
        "markets": market_rows,
        "portfolio_contract": (
            "A proven or fixed route solves only that exact route. It never closes a market. "
            "Market route completion requires diversified proven clothing routes plus a proven "
            "fabric-procurement route; discovery must continue while that gate is unmet."
        ),
        "project_domain_gate_enforced": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }


def render_market_route_portfolio_v1(portfolio: Mapping[str, Any]) -> str:
    gate = _mapping(portfolio.get("completion_gate"))
    min_clothing = int(
        gate.get("minimum_proven_clothing_commercial_route_families") or 2
    )
    min_fabric = int(
        gate.get("minimum_proven_fabric_procurement_route_families") or 1
    )
    lines = [
        "MARKET ROUTE PORTFOLIO V1",
        (
            "Guard: market route completion requires "
            f">={min_clothing} proven clothing commercial route families + "
            f">={min_fabric} proven fabric-procurement route."
        ),
        "",
    ]
    for market in _rows(portfolio.get("markets")):
        lines.append(
            f"{_upper(market.get('market_code'))}: "
            f"{_upper(market.get('portfolio_status'))} | "
            f"clothing={int(market.get('proven_clothing_commercial_route_family_count') or 0)}/{min_clothing} | "
            f"fabric={int(market.get('proven_fabric_procurement_route_family_count') or 0)}/{min_fabric} | "
            f"continue_discovery={str(bool(market.get('must_continue_discovery'))).lower()}"
        )
        for route in _rows(market.get("routes")):
            lines.append(
                f"  - {_upper(route.get('slot_id'))}: {_upper(route.get('status'))}"
            )
    lines.extend(
        [
            "",
            "A fixed rule handles one exact solved route only; it does not stop discovery.",
            "No automatic query/provider/source activation or commercial action is allowed.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_market_route_portfolio_v1(
    output_dir: str | Path,
    *,
    unified_memory: Mapping[str, Any],
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    output = Path(output_dir)
    portfolio = build_market_route_portfolio_v1(
        unified_memory=unified_memory,
        config=_read_json(Path(config_path)),
    )
    _write_json(output / OUTPUT_FILENAME, portfolio)
    (output / TEXT_FILENAME).write_text(
        render_market_route_portfolio_v1(portfolio),
        encoding="utf-8",
    )
    return portfolio
