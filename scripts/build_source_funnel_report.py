#!/usr/bin/env python3
"""Build a transparent per-source collection funnel.

The report distinguishes active sources, configured-but-empty sources and sources
that still require authorized access. Missing records are never presented as
successful collection.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def _source_from_item(item: dict[str, object]) -> str | None:
    explicit = str(item.get("source") or item.get("source_name") or "").strip()
    if explicit:
        return explicit
    host = urlparse(str(item.get("url") or "")).netloc.casefold()
    if "auksjonen" in host:
        return "Auksjonen.no"
    if "politiet.no" in host:
        return "Politiet.no"
    if "finn.no" in host:
        return "FINN.no"
    if "konkurskupp" in host:
        return "Konkurskupp"
    if "bjaroy" in host or "bjarøy" in host:
        return "Bjarøy"
    if "konkurs.app" in host:
        return "Konkurs.app"
    return None


def _selected_counts(channels: dict[str, object], channel_name: str) -> dict[str, int]:
    channel = channels.get(channel_name, {})
    items = channel.get("items", []) if isinstance(channel, dict) else []
    counts: dict[str, int] = {}
    if not isinstance(items, list):
        return counts
    for item in items:
        if not isinstance(item, dict):
            continue
        source = _source_from_item(item)
        if source:
            counts[source] = counts.get(source, 0) + 1
    return counts


def build_payload(
    coverage: dict[str, object],
    snapshot: dict[str, object],
    channels: dict[str, object],
    event_leads: dict[str, object] | None = None,
) -> dict[str, object]:
    fetched = snapshot.get("sources", {})
    fetched = dict(fetched) if isinstance(fetched, dict) else {}
    errors = snapshot.get("source_errors", {})
    errors = dict(errors) if isinstance(errors, dict) else {}
    event_leads = event_leads or {}
    event_source = str(event_leads.get("source") or "").strip()
    if event_source:
        fetched[event_source] = int(event_leads.get("fetched_count", 0) or 0)
        event_error = str(event_leads.get("error") or "").strip()
        if event_error:
            errors[event_source] = event_error

    actionable = _selected_counts(channels, "actionable_opportunities")
    bankruptcy = _selected_counts(channels, "bankruptcy_leads")
    event_selected: dict[str, int] = {}
    event_items = event_leads.get("items", [])
    if isinstance(event_items, list):
        for item in event_items:
            if isinstance(item, dict):
                source = _source_from_item(item)
                if source:
                    event_selected[source] = event_selected.get(source, 0) + 1

    rows: list[dict[str, object]] = []
    source_configs = coverage.get("sources", [])
    if not isinstance(source_configs, list):
        source_configs = []
    for config in source_configs:
        if not isinstance(config, dict):
            continue
        source = str(config.get("source") or "").strip()
        if not source:
            continue
        configured = bool(config.get("configured"))
        active = bool(config.get("active"))
        fetched_count = int(fetched.get(source, 0) or 0)
        error = str(errors.get(source) or "").strip() or None
        if error:
            status = "error"
        elif not configured:
            status = "awaiting_authorized_configuration"
        elif active and fetched_count > 0:
            status = "collecting"
        elif active:
            status = "active_no_records"
        else:
            status = "inactive"
        rows.append(
            {
                "source": source,
                "access_mode": config.get("access_mode"),
                "configured": configured,
                "active": active,
                "status": status,
                "fetched": fetched_count,
                "actionable_selected": actionable.get(source, 0),
                "bankruptcy_leads_selected": bankruptcy.get(source, 0),
                "public_auction_event_leads_selected": event_selected.get(source, 0),
                "error": error,
                "required_configuration": config.get("required_configuration", []),
                "note": config.get("note"),
            }
        )

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "per-source visibility from coverage, collection snapshot and separated output channels; zero means no verified records collected",
        "summary": {
            "source_count": len(rows),
            "collecting_count": sum(row["status"] == "collecting" for row in rows),
            "awaiting_configuration_count": sum(
                row["status"] == "awaiting_authorized_configuration" for row in rows
            ),
            "error_count": sum(row["status"] == "error" for row in rows),
            "fetched_total": sum(int(row["fetched"]) for row in rows),
        },
        "sources": rows,
    }


def _read(path: str) -> dict[str, object]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", default="data/source_coverage.json")
    parser.add_argument("--snapshot", default="data/todays_opportunities.json")
    parser.add_argument("--channels", default="data/opportunity_channels.json")
    parser.add_argument("--event-leads", default="data/public_auction_event_leads.json")
    parser.add_argument("--output", default="data/source_funnel.json")
    args = parser.parse_args()

    payload = build_payload(
        _read(args.coverage),
        _read(args.snapshot),
        _read(args.channels),
        _read(args.event_leads),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
