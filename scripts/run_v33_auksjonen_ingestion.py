#!/usr/bin/env python3
"""Refresh an Auksjonen snapshot, then pass it through V3.2 monitoring."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.source_ingestion.auksjonen import (
    AUKSJONEN_CATEGORY_URL,
    build_snapshot,
    fetch_public_page,
    parse_public_listings,
)
from scripts.run_v32_continuous_opportunity_monitoring import build_monitoring_report


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run_refresh(
    *,
    html: str,
    state_payload: dict[str, Any] | None = None,
    source_url: str = AUKSJONEN_CATEGORY_URL,
    captured_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    listings = parse_public_listings(html, category_url=source_url)
    snapshot = build_snapshot(listings, category_url=source_url, captured_at=captured_at)
    monitoring, next_state = build_monitoring_report(snapshot, state_payload)
    report = {
        "schema_version": "3.3",
        "source": "Auksjonen.no",
        "source_page": source_url,
        "captured_at": snapshot["captured_at"],
        "listings_extracted": len(snapshot["opportunities"]),
        "snapshot_written": True,
        "new_opportunities_detected": monitoring["new_opportunities_detected"],
        "ready_for_financial_review": monitoring["ready_for_financial_review"],
        "automatic_purchase_decision": False,
        "monitoring_status": monitoring["status"],
        "errors": [],
        "status": "PASS" if snapshot["opportunities"] else "SOURCE_EMPTY",
    }
    return report, snapshot, next_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=AUKSJONEN_CATEGORY_URL)
    parser.add_argument("--html-file")
    parser.add_argument("--snapshot", default="data/live_validation/v3.3-auksjonen-live-snapshot.json")
    parser.add_argument("--state", default="data/monitoring/v3.2-seen-state.json")
    parser.add_argument("--report", default="data/validation/v3.3-source-ingestion.json")
    parser.add_argument("--monitoring-report", default="data/validation/v3.2-continuous-monitoring.json")
    args = parser.parse_args()

    try:
        html = (
            Path(args.html_file).read_text(encoding="utf-8")
            if args.html_file
            else fetch_public_page(args.source_url)
        )
        state_path = Path(args.state)
        report, snapshot, next_state = run_refresh(
            html=html,
            state_payload=_read_json(state_path, {}),
            source_url=args.source_url,
        )
        monitoring_report, _ = build_monitoring_report(snapshot, _read_json(state_path, {}))
    except Exception as exc:  # keep scheduled source failures explicit and non-destructive
        report = {
            "schema_version": "3.3",
            "source": "Auksjonen.no",
            "source_page": args.source_url,
            "listings_extracted": 0,
            "snapshot_written": False,
            "new_opportunities_detected": 0,
            "ready_for_financial_review": 0,
            "automatic_purchase_decision": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "status": "SOURCE_UNAVAILABLE",
        }
        snapshot = None
        next_state = None
        monitoring_report = None

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if snapshot is not None and next_state is not None and monitoring_report is not None:
        snapshot_path = Path(args.snapshot)
        state_path = Path(args.state)
        monitor_path = Path(args.monitoring_report)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        monitor_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        state_path.write_text(json.dumps(next_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        monitor_path.write_text(json.dumps(monitoring_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
