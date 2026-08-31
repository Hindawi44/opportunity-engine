#!/usr/bin/env python3
"""Apply persisted human reviews to a completed lifecycle checkpoint."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.human_review_checkpoint import (
    reconcile_checkpoint_human_reviews,
)
from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    TERMINAL_WORKFLOWS,
    WORKFLOW_RANK,
    write_lifecycle_checkpoint_artifacts,
)
from opportunity_engine.discovery.one_opportunity_daily_analysis import (
    build_daily_analysis,
    render_daily_analysis,
)


ACTIVE_STAGE = "ACTIVE_OPPORTUNITY"
PREVIOUS_CHECKPOINT_SCOPE = "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT"


def _load(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_optional(path: str | Path) -> dict[str, Any] | None:
    target = Path(path)
    if not target.exists():
        return None
    return _load(target)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _same_event(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    keys = (
        "opportunity_id",
        "source_ref",
        "changed_at",
        "from_workflow_status",
        "to_workflow_status",
        "from_reason_code",
        "to_reason_code",
    )
    return all(_compact(left.get(key)) == _compact(right.get(key)) for key in keys)


def _merge_current_review_transition(
    report: dict[str, Any], review_payload: Mapping[str, Any] | None
) -> None:
    """Add the current manual-review transition once when enrichment missed it."""
    if not isinstance(review_payload, Mapping):
        return
    if review_payload.get("lifecycle_transition_created") is not True:
        return
    raw_event = review_payload.get("lifecycle_transition")
    if not isinstance(raw_event, Mapping):
        return

    lifecycle = report.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return
    transitions = lifecycle.setdefault("transitions", {})
    if not isinstance(transitions, dict):
        return
    current_events = transitions.setdefault("current_run_events", [])
    if not isinstance(current_events, list):
        return

    event = dict(raw_event)
    event["initial_snapshot"] = False
    opportunity_id = _compact(event.get("opportunity_id"))
    target = next(
        (
            item
            for item in report.get("deduplicated_opportunities") or []
            if isinstance(item, Mapping)
            and _compact(item.get("opportunity_identity")) == opportunity_id
        ),
        None,
    )
    if isinstance(target, Mapping):
        event["market_code"] = _compact(target.get("market_code")).upper()
        names = target.get("source_names") or []
        if isinstance(names, list) and names:
            event["source_name"] = _compact(names[0])

    if any(
        isinstance(existing, Mapping) and _same_event(existing, event)
        for existing in current_events
    ):
        return

    current_events.append(event)
    transitions["events_created_this_run"] = int(
        transitions.get("events_created_this_run") or 0
    ) + 1
    transitions["transitions_created_this_run"] = int(
        transitions.get("transitions_created_this_run") or 0
    ) + 1

    previous = _compact(event.get("from_workflow_status")).upper()
    current = _compact(event.get("to_workflow_status")).upper()
    if previous in WORKFLOW_RANK and current in WORKFLOW_RANK:
        if WORKFLOW_RANK[current] > WORKFLOW_RANK[previous]:
            transitions["promoted_count"] = int(
                transitions.get("promoted_count") or 0
            ) + 1
    if current in TERMINAL_WORKFLOWS and current != previous:
        transitions["closed_historical_or_rejected_count"] = int(
            transitions.get("closed_historical_or_rejected_count") or 0
        ) + 1

    persistence = lifecycle.get("persistence")
    if isinstance(persistence, dict):
        source_name = _compact(event.get("source_name"))
        market_code = _compact(event.get("market_code")).upper()
        for source in persistence.get("sources") or []:
            if not isinstance(source, dict):
                continue
            same_source = source_name and _compact(source.get("source_name")) == source_name
            same_market = market_code and _compact(source.get("market_code")).upper() == market_code
            if same_source or (not source_name and same_market):
                source["lifecycle_events_created_this_run"] = int(
                    source.get("lifecycle_events_created_this_run") or 0
                ) + 1
                break


def _active_analysis_candidates(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in report.get("deduplicated_opportunities") or []:
        if not isinstance(raw, Mapping):
            continue
        if _compact(raw.get("listing_status")).upper() != "ACTIVE":
            continue
        if _compact(raw.get("workflow_status")).upper() != ACTIVE_STAGE:
            continue
        if raw.get("analysis_eligible") is not True:
            continue
        result.append(dict(raw))
    return result


def _restored_source_map(report: Mapping[str, Any]) -> dict[str, bool]:
    lifecycle = report.get("lifecycle")
    if not isinstance(lifecycle, Mapping):
        return {}
    persistence = lifecycle.get("persistence")
    if not isinstance(persistence, Mapping):
        return {}
    result: dict[str, bool] = {}
    for raw in persistence.get("sources") or []:
        if not isinstance(raw, Mapping):
            continue
        name = _compact(raw.get("source_name"))
        if name:
            result[name] = raw.get("previous_state_restored") is True
    return result


def _novel_opportunity_ids(report: Mapping[str, Any]) -> set[str] | None:
    """Return cross-run-proven changed IDs, or None when no prior baseline exists.

    A source whose previous state was not restored cannot prove that an initial
    snapshot is new. Those snapshots stay carry-over/watch-only until a real
    lifecycle transition is observed. This prevents the same lot from being
    presented as a new daily opportunity merely because one source lacked state.
    """
    lifecycle = report.get("lifecycle")
    if not isinstance(lifecycle, Mapping):
        return None
    persistence = lifecycle.get("persistence")
    if not isinstance(persistence, Mapping):
        return None
    if _compact(persistence.get("comparison_scope")).upper() != PREVIOUS_CHECKPOINT_SCOPE:
        return None
    transitions = lifecycle.get("transitions")
    if not isinstance(transitions, Mapping):
        return set()
    events = transitions.get("current_run_events")
    if not isinstance(events, list):
        return set()

    restored_by_source = _restored_source_map(report)
    result: set[str] = set()
    for raw in events:
        if not isinstance(raw, Mapping):
            continue
        identity = _compact(raw.get("opportunity_id"))
        if not identity:
            continue
        if raw.get("initial_snapshot") is True:
            source_name = _compact(raw.get("source_name"))
            if not restored_by_source.get(source_name, False):
                continue
        result.add(identity)
    return result


def _candidate_rank(item: Mapping[str, Any]) -> tuple[bool, float, str]:
    try:
        score = float(item.get("discovery_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return (
        item.get("top5_eligible") is not True,
        -score,
        _compact(item.get("opportunity_identity")),
    )


def _apply_daily_novelty_gate(report: dict[str, Any]) -> dict[str, Any]:
    """Prevent unchanged carry-over opportunities from becoming 'opportunity of the day'."""
    active = _active_analysis_candidates(report)
    novel_ids = _novel_opportunity_ids(report)
    if novel_ids is None:
        meta = {
            "schema_version": "daily-opportunity-novelty-gate-1.0",
            "gate_applied": False,
            "reason": "NO_PREVIOUS_SUCCESSFUL_CHECKPOINT_BASELINE",
            "active_analysis_eligible_count": len(active),
            "novel_active_count": len(active),
            "carryover_active_count": 0,
            "novel_active_opportunity_ids": [
                _compact(item.get("opportunity_identity")) for item in active
            ],
        }
        report["daily_novelty"] = meta
        return meta

    novel = [
        item
        for item in active
        if _compact(item.get("opportunity_identity")) in novel_ids
    ]
    novel.sort(key=_candidate_rank)
    novel_identity_set = {
        _compact(item.get("opportunity_identity")) for item in novel
    }
    carryover = [
        item
        for item in active
        if _compact(item.get("opportunity_identity")) not in novel_identity_set
    ]

    existing = report.get("next_human_action")
    existing_identity = (
        _compact(existing.get("opportunity_identity"))
        if isinstance(existing, Mapping)
        else ""
    )
    if novel:
        preferred = next(
            (
                item
                for item in novel
                if _compact(item.get("opportunity_identity")) == existing_identity
            ),
            novel[0],
        )
        report["next_human_action"] = {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": _compact(preferred.get("opportunity_identity")),
            "reason": "A new or lifecycle-changed active opportunity is ready for human review.",
            "workflow_status": ACTIVE_STAGE,
        }
    else:
        report["next_human_action"] = {
            "action": "NO_IMMEDIATE_ACTION",
            "opportunity_identity": None,
            "reason": "No new or lifecycle-changed active analysis-eligible opportunity since the previous successful checkpoint.",
            "carryover_active_opportunity_count": len(carryover),
        }

    meta = {
        "schema_version": "daily-opportunity-novelty-gate-1.0",
        "gate_applied": True,
        "reason": "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT",
        "active_analysis_eligible_count": len(active),
        "novel_active_count": len(novel),
        "carryover_active_count": len(carryover),
        "novel_active_opportunity_ids": sorted(novel_identity_set),
        "carryover_active_opportunity_ids": sorted(
            _compact(item.get("opportunity_identity")) for item in carryover
        ),
    }
    report["daily_novelty"] = meta
    return meta


def _daily_analysis_checkpoint_view(
    report: Mapping[str, Any], novelty: Mapping[str, Any]
) -> dict[str, Any]:
    if novelty.get("gate_applied") is not True:
        return deepcopy(dict(report))
    allowed = {
        _compact(item) for item in novelty.get("novel_active_opportunity_ids") or []
    }
    view = deepcopy(dict(report))
    view["deduplicated_opportunities"] = [
        dict(item)
        for item in report.get("deduplicated_opportunities") or []
        if isinstance(item, Mapping)
        and _compact(item.get("opportunity_identity")) in allowed
    ]
    view["next_human_action"] = deepcopy(report.get("next_human_action"))
    return view


def _detail_records(manifest: Mapping[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for source in manifest.get("sources") or []:
        if not isinstance(source, Mapping):
            continue
        directory = root / _compact(source.get("artifact_dir"))
        filename = _compact(source.get("unified_report_file")) or "unified-opportunity-report.json"
        path = directory / filename
        if not path.exists():
            continue
        payload = _load(path)
        for raw in payload.get("records") or []:
            if not isinstance(raw, Mapping):
                continue
            item = dict(raw)
            for key in ("opportunity_id", "opportunity_identity", "source_url", "canonical_url", "url"):
                identity = _compact(item.get(key))
                if identity:
                    details.setdefault(identity, item)
    return details


def _render_daily_analysis_with_novelty(analysis: Mapping[str, Any]) -> str:
    if analysis.get("analysis_state") != "NO_NEW_OR_CHANGED_OPPORTUNITY":
        return render_daily_analysis(analysis)
    count = int(analysis.get("carryover_active_candidate_count") or 0)
    lines = [
        "تحليل فرصة اليوم — مخزون الملابس",
        f"الوقت: {analysis.get('generated_at')}",
        "الحالة: لا توجد فرصة جديدة أو متغيرة جوهريًا اليوم.",
        f"فرص نشطة قديمة تحت المراقبة: {count}",
        "القرار الحالي: لا نعيد تدوير الفرص القديمة؛ ننتظر فرصة جديدة أو تغييرًا مثبتًا.",
        "الإجراء البشري الوحيد: WAIT_FOR_NEW_OR_CHANGED_OPPORTUNITY",
        "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
    ]
    return "\n".join(lines) + "\n"


def _write_daily_analysis(
    report: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    root: Path,
    output_dir: Path,
    novelty: Mapping[str, Any],
) -> dict[str, Any]:
    view = _daily_analysis_checkpoint_view(report, novelty)
    analysis = build_daily_analysis(
        view,
        detail_records=_detail_records(manifest, root),
    )
    analysis["daily_novelty"] = dict(novelty)
    if novelty.get("gate_applied") is True and int(novelty.get("novel_active_count") or 0) == 0:
        analysis["selection_status"] = "VALID_ZERO_RESULT"
        analysis["selection_reason"] = "NO_NEW_OR_CHANGED_ACTIVE_OPPORTUNITY"
        analysis["analysis_state"] = "NO_NEW_OR_CHANGED_OPPORTUNITY"
        analysis["active_analysis_eligible_candidate_count"] = int(
            novelty.get("active_analysis_eligible_count") or 0
        )
        analysis["carryover_active_candidate_count"] = int(
            novelty.get("carryover_active_count") or 0
        )
        analysis["next_human_action"] = {
            "action": "WAIT_FOR_NEW_OR_CHANGED_OPPORTUNITY",
            "opportunity_identity": None,
        }

    json_path = output_dir / "one-opportunity-daily-analysis.json"
    text_path = output_dir / "one-opportunity-daily-analysis.txt"
    json_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(
        _render_daily_analysis_with_novelty(analysis), encoding="utf-8"
    )
    return analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--human-review-outcome")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = _load(args.manifest)
    reconciled = reconcile_checkpoint_human_reviews(
        _load(args.report),
        manifest,
        root=args.root,
    )
    review_path = (
        Path(args.human_review_outcome)
        if args.human_review_outcome
        else Path(args.report).with_name("human-review-outcome.json")
    )
    _merge_current_review_transition(reconciled, _load_optional(review_path))
    novelty = _apply_daily_novelty_gate(reconciled)
    write_lifecycle_checkpoint_artifacts(
        reconciled,
        args.report,
        args.summary,
    )
    analysis = _write_daily_analysis(
        reconciled,
        manifest,
        root=Path(args.root),
        output_dir=Path(args.report).parent,
        novelty=novelty,
    )
    print(
        json.dumps(
            {
                "human_review_outcome_count": reconciled.get(
                    "human_review_outcome_count", 0
                ),
                "next_human_action": reconciled.get("next_human_action"),
                "transitions": (reconciled.get("lifecycle") or {}).get(
                    "transitions"
                ),
                "daily_novelty": novelty,
                "daily_analysis": {
                    "selection_status": analysis.get("selection_status"),
                    "analysis_state": analysis.get("analysis_state"),
                    "next_human_action": analysis.get("next_human_action"),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
