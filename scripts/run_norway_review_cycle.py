#!/usr/bin/env python3
"""Reconnect existing Norwegian SQLite review memory to the restored direct-sale search."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from opportunity_engine.discovery.unified_opportunity_report import (
    build_unified_opportunity_report,
    serialize_unified_opportunity_report,
)
from opportunity_engine.human_listing_review_queue import build_queue
from opportunity_engine.operator_decision_ingest import (
    DEFAULT_EVENTS,
    ingest_explicit_events,
)
from opportunity_engine.operator_study_memory import export_memory
from opportunity_engine.persistence.live_unified_persistence import (
    persist_unified_report_with_artifacts,
)


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _first_price(card: Mapping[str, Any]) -> float | None:
    for key in ("current_bid_nok", "buy_now_nok", "start_price_nok"):
        value = card.get(key)
        if value is not None:
            return float(value)
    return None


def _candidate(card: Mapping[str, Any]) -> dict[str, Any]:
    url = str(card.get("url") or "").strip()
    title = str(card.get("title") or "").strip()
    if not url or not title:
        raise ValueError("direct-sale card requires title and URL")
    return {
        "title": title,
        "scenario": "AUCTION",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": (
            "Norwegian public Auksjonen item page was opened and matched to the "
            "source object; human study/delete/later review remains separate."
        ),
        "page_role": "ITEM_LISTING",
        "opportunity_identity": url,
        "identity_stable": True,
        "listing_status": "ACTIVE",
        "top5_eligible": False,
        "analysis_eligible": False,
        "verified": True,
        "source_urls": [url],
        "source_providers": ["Auksjonen.no"],
        "textile_category": "GENERAL_ASSET",
        "inventory_type": "auction_asset",
        "location": card.get("location"),
        "price_nok": _first_price(card),
        "source_object_id": str(card.get("object_id") or ""),
        "evidence_signals": [
            "active_public_api_listing",
            "verified_exact_public_item_page",
        ],
        "verification": [
            {
                "url": url,
                "title": title,
                "bounded_context": (
                    "Exact public item page loaded at collection time; this does "
                    "not prove bankruptcy ownership, profitability, or future availability."
                ),
                "page_role": "ITEM_DETAIL",
                "listing_status": "ACTIVE",
                "verified": True,
            }
        ],
        "missing_information": ["commercial qualification not evaluated"],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _queue_row(card: Mapping[str, Any]) -> dict[str, Any]:
    url = str(card.get("url") or "").strip()
    return {
        "opportunity_identity": url,
        "title": card.get("title"),
        "canonical_url": url,
        "source_urls": [url],
        "market_code": "NO",
        "listing_status": "ACTIVE",
        "source_names": ["Auksjonen.no"],
        "missing_evidence": ["commercial qualification not evaluated"],
    }


def _filtered_norway_events(source: Path, destination: Path) -> dict[str, int]:
    if not source.is_file():
        payload = {"schema_version": "operator-review-events-v1", "events": []}
        total = 0
    else:
        payload = _load_object(source)
        if payload.get("schema_version") != "operator-review-events-v1":
            raise ValueError("invalid operator review event schema")
        events = payload.get("events")
        if not isinstance(events, list):
            raise ValueError("operator review events must be a list")
        total = len(events)
        payload = {
            "schema_version": "operator-review-events-v1",
            "events": [
                event
                for event in events
                if isinstance(event, dict)
                and str(event.get("database_relative_path") or "").startswith("no-")
            ],
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "events_total": total,
        "events_norway": len(payload["events"]),
        "events_out_of_scope_preserved_not_ingested": total - len(payload["events"]),
    }


def _legacy_review_summary(input_root: Path) -> dict[str, Any]:
    databases: list[dict[str, Any]] = []
    total = 0
    quick_checks: list[dict[str, str]] = []
    for database in sorted(input_root.glob("no-*/opportunity_engine.db")):
        with sqlite3.connect(database) as connection:
            quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            quick_checks.append(
                {"database": database.relative_to(input_root).as_posix(), "quick_check": quick}
            )
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='human_review_outcomes'"
            ).fetchone()
            count = (
                int(connection.execute("SELECT COUNT(*) FROM human_review_outcomes").fetchone()[0])
                if table is not None
                else 0
            )
        total += count
        databases.append(
            {
                "database": database.relative_to(input_root).as_posix(),
                "legacy_human_review_outcomes": count,
            }
        )
    return {
        "legacy_human_review_outcomes": total,
        "databases": databases,
        "sqlite_quick_checks": quick_checks,
    }


def run_review_cycle(
    *,
    direct_sales_path: Path,
    input_root: Path,
    output_dir: Path,
    events_path: Path = DEFAULT_EVENTS,
    config_path: str | Path = "alembic.ini",
) -> dict[str, Any]:
    direct = _load_object(direct_sales_path)
    if direct.get("scope") != "NO_ONLY_ALL_ASSETS":
        raise ValueError("direct-sales report is not Norway-only")
    cards = direct.get("cards")
    if not isinstance(cards, list):
        raise ValueError("direct-sales cards must be a list")
    captured_at = datetime.fromisoformat(str(direct["captured_at"]).replace("Z", "+00:00"))
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")

    source_dir = input_root / "no-auksjonen"
    source_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {"all_discovered_candidates": [_candidate(card) for card in cards]}
    unified = build_unified_opportunity_report(
        result,
        generated_at=captured_at,
        market_code="NO",
        currency="NOK",
        domain="GENERAL_ASSETS",
    )
    unified_path = source_dir / "unified-opportunity-report.json"
    unified_path.write_text(
        serialize_unified_opportunity_report(unified) + "\n",
        encoding="utf-8",
    )
    database = source_dir / "opportunity_engine.db"
    persistence, persistence_path = persist_unified_report_with_artifacts(
        unified_path,
        source_dir,
        database_url=f"sqlite:///{database}",
        config_path=config_path,
    )

    filtered_events_path = output_dir / "norway-operator-review-events.json"
    event_scope = _filtered_norway_events(events_path, filtered_events_path)
    ingestion = ingest_explicit_events(input_root, events_path=filtered_events_path)
    memory = export_memory(input_root)

    queue_report = {
        "generated_at": direct.get("captured_at"),
        "commercially_qualified_count": 0,
        "deduplicated_opportunities": [_queue_row(card) for card in cards],
    }
    queue = build_queue(queue_report, memory, batch_size=10)
    legacy = _legacy_review_summary(input_root)

    memory_path = output_dir / "norway-operator-study-memory.json"
    queue_path = output_dir / "norway-human-review-queue.json"
    status_path = output_dir / "norway-review-cycle-status.json"
    memory_path.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    queue_path.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = {
        "schema_version": "norway-review-cycle-1.0",
        "scope": "NO_ONLY",
        "direct_cards_persisted": persistence["persisted_record_count"],
        "unified_conversion_error_count": persistence["conversion_error_count"],
        "operator_event_scope": event_scope,
        "operator_ingestion": ingestion,
        "memory": {
            "study": len(memory["study"]),
            "later": len(memory["later"]),
            "deleted": len(memory["deleted_ids"]),
            "explicit_decision_count": memory["explicit_decision_count"],
            "audit_event_count": memory["audit_event_count"],
            "learning_review_only": memory["learning_review_only"],
        },
        "review_queue_counts": queue["counts"],
        "legacy_review_history": legacy,
        "sqlite_database": database.relative_to(input_root).as_posix(),
        "persistence_summary": persistence_path.relative_to(source_dir).as_posix(),
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_exclusion": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    status_path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-sales", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--alembic-config", default="alembic.ini")
    args = parser.parse_args()
    run_review_cycle(
        direct_sales_path=args.direct_sales,
        input_root=args.input_root,
        output_dir=args.output_dir,
        events_path=args.events,
        config_path=args.alembic_config,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
