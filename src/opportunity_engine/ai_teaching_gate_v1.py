"""Route work between fixed rules, deterministic proof, and manual AI teaching.

This layer implements one governing principle:

    AI teaches only what the project has not already learned.

It consumes Unified Memory V2 plus Market Route Portfolio V1. It never calls an
AI model, never activates a provider/query/source, and never performs a
commercial action. The output is a review queue that can later be supplied to
the existing MIND FORGE paid/manual runtime.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)


SCHEMA_VERSION = "ai-teaching-gate-1.0"
OUTPUT_FILENAME = "ai-teaching-queue-v1.json"
TEXT_FILENAME = "ai-teaching-queue-v1.txt"

_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}
_PROVEN_STATUSES = {"PROVEN", "FIXED_RULE_ACTIVE"}
_SAFETY_FALSE_FIELDS = (
    "automatic_ai_invocation",
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


def _task_id(prefix: str, identity: str) -> str:
    digest = sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


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


def _validate_safety(payload: Mapping[str, Any], *, label: str) -> None:
    if payload.get("project_domain_gate_enforced") is not True:
        raise ValueError(f"{label} lost project-domain gate")
    for field in _SAFETY_FALSE_FIELDS:
        if field == "automatic_ai_invocation":
            # Upstream layers predate this field and may omit it.
            if payload.get(field) not in {None, False}:
                raise ValueError(f"{label} changed safety field {field}")
        elif payload.get(field) not in {None, False}:
            raise ValueError(f"{label} changed safety field {field}")


def _validate_inputs(memory: Mapping[str, Any], portfolio: Mapping[str, Any]) -> None:
    if not _text(memory.get("schema_version")).startswith("unified-memory-2."):
        raise ValueError("AI Teaching Gate V1 requires Unified Memory V2")
    if _upper(memory.get("status")) not in {"SUCCESS", "VALID_ZERO"}:
        raise ValueError("Unified Memory V2 must be successful")
    _validate_safety(memory, label="Unified Memory V2")

    if not _text(portfolio.get("schema_version")).startswith("market-route-portfolio-1."):
        raise ValueError("AI Teaching Gate V1 requires Market Route Portfolio V1")
    if _upper(portfolio.get("status")) != "SUCCESS":
        raise ValueError("Market Route Portfolio V1 must be successful")
    _validate_safety(portfolio, label="Market Route Portfolio V1")

    memory_run = _text(memory.get("current_run_id"))
    portfolio_run = _text(portfolio.get("generated_from_memory_run_id"))
    if memory_run and portfolio_run and memory_run != portfolio_run:
        raise ValueError("memory and route portfolio must come from the same checkpoint run")


def _is_safely_learned(pattern: Mapping[str, Any]) -> bool:
    """Return true only for a genuinely proven, explicitly active fixed rule.

    This is deliberately stricter than trusting converted_to_rule alone. If an
    old or malformed memory row ever marks an unproven pattern as converted, the
    gate fails toward AI/review rather than incorrectly bypassing intelligence.
    """
    return (
        _upper(pattern.get("pattern_status")) == "PROVEN"
        and pattern.get("converted_to_rule") is True
        and _upper(pattern.get("rule_review_status")) == "FIXED_RULE_ACTIVE"
        and pattern.get("ai_still_needed") is False
        and bool(_text(pattern.get("rule_id")))
    )


def _pattern_context(pattern: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pattern_id": _text(pattern.get("pattern_id")) or None,
        "pattern_key": _text(pattern.get("pattern_key")) or None,
        "pattern_type": _upper(pattern.get("pattern_type")) or None,
        "pattern_status": _upper(pattern.get("pattern_status")) or None,
        "market_code": _upper(pattern.get("market_code")) or None,
        "project_domain": _upper(pattern.get("project_domain")) or None,
        "provider": _text(pattern.get("provider")) or None,
        "route": _upper(pattern.get("route")) or None,
        "source_identity": _text(pattern.get("source_identity")) or None,
        "rule_id": _text(pattern.get("rule_id")) or None,
    }


def _deterministic_pattern_task(pattern: Mapping[str, Any]) -> dict[str, Any]:
    context = _pattern_context(pattern)
    identity = _text(pattern.get("pattern_key")) or _text(pattern.get("pattern_id"))
    return {
        "task_id": _task_id("det-proof", identity),
        "execution_mode": "DETERMINISTIC_PROOF",
        "task_kind": "REOBSERVE_KNOWN_ROUTE",
        "priority": 50,
        "requires_paid_ai": False,
        "reason": (
            "The route is already known. It needs independent re-observation/proof, "
            "not another AI reasoning pass."
        ),
        "context": context,
    }


def _pattern_teaching_kind(pattern: Mapping[str, Any]) -> tuple[str, int, str]:
    pattern_type = _upper(pattern.get("pattern_type"))
    status = _upper(pattern.get("pattern_status"))

    if pattern.get("converted_to_rule") is True and status != "PROVEN":
        return (
            "RULE_MAPPING_BLOCKED_UNPROVEN",
            100,
            "An unproven pattern carries a rule mapping; keep AI/review active and do not bypass it.",
        )
    if status == "PROVEN":
        return (
            "RULE_DESIGN_REVIEW",
            45,
            "The pattern is proven but has no safely active fixed rule yet.",
        )
    if pattern_type == "MISS_REASON":
        return (
            "FAILURE_DIAGNOSIS",
            82,
            "Teach the project why this discovery path fails and what reusable correction should be tested.",
        )
    if pattern_type == "SOURCE_OUTCOME":
        return (
            "SOURCE_BEHAVIOR_LEARNING",
            72,
            "Teach the project what this source outcome means and whether a reusable source rule is justified.",
        )
    return (
        "NOVEL_OR_UNPROVEN_PATTERN",
        75,
        "The pattern is not safely learned and still needs novel analysis or evidence design.",
    )


def _ai_pattern_task(pattern: Mapping[str, Any]) -> dict[str, Any]:
    kind, priority, reason = _pattern_teaching_kind(pattern)
    context = _pattern_context(pattern)
    identity = _text(pattern.get("pattern_key")) or _text(pattern.get("pattern_id"))
    market = _upper(pattern.get("market_code")) or "UNKNOWN"
    domain = _upper(pattern.get("project_domain")) or "UNKNOWN"
    return {
        "task_id": _task_id("ai-pattern", f"{kind}|{identity}"),
        "execution_mode": "AI_TEACHING",
        "task_kind": kind,
        "priority": priority,
        "requires_paid_ai": True,
        "reason": reason,
        "mind_forge_seed": (
            f"Teach opportunity-engine a reusable discovery lesson for {market} / {domain}. "
            f"Analyze only the unresolved pattern {identity}. Preserve verified facts, identify "
            "what is genuinely new, propose the smallest evidence test, and do not revisit any "
            "already-fixed rule."
        ),
        "context": context,
    }


def _portfolio_task(market: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any] | None:
    market_code = _upper(market.get("market_code"))
    slot_id = _upper(route.get("slot_id"))
    axis = _upper(route.get("axis"))
    domain = _upper(route.get("project_domain"))
    status = _upper(route.get("status"))

    if domain not in _ALLOWED_DOMAINS:
        raise ValueError(f"portfolio route escaped project domain: {market_code}/{slot_id}")
    if status in _PROVEN_STATUSES:
        return None

    context = {
        "market_code": market_code,
        "slot_id": slot_id,
        "axis": axis,
        "project_domain": domain,
        "route_status": status,
        "tracked_targets": [
            _text(item) for item in route.get("tracked_targets") or [] if _text(item)
        ],
        "evidence_observation_count": int(route.get("evidence_observation_count") or 0),
        "proof_pattern_ids": [
            _text(item) for item in route.get("proof_pattern_ids") or [] if _text(item)
        ],
    }
    identity = f"{market_code}|{domain}|{slot_id}|{status}"

    if status == "CANDIDATE":
        return {
            "task_id": _task_id("det-slot", identity),
            "execution_mode": "DETERMINISTIC_PROOF",
            "task_kind": "REOBSERVE_CANDIDATE_ROUTE_SLOT",
            "priority": 48,
            "requires_paid_ai": False,
            "reason": "A candidate route exists; repeat the existing proof path before spending AI.",
            "context": context,
        }

    if slot_id == "FABRIC_PROCUREMENT":
        priority = 100 if status == "GAP" else 92
    elif axis == "COMMERCIAL_ROUTE":
        priority = 90 if status == "GAP" else 80
    else:
        priority = 68 if status == "GAP" else 62

    if status == "GAP":
        kind = "DISCOVER_NEW_ROUTE"
        reason = "No route is currently known for this market/slot; this is genuinely novel work."
    elif status == "TRACKED_NO_ROUTE_PROOF":
        kind = "TURN_TRACKED_TARGET_INTO_ROUTE"
        reason = "Targets are known, but no successful route proof exists yet."
    elif status == "OBSERVED_NO_ROUTE_PROOF":
        kind = "RESOLVE_OBSERVATION_TO_ROUTE"
        reason = "Evidence exists, but the project has not learned a repeatable successful route."
    else:
        kind = "RESOLVE_ROUTE_GAP"
        reason = "The route slot remains unresolved and is not safely learned."

    tracked = ", ".join(context["tracked_targets"]) or "none"
    return {
        "task_id": _task_id("ai-slot", identity),
        "execution_mode": "AI_TEACHING",
        "task_kind": kind,
        "priority": priority,
        "requires_paid_ai": True,
        "reason": reason,
        "mind_forge_seed": (
            f"Improve discovery intelligence for {market_code} / {domain} / {slot_id}. "
            f"Current route status: {status}. Tracked targets: {tracked}. Generate alternative "
            "search/discovery mechanisms, challenge dependence on one source, and define low-cost "
            "evidence tests. Stay strictly inside CLOTHING_INVENTORY or FABRIC_PROCUREMENT and do "
            "not make a buy/contact decision."
        ),
        "context": context,
    }


def _dedupe_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for task in sorted(
        tasks,
        key=lambda row: (
            -int(row.get("priority") or 0),
            _text(row.get("task_kind")),
            _text(row.get("task_id")),
        ),
    ):
        task_id = _text(task.get("task_id"))
        if not task_id or task_id in seen:
            continue
        seen.add(task_id)
        output.append(task)
    return output


def build_ai_teaching_gate_v1(
    *,
    unified_memory: Mapping[str, Any],
    market_route_portfolio: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the non-spending gate that decides where AI is still useful."""
    memory = _mapping(unified_memory)
    portfolio = _mapping(market_route_portfolio)
    _validate_inputs(memory, portfolio)

    learned_patterns: list[dict[str, Any]] = []
    deterministic_tasks: list[dict[str, Any]] = []
    ai_tasks: list[dict[str, Any]] = []

    for pattern in _rows(memory.get("patterns")):
        domain = _upper(pattern.get("project_domain"))
        if domain not in _ALLOWED_DOMAINS:
            raise ValueError("memory pattern escaped project domain")

        if _is_safely_learned(pattern):
            learned_patterns.append(_pattern_context(pattern))
            continue

        if (
            _upper(pattern.get("pattern_type")) == "ROUTE_SUCCESS"
            and _upper(pattern.get("pattern_status")) == "CANDIDATE"
            and pattern.get("converted_to_rule") is not True
        ):
            deterministic_tasks.append(_deterministic_pattern_task(pattern))
            continue

        if pattern.get("ai_still_needed") is True or pattern.get("converted_to_rule") is True:
            ai_tasks.append(_ai_pattern_task(pattern))

    for market in _rows(portfolio.get("markets")):
        if market.get("must_continue_discovery") is not True:
            continue
        for route in _rows(market.get("routes")):
            task = _portfolio_task(market, route)
            if task is None:
                continue
            if task["execution_mode"] == "DETERMINISTIC_PROOF":
                deterministic_tasks.append(task)
            else:
                ai_tasks.append(task)

        for unresolved in _rows(market.get("unclassified_route_patterns")):
            pattern_key = _text(unresolved.get("pattern_key"))
            identity = f"{_upper(market.get('market_code'))}|{pattern_key}"
            ai_tasks.append(
                {
                    "task_id": _task_id("ai-unclassified", identity),
                    "execution_mode": "AI_TEACHING",
                    "task_kind": "CLASSIFY_NEW_ROUTE_PATTERN",
                    "priority": 96,
                    "requires_paid_ai": True,
                    "reason": "A newly learned route does not fit the current route portfolio taxonomy.",
                    "mind_forge_seed": (
                        "Classify this new successful route into the discovery architecture without "
                        "discarding it or allowing it to close the whole market. Determine whether an "
                        "existing slot fits or whether a reviewed new route family is needed."
                    ),
                    "context": {
                        "market_code": _upper(market.get("market_code")),
                        "pattern_id": _text(unresolved.get("pattern_id")) or None,
                        "pattern_key": pattern_key or None,
                        "pattern_status": _upper(unresolved.get("pattern_status")) or None,
                    },
                }
            )

    deterministic_tasks = _dedupe_tasks(deterministic_tasks)
    ai_tasks = _dedupe_tasks(ai_tasks)
    learned_patterns = sorted(
        learned_patterns,
        key=lambda row: (_text(row.get("market_code")), _text(row.get("pattern_key"))),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "generated_from_memory_run_id": _text(memory.get("current_run_id")) or None,
        "generated_from_memory_run_count": int(memory.get("memory_run_count") or 0),
        "governing_principle": (
            "Do not add AI to work the project already learned. AI teaches novel or unresolved "
            "work; proven reviewed knowledge is handled by fixed rules."
        ),
        "safely_learned_pattern_count": len(learned_patterns),
        "safely_learned_patterns": learned_patterns,
        "deterministic_proof_task_count": len(deterministic_tasks),
        "deterministic_proof_tasks": deterministic_tasks,
        "ai_teaching_task_count": len(ai_tasks),
        "ai_teaching_tasks": ai_tasks,
        "next_manual_ai_task_id": ai_tasks[0]["task_id"] if ai_tasks else None,
        "mind_forge_contract": {
            "existing_runtime_reused": True,
            "runtime_reference": "mind-forge-live/phase1/live_model_adapter_v1.py",
            "existing_cross_run_learning_reused": True,
            "learning_reference": "scripts/mind_forge_v2_fast_learning_memory.py",
            "manual_paid_run_required": True,
            "automatic_ai_invocation": False,
            "budget_policy_is_not_duplicated_here": True,
        },
        "project_domain_gate_enforced": True,
        **{field: False for field in _SAFETY_FALSE_FIELDS},
    }


def render_ai_teaching_gate_v1(report: Mapping[str, Any]) -> str:
    lines = [
        "AI TEACHING GATE V1",
        "AI teaches only novel/unresolved work; fixed rules handle learned work.",
        "",
        f"learned_fixed_patterns={int(report.get('safely_learned_pattern_count') or 0)}",
        f"deterministic_proof_tasks={int(report.get('deterministic_proof_task_count') or 0)}",
        f"ai_teaching_tasks={int(report.get('ai_teaching_task_count') or 0)}",
        f"next_manual_ai_task_id={_text(report.get('next_manual_ai_task_id')) or 'NONE'}",
        "",
        "Top AI teaching tasks:",
    ]
    for task in _rows(report.get("ai_teaching_tasks"))[:10]:
        context = _mapping(task.get("context"))
        lines.append(
            f"- p{int(task.get('priority') or 0):03d} {_text(task.get('task_id'))} "
            f"{_upper(task.get('task_kind'))} "
            f"{_upper(context.get('market_code'))}/{_upper(context.get('project_domain')) or _upper(context.get('slot_id'))}"
        )
    lines.extend(
        [
            "",
            "No AI/API call is made by this gate.",
            "Paid MIND FORGE execution remains manual and continues to use its existing budget gate.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_ai_teaching_gate_v1(
    output_dir: str | Path,
    *,
    unified_memory: Mapping[str, Any],
    market_route_portfolio: Mapping[str, Any],
) -> dict[str, Any]:
    output = Path(output_dir)
    report = build_ai_teaching_gate_v1(
        unified_memory=unified_memory,
        market_route_portfolio=market_route_portfolio,
    )
    _write_json(output / OUTPUT_FILENAME, report)
    output.mkdir(parents=True, exist_ok=True)
    (output / TEXT_FILENAME).write_text(
        render_ai_teaching_gate_v1(report),
        encoding="utf-8",
    )
    return report
