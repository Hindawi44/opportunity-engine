#!/usr/bin/env python3
"""Run the existing bounded OpenAI hunt analysis over current Norwegian source reports only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.openai_hunt_case_enrichment import (
    run_openai_hunt_case_enrichment,
    write_openai_hunt_case_artifacts,
)

SOURCE_REPORTS = (
    "no-auksjonen/unified-opportunity-report.json",
    "no-exa-exact-lot/unified-opportunity-report.json",
    "no-finn-email/unified-opportunity-report.json",
)
INACTIVE = {"ENDED", "SOLD", "UNAVAILABLE", "HISTORICAL"}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def build_norway_search_brief(input_root: str | Path) -> dict[str, Any]:
    """Convert existing current NO source records into the established hunt-signal contract."""
    root = Path(input_root)
    signals: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_reports_read: list[str] = []

    for relative in SOURCE_REPORTS:
        path = root / relative
        if not path.is_file():
            continue
        report = _load(path)
        source_reports_read.append(relative)
        records = report.get("records") or []
        if not isinstance(records, list):
            raise ValueError(f"records must be a list: {path}")
        for record in records:
            if not isinstance(record, Mapping):
                continue
            market = str(record.get("market_code") or "").strip().upper()
            if market != "NO":
                raise ValueError(
                    f"foreign record reached Norway-only OpenAI input: {market or 'UNKNOWN'}"
                )
            listing_status = str(record.get("listing_status") or "").strip().upper()
            if listing_status in INACTIVE:
                continue
            identity = str(
                record.get("opportunity_id")
                or record.get("source_url")
                or ""
            ).strip()
            url = str(record.get("source_url") or "").strip()
            if not identity or not url or identity in seen:
                continue
            seen.add(identity)
            signals.append(
                {
                    "signal_id": f"norway-search:{identity}",
                    "signal_type": "DIRECT_OPPORTUNITY_CHANGE",
                    "source_country": "NO",
                    "source": str(record.get("source_provider") or "Norway search"),
                    "source_url": url,
                    "title": str(record.get("title") or identity),
                    "company_name": str(record.get("company_name") or ""),
                    "location": str(record.get("location") or ""),
                    "status": "WATCH",
                    "confidence": 1.0 if record.get("verified") is True else 0.65,
                    "metadata": {
                        "learning_trigger": "NORWAY_SEARCH_RESULT",
                        "opportunity_id": identity,
                        "workflow_status": record.get("workflow_status"),
                        "listing_status": record.get("listing_status"),
                        "analysis_eligible": record.get("analysis_eligible") is True,
                        "top5_eligible": record.get("top5_eligible") is True,
                    },
                }
            )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "norway-search-openai-brief-1.0",
        "generated_at": now,
        "market_coverage": ["NO"],
        "source_reports_read": source_reports_read,
        "early_signals_to_watch": signals,
        # Do not claim novelty merely because a row is visible in today's report.
        "new_signals_today": [],
        "changed_signals_since_previous_checkpoint": [],
        "counts": {"norway_search_signals": len(signals)},
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def run_norway_search_intelligence(
    *,
    input_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    brief = build_norway_search_brief(input_root)
    brief_path = destination / "norway-search-openai-brief.json"
    brief_path.write_text(
        json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = run_openai_hunt_case_enrichment(brief)
    for case in report.get("cases") or []:
        if isinstance(case, Mapping) and str(case.get("market_code") or "").upper() != "NO":
            raise RuntimeError("OpenAI hunt case escaped Norway-only scope")
    report["market_scope"] = ["NO"]
    report["foreign_market_execution"] = False
    report["source_reports_read"] = brief["source_reports_read"]
    write_openai_hunt_case_artifacts(
        report,
        json_path=destination / "openai-hunt-case-enrichment.json",
        text_path=destination / "openai-hunt-case-enrichment.txt",
    )
    summary = {
        "schema_version": "norway-search-openai-summary-1.0",
        "status": report.get("status"),
        "market_scope": ["NO"],
        "input_signal_count": len(brief["early_signals_to_watch"]),
        "api_request_count": int(report.get("api_request_count") or 0),
        "estimated_cost_usd": float(report.get("estimated_cost_usd") or 0.0),
        "case_count": len(report.get("cases") or []),
        "foreign_market_execution": False,
        "automatic_query_activation": False,
        "automatic_source_promotion": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    (destination / "norway-search-openai-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run_norway_search_intelligence(
        input_root=args.input_root,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
