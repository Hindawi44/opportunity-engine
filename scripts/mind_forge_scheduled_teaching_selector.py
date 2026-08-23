from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


QUEUE_SCHEMA_PREFIX = "ai-teaching-gate-1."
STATE_SCHEMA_VERSION = "mind-forge-scheduled-teaching-state-1.0"
SELECTION_SCHEMA_VERSION = "mind-forge-scheduled-teaching-selection-1.0"
_ALLOWED_DOMAINS = {"CLOTHING_INVENTORY", "FABRIC_PROCUREMENT"}
_MAX_COMPLETED = 180


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
    if not path.exists():
        return {}
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


def _fingerprint(task: Mapping[str, Any]) -> str:
    material = {
        "task_id": _text(task.get("task_id")),
        "task_kind": _upper(task.get("task_kind")),
        "priority": int(task.get("priority") or 0),
        "reason": _text(task.get("reason")),
        "mind_forge_seed": _text(task.get("mind_forge_seed")),
        "context": dict(_mapping(task.get("context"))),
    }
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_queue(queue: Mapping[str, Any]) -> None:
    if not _text(queue.get("schema_version")).startswith(QUEUE_SCHEMA_PREFIX):
        raise ValueError("scheduled teaching requires AI Teaching Gate V1 queue")
    if _upper(queue.get("status")) != "SUCCESS":
        raise ValueError("AI Teaching Gate queue must be successful")
    if queue.get("project_domain_gate_enforced") is not True:
        raise ValueError("AI Teaching Gate queue lost project-domain gate")
    for field in (
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
    ):
        if queue.get(field) not in {None, False}:
            raise ValueError(f"AI Teaching Gate queue changed safety field {field}")


def _completed_fingerprints(state: Mapping[str, Any]) -> set[str]:
    if state and _text(state.get("schema_version")) not in {"", STATE_SCHEMA_VERSION}:
        raise ValueError("unsupported scheduled teaching state schema")
    return {
        _text(row.get("fingerprint"))
        for row in _rows(state.get("completed"))
        if _text(row.get("fingerprint"))
    }


def select_scheduled_teaching(
    *,
    queue: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Select at most one unseen AI_TEACHING task from a morning checkpoint."""

    _validate_queue(queue)
    completed = _completed_fingerprints(_mapping(state))

    eligible: list[dict[str, Any]] = []
    for raw in _rows(queue.get("ai_teaching_tasks")):
        task = dict(raw)
        if _upper(task.get("execution_mode")) != "AI_TEACHING":
            continue
        if task.get("requires_paid_ai") is not True:
            continue
        seed = _text(task.get("mind_forge_seed"))
        task_id = _text(task.get("task_id"))
        if not task_id or not seed:
            continue

        context = _mapping(task.get("context"))
        domain = _upper(context.get("project_domain"))
        if domain and domain not in _ALLOWED_DOMAINS:
            raise ValueError(f"scheduled AI task escaped project domain: {domain}")

        fingerprint = _fingerprint(task)
        task["scheduled_fingerprint"] = fingerprint
        if fingerprint in completed:
            continue
        eligible.append(task)

    eligible.sort(
        key=lambda row: (
            -int(row.get("priority") or 0),
            _text(row.get("task_kind")),
            _text(row.get("task_id")),
        )
    )

    selected = eligible[0] if eligible else None
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "SELECTED" if selected else "NO_NEW_AI_TEACHING_TASK",
        "scheduled": True,
        "should_run": selected is not None,
        "selected_task": selected,
        "eligible_unseen_task_count": len(eligible),
        "max_paid_ai_tasks_this_checkpoint": 1,
        "unchanged_completed_tasks_skipped": max(
            0,
            len(_rows(queue.get("ai_teaching_tasks"))) - len(eligible),
        ),
        "project_domain_gate_enforced": True,
        "automatic_code_change": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def manual_selection(seed: str) -> dict[str, Any]:
    clean = _text(seed)
    if not clean:
        raise ValueError("manual MIND FORGE seed is required")
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "SELECTED",
        "scheduled": False,
        "should_run": True,
        "selected_task": {
            "task_id": "manual-seed",
            "task_kind": "MANUAL_SEED",
            "priority": 0,
            "mind_forge_seed": clean,
            "scheduled_fingerprint": None,
        },
        "eligible_unseen_task_count": 1,
        "max_paid_ai_tasks_this_checkpoint": 1,
        "unchanged_completed_tasks_skipped": 0,
        "project_domain_gate_enforced": True,
        "automatic_code_change": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def record_success(
    *,
    state: Mapping[str, Any] | None,
    selection: Mapping[str, Any],
    run_id: str,
    source_run_id: str | None,
) -> dict[str, Any]:
    old = dict(_mapping(state))
    if old and _text(old.get("schema_version")) not in {"", STATE_SCHEMA_VERSION}:
        raise ValueError("unsupported scheduled teaching state schema")
    if selection.get("scheduled") is not True or selection.get("should_run") is not True:
        return old or {"schema_version": STATE_SCHEMA_VERSION, "completed": []}

    task = _mapping(selection.get("selected_task"))
    fingerprint = _text(task.get("scheduled_fingerprint"))
    task_id = _text(task.get("task_id"))
    if not fingerprint or not task_id:
        raise ValueError("successful scheduled selection is missing task fingerprint")

    completed = [dict(row) for row in _rows(old.get("completed"))]
    completed = [row for row in completed if _text(row.get("fingerprint")) != fingerprint]
    completed.append(
        {
            "fingerprint": fingerprint,
            "task_id": task_id,
            "task_kind": _upper(task.get("task_kind")) or None,
            "completed_run_id": _text(run_id),
            "source_checkpoint_run_id": _text(source_run_id) or None,
        }
    )
    completed = completed[-_MAX_COMPLETED:]
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "completed": completed,
        "completed_count": len(completed),
        "last_completed_task_id": task_id,
        "last_completed_run_id": _text(run_id),
    }


def _write_github_output(path: str | None, selection: Mapping[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(
            f"should_run={'true' if selection.get('should_run') is True else 'false'}\n"
        )
        task = _mapping(selection.get("selected_task"))
        handle.write(f"task_id={_text(task.get('task_id'))}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    select = sub.add_parser("select")
    select.add_argument("--queue", required=True)
    select.add_argument("--state")
    select.add_argument("--output", required=True)
    select.add_argument("--github-output")

    manual = sub.add_parser("manual")
    manual.add_argument("--seed", required=True)
    manual.add_argument("--output", required=True)
    manual.add_argument("--github-output")

    record = sub.add_parser("record")
    record.add_argument("--state")
    record.add_argument("--selection", required=True)
    record.add_argument("--run-id", required=True)
    record.add_argument("--source-run-id")
    record.add_argument("--output", required=True)

    args = parser.parse_args()

    if args.command == "select":
        queue = _read_json(Path(args.queue))
        state = _read_json(Path(args.state)) if args.state else {}
        result = select_scheduled_teaching(queue=queue, state=state)
        _write_json(Path(args.output), result)
        _write_github_output(args.github_output, result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "should_run": result["should_run"],
                    "eligible_unseen_task_count": result["eligible_unseen_task_count"],
                    "selected_task_id": _text(
                        _mapping(result.get("selected_task")).get("task_id")
                    )
                    or None,
                },
                ensure_ascii=False,
            )
        )
        return

    if args.command == "manual":
        result = manual_selection(args.seed)
        _write_json(Path(args.output), result)
        _write_github_output(args.github_output, result)
        print(json.dumps({"status": result["status"], "should_run": True}))
        return

    state = _read_json(Path(args.state)) if args.state else {}
    selection = _read_json(Path(args.selection))
    result = record_success(
        state=state,
        selection=selection,
        run_id=args.run_id,
        source_run_id=args.source_run_id,
    )
    _write_json(Path(args.output), result)
    print(
        json.dumps(
            {
                "status": "SCHEDULED_TEACHING_RECORDED",
                "completed_count": result.get("completed_count", 0),
                "last_completed_task_id": result.get("last_completed_task_id"),
            }
        )
    )


if __name__ == "__main__":
    main()
