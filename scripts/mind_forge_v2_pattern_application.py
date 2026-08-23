from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from scripts.mind_forge_v2_pattern_promotion import evaluate_pattern_promotions


_RESERVED_NON_HUMAN_ACTORS = {
    "system",
    "auto",
    "automation",
    "model",
    "mind_forge",
    "mind-forge",
    "agent",
}


def _require_human_actor(value: Any, *, field: str) -> str:
    actor = str(value or "").strip()
    if not actor or actor.casefold() in _RESERVED_NON_HUMAN_ACTORS:
        raise ValueError(f"{field} must identify an explicit human actor")
    return actor


def _applications(memory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in memory.get("pattern_applications", []) or []]
    ids = [str(row.get("application_id") or "").strip() for row in rows]
    if any(not item for item in ids):
        raise ValueError("every pattern application must have an application id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate application id in pattern application registry")
    return rows


def _promotion_by_code(memory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    promotion = evaluate_pattern_promotions(memory)
    rows: dict[str, dict[str, Any]] = {}
    for raw in promotion.get("assessments", []) or []:
        row = dict(raw)
        code = str(row.get("pattern_code") or "").strip()
        if not code:
            continue
        if code in rows:
            raise ValueError(f"duplicate promoted pattern code: {code}")
        rows[code] = row
    return rows


def _policy_source(memory: dict[str, Any], *, pattern_id: str) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for raw in memory.get("next_cycle_search_adjustments", []) or []:
        row = dict(raw)
        if str(row.get("origin_memory_id") or "").strip() != pattern_id:
            continue
        if str(row.get("mode") or "") != "SHADOW_HINT":
            continue
        if row.get("may_auto_reject_ideas") is True:
            raise ValueError("learned search policy may not auto-reject ideas")
        question = str(row.get("search_question") or "").strip()
        required = str(row.get("required_evidence") or "").strip()
        if not question or not required:
            continue
        matches.append(row)
    if len(matches) > 1:
        raise ValueError(f"multiple policy sources found for pattern {pattern_id}")
    return matches[0] if matches else None


def _approved_policy(source: dict[str, Any], application: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": str(source.get("action") or "").strip(),
        "search_question": str(source.get("search_question") or "").strip(),
        "required_evidence": str(source.get("required_evidence") or "").strip(),
        "origin_memory_id": str(application["pattern_id"]),
        "mode": "APPROVED_POLICY_HINT",
        "application_id": str(application["application_id"]),
        "approved_by": str(application["approved_by"]),
        "human_approval_recorded": True,
        "may_change_search_priority": True,
        "may_auto_reject_ideas": False,
        "approved_at_independent_run_count": int(application["approved_at_independent_run_count"]),
        "approved_at_example_diversity_count": int(application["approved_at_example_diversity_count"]),
    }


def reconcile_pattern_applications(memory: dict[str, Any]) -> dict[str, Any]:
    """Revalidate persisted human approvals against current promotion state.

    Raw `approved_production_adjustments` are never trusted. They are rebuilt only
    from an ACTIVE application record whose underlying pattern remains
    PRODUCTION_ELIGIBLE and whose original shadow-policy source still exists.
    """

    data = copy.deepcopy(memory)
    if data.get("auto_apply_to_production") is True:
        raise ValueError("pattern application gate refuses memory that claims auto-apply")

    promotions = _promotion_by_code(data)
    apps = _applications(data)
    active_policies: list[dict[str, Any]] = []
    reconciled_apps: list[dict[str, Any]] = []

    for app in apps:
        status = str(app.get("status") or "").strip()
        code = str(app.get("pattern_code") or "").strip()
        pattern_id = str(app.get("pattern_id") or "").strip()

        if status == "ROLLED_BACK" or status.startswith("SUSPENDED_"):
            reconciled_apps.append(app)
            continue

        if status != "ACTIVE":
            app["status"] = "SUSPENDED_INTEGRITY"
            app["suspension_reason"] = "unknown application status"
            reconciled_apps.append(app)
            continue

        try:
            approved_by = _require_human_actor(app.get("approved_by"), field="approved_by")
        except ValueError:
            app["status"] = "SUSPENDED_INTEGRITY"
            app["suspension_reason"] = "human approval actor is missing or invalid"
            reconciled_apps.append(app)
            continue

        if app.get("human_approval_recorded") is not True:
            app["status"] = "SUSPENDED_INTEGRITY"
            app["suspension_reason"] = "explicit human approval record is missing"
            reconciled_apps.append(app)
            continue

        assessment = promotions.get(code)
        if (
            assessment is None
            or assessment.get("production_eligible") is not True
            or str(assessment.get("pattern_id") or "").strip() != pattern_id
        ):
            app["status"] = "SUSPENDED_NOT_ELIGIBLE"
            app["suspension_reason"] = "pattern is no longer production eligible"
            reconciled_apps.append(app)
            continue

        approved_runs = int(app.get("approved_at_independent_run_count", -1))
        approved_diversity = int(app.get("approved_at_example_diversity_count", -1))
        current_runs = int(assessment.get("independent_run_count", 0))
        current_diversity = int(assessment.get("example_diversity_count", 0))
        if approved_runs < 5 or approved_diversity < 3:
            app["status"] = "SUSPENDED_INTEGRITY"
            app["suspension_reason"] = "approval snapshot was below production eligibility thresholds"
            reconciled_apps.append(app)
            continue
        if current_runs < approved_runs or current_diversity < approved_diversity:
            app["status"] = "SUSPENDED_NOT_ELIGIBLE"
            app["suspension_reason"] = "current evidence is weaker than the approved snapshot"
            reconciled_apps.append(app)
            continue

        source = _policy_source(data, pattern_id=pattern_id)
        if source is None:
            app["status"] = "SUSPENDED_POLICY_MISSING"
            app["suspension_reason"] = "the reviewed search-policy source is no longer present"
            reconciled_apps.append(app)
            continue

        app["approved_by"] = approved_by
        app.pop("suspension_reason", None)
        reconciled_apps.append(app)
        active_policies.append(_approved_policy(source, app))

    data["pattern_applications"] = reconciled_apps
    data["approved_production_adjustments"] = active_policies
    data["active_pattern_application_count"] = len(active_policies)
    data["auto_apply_to_production"] = False
    return data


def approve_pattern_application(memory: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    """Activate one production-eligible pattern after an explicit human approval."""

    if str(approval.get("action") or "") != "APPROVE_PATTERN":
        raise ValueError("approval action must be APPROVE_PATTERN")
    actor = _require_human_actor(approval.get("approved_by"), field="approved_by")
    application_id = str(approval.get("application_id") or "").strip()
    pattern_code = str(approval.get("pattern_code") or "").strip()
    if not application_id:
        raise ValueError("application id is required")
    if not pattern_code:
        raise ValueError("pattern code is required")

    data = reconcile_pattern_applications(memory)
    apps = _applications(data)
    if any(str(row["application_id"]) == application_id for row in apps):
        raise ValueError(f"application id already exists: {application_id}")
    if any(
        str(row.get("pattern_code") or "") == pattern_code and str(row.get("status") or "") == "ACTIVE"
        for row in apps
    ):
        raise ValueError(f"pattern already active: {pattern_code}")

    assessment = _promotion_by_code(data).get(pattern_code)
    if assessment is None or assessment.get("production_eligible") is not True:
        raise ValueError(f"pattern is not production eligible: {pattern_code}")

    try:
        observed_runs = int(approval.get("observed_independent_run_count"))
    except (TypeError, ValueError):
        raise ValueError("observed independent run count is required") from None
    try:
        observed_diversity = int(approval.get("observed_example_diversity_count"))
    except (TypeError, ValueError):
        raise ValueError("observed example diversity count is required") from None

    current_runs = int(assessment["independent_run_count"])
    current_diversity = int(assessment["example_diversity_count"])
    if observed_runs != current_runs:
        raise ValueError("approval run count does not match the current production-eligible snapshot")
    if observed_diversity != current_diversity:
        raise ValueError("approval diversity count does not match the current production-eligible snapshot")

    pattern_id = str(assessment["pattern_id"])
    if _policy_source(data, pattern_id=pattern_id) is None:
        raise ValueError("production-eligible pattern has no reviewed search-policy source")

    apps.append({
        "application_id": application_id,
        "pattern_id": pattern_id,
        "pattern_code": pattern_code,
        "status": "ACTIVE",
        "approved_by": actor,
        "approved_at_independent_run_count": current_runs,
        "approved_at_example_diversity_count": current_diversity,
        "human_approval_recorded": True,
        "may_auto_reject_ideas": False,
    })
    data["pattern_applications"] = apps
    return reconcile_pattern_applications(data)


def rollback_pattern_application(memory: dict[str, Any], rollback: dict[str, Any]) -> dict[str, Any]:
    """Manually disable one prior application without deleting the learned pattern."""

    if str(rollback.get("action") or "") != "ROLLBACK_PATTERN":
        raise ValueError("rollback action must be ROLLBACK_PATTERN")
    actor = _require_human_actor(rollback.get("rolled_back_by"), field="rolled_back_by")
    application_id = str(rollback.get("application_id") or "").strip()
    rollback_id = str(rollback.get("rollback_id") or "").strip()
    if not application_id:
        raise ValueError("application id is required for rollback")
    if not rollback_id:
        raise ValueError("rollback id is required")

    data = reconcile_pattern_applications(memory)
    apps = _applications(data)
    if any(str(row.get("rollback_id") or "") == rollback_id for row in apps):
        raise ValueError(f"rollback id already exists: {rollback_id}")

    matches = [row for row in apps if str(row["application_id"]) == application_id]
    if len(matches) != 1:
        raise ValueError(f"application not found: {application_id}")
    target = matches[0]
    if str(target.get("status") or "") == "ROLLED_BACK":
        raise ValueError(f"application already rolled back: {application_id}")

    target["status"] = "ROLLED_BACK"
    target["rollback_id"] = rollback_id
    target["rolled_back_by"] = actor
    target["human_rollback_recorded"] = True
    target.pop("suspension_reason", None)
    data["pattern_applications"] = apps
    return reconcile_pattern_applications(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("memory_json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--action", required=True, choices=["APPROVE_PATTERN", "ROLLBACK_PATTERN"])
    parser.add_argument("--pattern-code", default="")
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--observed-independent-run-count", type=int, default=0)
    parser.add_argument("--observed-example-diversity-count", type=int, default=0)
    parser.add_argument("--rollback-id", default="")
    args = parser.parse_args()

    memory = json.loads(Path(args.memory_json).read_text(encoding="utf-8"))
    if args.action == "APPROVE_PATTERN":
        result = approve_pattern_application(
            memory,
            {
                "action": args.action,
                "pattern_code": args.pattern_code,
                "application_id": args.application_id,
                "approved_by": args.actor,
                "observed_independent_run_count": args.observed_independent_run_count,
                "observed_example_diversity_count": args.observed_example_diversity_count,
            },
        )
    else:
        result = rollback_pattern_application(
            memory,
            {
                "action": args.action,
                "application_id": args.application_id,
                "rollback_id": args.rollback_id,
                "rolled_back_by": args.actor,
            },
        )

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "MIND_FORGE_V2_PATTERN_APPLICATION_GATE_COMPLETE",
        "action": args.action,
        "active_pattern_application_count": result.get("active_pattern_application_count", 0),
        "auto_apply_to_production": result.get("auto_apply_to_production"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
