#!/usr/bin/env python3
"""Adapt the bounded Norway cross-source verifier to checkpoint source artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _read_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected JSON list: {path}")
    return [dict(item) for item in payload if isinstance(item, dict)]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _normalize_candidate(item: dict[str, Any]) -> dict[str, Any]:
    record = dict(item)
    source_channel = str(record.get("source_channel") or "")
    if source_channel == "KONKURS_APP_AUKSJONEN_EXACT_ORGNR":
        score = 100
    elif source_channel == "VAREAUKSJONEN_DIRECT_ACTIVE_LOT":
        score = 96
    elif source_channel == "AUKSJONER_NO_CURRENT_ACTIVE_LOT":
        score = 94
    else:
        score = 90
    record.setdefault("discovery_score", score)
    record.setdefault("opportunity_state", "ACTIVE_OPPORTUNITY")
    record.setdefault("workflow_status", "REQUIRES_VERIFICATION")
    record.setdefault("evaluation_status", "REQUIRES_VERIFICATION")
    record.setdefault("currency", "NOK")
    record.setdefault("automatic_contact", False)
    record.setdefault("automatic_bid", False)
    record.setdefault("automatic_purchase_decision", False)
    record.setdefault("automatic_payment", False)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--max-bankruptcy-leads", type=int, default=40)
    parser.add_argument("--max-detail-pages", type=int, default=5)
    parser.add_argument("--max-vareauksjonen-details", type=int, default=5)
    parser.add_argument("--max-auksjoner-no-auctions", type=int, default=25)
    args = parser.parse_args()

    if not 1 <= args.max_bankruptcy_leads <= 100:
        raise ValueError("max-bankruptcy-leads must be between 1 and 100")
    if not 1 <= args.max_detail_pages <= 10:
        raise ValueError("max-detail-pages must be between 1 and 10")
    if not 1 <= args.max_vareauksjonen_details <= 10:
        raise ValueError("max-vareauksjonen-details must be between 1 and 10")
    if not 1 <= args.max_auksjoner_no_auctions <= 50:
        raise ValueError("max-auksjoner-no-auctions must be between 1 and 50")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "scripts/run_cross_source_clothing_verification.py",
        "--output-dir",
        str(args.output_dir),
        "--lookback-days",
        str(args.lookback_days),
        "--max-bankruptcy-leads",
        str(args.max_bankruptcy_leads),
        "--max-detail-pages",
        str(args.max_detail_pages),
        "--max-vareauksjonen-details",
        str(args.max_vareauksjonen_details),
        "--max-auksjoner-no-auctions",
        str(args.max_auksjoner_no_auctions),
    ]
    completed = subprocess.run(command, check=False)

    live_report_path = args.output_dir / "multi-source-live-report.json"
    top5_path = args.output_dir / "live-clothing-top5.json"
    if not live_report_path.exists() or not top5_path.exists():
        return completed.returncode or 2

    live_report = _read_object(live_report_path)
    top5 = [_normalize_candidate(item) for item in _read_list(top5_path)]
    scan_complete = bool(live_report.get("scan_complete"))
    error_count = int(live_report.get("errors") or 0)
    status = "PASS" if scan_complete and error_count == 0 and completed.returncode == 0 else "FAILED"

    report = {
        "schema_version": "checkpoint-cross-source-no-1.0",
        "status": status,
        "market_code": "NO",
        "currency": "NOK",
        "source_mode": "NORWAY_CROSS_SOURCE_VERIFICATION",
        "source_target": "KONKURS_APP_AUKSJONEN_VAREAUKSJONEN_AUKSJONER_NO",
        "scan_complete": scan_complete,
        "source_report": "multi-source-live-report.json",
        "record_count": len(top5),
        "commercial_top5_count": len(top5),
        "errors": error_count,
        "paid_search_used": False,
        "openai_api_used": False,
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_json(args.output_dir / "search-run-report.json", report)
    _write_json(args.output_dir / "all-discovered-candidates.json", top5)
    _write_json(args.output_dir / "discovery-top5.json", top5)

    print("checkpoint_cross_source_status:", status)
    print("checkpoint_cross_source_records:", len(top5))
    print("paid_search_used: false")
    print("openai_api_used: false")
    return 0 if status == "PASS" else (completed.returncode or 2)


if __name__ == "__main__":
    raise SystemExit(main())
