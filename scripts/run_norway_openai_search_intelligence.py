#!/usr/bin/env python3
"""Run the existing bounded OpenAI hunt analysis over current Norwegian source reports only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

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
BANKRUPTCY_HUNT_SCHEMA = "norway-bankruptcy-link-hunt-1.0"
BANKRUPTCY_HUNT_SCOPE = "NO_ONLY_OFFICIAL_BANKRUPTCY_LINK_CHASE"


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


def build_bankruptcy_hunt_brief(report_path: str | Path) -> dict[str, Any]:
    """Expose only deterministically linked bankruptcy events/pages to OpenAI.

    The model remains advisory. It cannot promote a search hit, prove a link or
    make a liquidation/surplus result eligible; those decisions have already
    failed closed in the deterministic bankruptcy-link hunter.
    """
    path = Path(report_path)
    report = _load(path)
    if report.get("schema_version") != BANKRUPTCY_HUNT_SCHEMA:
        raise ValueError("Norway bankruptcy-link hunt report is required")
    if report.get("scope") != BANKRUPTCY_HUNT_SCOPE:
        raise ValueError("OpenAI bankruptcy analysis is restricted to Norway")
    rows = report.get("verified_bankruptcy_sale_links")
    if not isinstance(rows, list):
        raise ValueError("verified_bankruptcy_sale_links must be a list")
    if int(report.get("verified_bankruptcy_sale_link_count") or 0) != len(rows):
        raise ValueError("Bankruptcy-link count does not match its evidence rows")

    signals: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    sale_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid verified bankruptcy-link row")
        organisation_number = str(row.get("organisation_number") or "").strip()
        company_name = str(row.get("company_name") or "").strip()
        official_url = str(row.get("official_bankruptcy_url") or "").strip()
        sale_url = str(row.get("sale_url") or "").strip()
        sale_host = (urlsplit(sale_url).hostname or "").casefold().rstrip(".")
        if (
            row.get("classification") != "OFFICIAL_BANKRUPTCY_LINKED_ASSET_SALE"
            or row.get("event_kind") != "KONKURS"
            or len(organisation_number) != 9
            or not organisation_number.isascii()
            or not organisation_number.isdigit()
            or not company_name
            or official_url
            != "https://data.brreg.no/enhetsregisteret/api/enheter/"
            + organisation_number
            or not sale_url.startswith("https://")
            or not sale_host.endswith(".no")
            or row.get("bankruptcy_language_verified_on_page") is not True
            or row.get("sale_language_verified_on_page") is not True
            or row.get("bankruptcy_estate_sale_relationship_verified_on_page")
            is not True
            or row.get("liquidation_only") is not False
            or row.get("surplus_only") is not False
            or row.get("dealer_only") is not False
        ):
            raise ValueError("Unverified or non-bankruptcy row reached OpenAI input")

        event_id = f"bankruptcy-event:no:{organisation_number}"
        if event_id not in event_ids:
            event_ids.add(event_id)
            signals.append(
                {
                    "signal_id": event_id,
                    "signal_type": "BANKRUPTCY",
                    "source_country": "NO",
                    "source": "Brønnøysundregistrene",
                    "source_url": official_url,
                    "title": f"Official bankruptcy: {company_name}",
                    "company_name": company_name,
                    "location": str(row.get("location") or ""),
                    "status": "WATCH",
                    "confidence": 1.0,
                    "metadata": {
                        "learning_trigger": "OFFICIAL_NORWAY_BANKRUPTCY",
                        "event_kind": "KONKURS",
                        "organisation_number": organisation_number,
                    },
                }
            )
        sale_id = "bankruptcy-sale:no:" + sha256(sale_url.encode()).hexdigest()[:20]
        if sale_id in sale_ids:
            continue
        sale_ids.add(sale_id)
        signals.append(
            {
                "signal_id": sale_id,
                "signal_type": "DIRECT_OPPORTUNITY_CHANGE",
                "source_country": "NO",
                "source": str(row.get("search_provider") or sale_host),
                "source_url": sale_url,
                "title": str(row.get("sale_page_title") or "Bankruptcy asset sale"),
                "company_name": company_name,
                "location": str(row.get("location") or ""),
                "status": "WATCH",
                "confidence": 0.95,
                "metadata": {
                    "learning_trigger": "VERIFIED_NORWAY_BANKRUPTCY_SALE_LINK",
                    "event_kind": "KONKURS",
                    "organisation_number": organisation_number,
                    "identity_match_method": row.get("identity_match_method"),
                    "inventory_contents_verified": False,
                    "sale_availability_fully_verified": False,
                },
            }
        )

    generated_at = str(report.get("captured_at") or "").strip()
    if not generated_at:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "norway-bankruptcy-openai-brief-1.0",
        "generated_at": generated_at,
        "market_coverage": ["NO"],
        "source_reports_read": [str(path)],
        "early_signals_to_watch": signals,
        "new_signals_today": [],
        "changed_signals_since_previous_checkpoint": [],
        "counts": {
            "official_bankruptcy_signals": len(event_ids),
            "verified_bankruptcy_sale_link_signals": len(sale_ids),
        },
        "input_policy": "DETERMINISTIC_BANKRUPTCY_LINKS_ONLY",
        "liquidation_only_excluded": True,
        "surplus_only_excluded": True,
        "dealer_only_excluded": True,
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
    input_root: str | Path | None = None,
    bankruptcy_report: str | Path | None = None,
    output_dir: str | Path,
) -> dict[str, Any]:
    if (input_root is None) == (bankruptcy_report is None):
        raise ValueError("Choose exactly one Norway input mode")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if bankruptcy_report is not None:
        brief = build_bankruptcy_hunt_brief(bankruptcy_report)
        input_mode = "OFFICIAL_BANKRUPTCY_LINKS_ONLY"
    else:
        brief = build_norway_search_brief(input_root)  # type: ignore[arg-type]
        input_mode = "LEGACY_NORWAY_SEARCH_REPORTS"
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
        "input_mode": input_mode,
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
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input-root")
    inputs.add_argument("--bankruptcy-report")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run_norway_search_intelligence(
        input_root=args.input_root,
        bankruptcy_report=args.bankruptcy_report,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
