"""Route missed-opportunity root causes to the correct adaptation mechanism.

The project must not respond to every miss by broadening search vocabulary.
This router is a deterministic control plane above durable missed-opportunity
memory: QUERY_GAP may flow into the existing bounded keyword learner, while
source, parser, verification, entity, ranking and reporting failures are routed
to dedicated repair queues.  The router itself does not mutate source policy,
code, queries, rankings, or financial state.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.missed_opportunity_learning import (
    MissedOpportunityCase,
    load_missed_opportunity_memory,
)

SCHEMA_VERSION = "root-cause-feedback-router-1.0"
OUTPUT_FILENAME = "root-cause-feedback-router.json"
MEMORY_RELATIVE_PATH = Path("learning/missed-opportunities.json")

_ROUTE_POLICY: dict[str, dict[str, object]] = {
    "QUERY_GAP": {
        "mechanism": "ADAPTIVE_KEYWORD_LEARNING",
        "action": "RUN_BOUNDED_SHADOW_KEYWORD_LEARNING",
        "keyword_learning_eligible": True,
        "automatic_adaptation_available": True,
        "priority": "HIGH",
    },
    "SOURCE_GAP": {
        "mechanism": "SOURCE_COVERAGE_WATERFALL",
        "action": "REVIEW_OR_EXPAND_ZERO_COST_FIRST_SOURCE_FALLBACK",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
    "RETRIEVAL_GAP": {
        "mechanism": "RETRIEVAL_RELIABILITY_QUEUE",
        "action": "REPAIR_SOURCE_FETCH_OR_RETRY_PATH",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
    "TIMING_GAP": {
        "mechanism": "SCHEDULING_COVERAGE_QUEUE",
        "action": "REVIEW_DISCOVERY_FREQUENCY_OR_FRESHNESS_WINDOW",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "MEDIUM",
    },
    "PARSER_GAP": {
        "mechanism": "PARSER_REGRESSION_QUEUE",
        "action": "CREATE_SOURCE_SPECIFIC_PARSER_REGRESSION_CASE",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
    "ENTITY_LINK_GAP": {
        "mechanism": "ENTITY_LINK_REPAIR_QUEUE",
        "action": "CREATE_ENTITY_LINK_REGRESSION_CASE",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
    "CLASSIFICATION_GAP": {
        "mechanism": "CLASSIFIER_REGRESSION_QUEUE",
        "action": "CREATE_CLASSIFICATION_REGRESSION_CASE",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
    "VERIFICATION_GAP": {
        "mechanism": "VERIFIER_REPAIR_QUEUE",
        "action": "CREATE_SOURCE_VERIFICATION_REGRESSION_CASE",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
    "RANKING_GAP": {
        "mechanism": "RANKING_POLICY_REVIEW_QUEUE",
        "action": "REVIEW_RANKING_OR_USEFUL_OPPORTUNITY_FILTER",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "MEDIUM",
    },
    "REPORTING_GAP": {
        "mechanism": "REPORTING_INTEGRITY_QUEUE",
        "action": "CREATE_REPORTING_RECONCILIATION_REGRESSION_CASE",
        "keyword_learning_eligible": False,
        "automatic_adaptation_available": False,
        "priority": "HIGH",
    },
}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def _priority(base: object, *, repeat_miss: bool) -> str:
    if repeat_miss:
        return "CRITICAL"
    value = str(base or "MEDIUM").strip().upper()
    return value if value in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "MEDIUM"


def _route_case(case: MissedOpportunityCase) -> dict[str, Any]:
    diagnosed = case if case.root_cause else case.with_diagnosis()
    cause = str(diagnosed.root_cause or "UNDIAGNOSED").strip().upper()
    policy = _ROUTE_POLICY.get(
        cause,
        {
            "mechanism": "MANUAL_DIAGNOSTICS_QUEUE",
            "action": "REVIEW_UNCLASSIFIED_PIPELINE_FAILURE",
            "keyword_learning_eligible": False,
            "automatic_adaptation_available": False,
            "priority": "MEDIUM",
        },
    )
    recovered_monitor_only = (
        diagnosed.learning_status == "RECOVERED" and not diagnosed.repeat_miss
    )
    return {
        "case_id": diagnosed.case_id,
        "market_code": diagnosed.market_code,
        "root_cause": cause,
        "mechanism": policy["mechanism"],
        "action": policy["action"],
        "priority": _priority(policy.get("priority"), repeat_miss=diagnosed.repeat_miss),
        "route_status": (
            "RECOVERED_MONITOR_ONLY" if recovered_monitor_only else "ACTIVE"
        ),
        "repeat_miss": diagnosed.repeat_miss,
        "learning_status": diagnosed.learning_status,
        "keyword_learning_eligible": (
            bool(policy["keyword_learning_eligible"]) and not recovered_monitor_only
        ),
        "automatic_adaptation_available": (
            bool(policy["automatic_adaptation_available"]) and not recovered_monitor_only
        ),
        "ground_truth_url": diagnosed.ground_truth_url,
        "stock_proven": diagnosed.stock_proven,
    }


def build_root_cause_feedback_report(
    cases: Sequence[MissedOpportunityCase],
) -> dict[str, Any]:
    """Build deterministic repair routes without mutating any subsystem."""
    routes = [_route_case(case) for case in cases]
    priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    routes.sort(
        key=lambda row: (
            row["route_status"] != "ACTIVE",
            priority_rank.get(str(row["priority"]), 9),
            str(row["market_code"]),
            str(row["case_id"]),
        )
    )
    active = [row for row in routes if row["route_status"] == "ACTIVE"]
    mechanisms = Counter(str(row["mechanism"]) for row in active)
    causes = Counter(str(row["root_cause"]) for row in active)
    critical = sum(row["priority"] == "CRITICAL" for row in active)
    keyword_count = sum(row["keyword_learning_eligible"] is True for row in active)

    if not routes:
        status = "VALID_ZERO_NO_MISSED_OPPORTUNITIES"
    elif active:
        status = "ACTION_REQUIRED"
    else:
        status = "MONITOR_ONLY"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "known_case_count": len(routes),
        "active_route_count": len(active),
        "monitor_only_count": len(routes) - len(active),
        "critical_route_count": critical,
        "keyword_learning_route_count": keyword_count,
        "mechanism_counts": dict(sorted(mechanisms.items())),
        "root_cause_counts": dict(sorted(causes.items())),
        "routes": routes,
        "routing_contract": {
            "query_gap": "ADAPTIVE_KEYWORD_LEARNING",
            "source_gap": "SOURCE_COVERAGE_WATERFALL",
            "parser_gap": "PARSER_REGRESSION_QUEUE",
            "verification_gap": "VERIFIER_REPAIR_QUEUE",
            "reporting_gap": "REPORTING_INTEGRITY_QUEUE",
        },
        "source_gap_never_auto_becomes_keyword": True,
        "automatic_source_policy_mutation": False,
        "automatic_code_change": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _attach_to_brief(output_dir: Path, report: Mapping[str, Any]) -> None:
    path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(path)
    if brief is None:
        return
    brief["root_cause_feedback_router"] = {
        key: report.get(key)
        for key in (
            "schema_version",
            "status",
            "known_case_count",
            "active_route_count",
            "monitor_only_count",
            "critical_route_count",
            "keyword_learning_route_count",
            "mechanism_counts",
            "root_cause_counts",
        )
    }
    _write_json(path, brief)


def write_root_cause_feedback_router(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    """Read durable missed-opportunity memory and write the operator routing view."""
    output = Path(output_dir)
    memory_path = Path(input_root) / MEMORY_RELATIVE_PATH
    cases = load_missed_opportunity_memory(memory_path)
    report = build_root_cause_feedback_report(cases)
    report["memory_path"] = memory_path.as_posix()
    _write_json(output / OUTPUT_FILENAME, report)
    _attach_to_brief(output, report)
    return report
