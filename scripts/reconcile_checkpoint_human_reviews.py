#!/usr/bin/env python3
"""Apply persisted human reviews to a completed lifecycle checkpoint."""
from __future__ import annotations

import argparse
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


def _write_daily_analysis(
    report: Mapping[str, Any], manifest: Mapping[str, Any], *, root: Path, output_dir: Path
) -> dict[str, Any]:
    analysis = build_daily_analysis(
        report,
        detail_records=_detail_records(manifest, root),
    )
    json_path = output_dir / "one-opportunity-daily-analysis.json"
    text_path = output_dir / "one-opportunity-daily-analysis.txt"
    json_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(render_daily_analysis(analysis), encoding="utf-8")
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
