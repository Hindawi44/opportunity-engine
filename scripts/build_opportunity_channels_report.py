#!/usr/bin/env python3
"""Build separate actionable-sale and bankruptcy-discovery channels.

Bankruptcy records are leads for follow-up, not sale listings. They never compete
with priced auction listings and never receive invented prices, profit or ROI.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.ods.konkurs_app import KonkursAppPublicApiClient


LEAD_TERMS = {
    "butikk": 12,
    "varelager": 18,
    "butikkinnredning": 20,
    "inventar": 14,
    "møbler": 12,
    "kontor": 10,
    "tekstil": 18,
    "klær": 16,
    "søm": 16,
    "symaskin": 20,
    "lager": 10,
    "handel": 8,
}


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _lead_score(title: str, description: str, metadata: dict[str, object]) -> tuple[int, list[str]]:
    searchable = _normalize(
        " ".join(
            str(value or "")
            for value in (
                title,
                description,
                metadata.get("industry_description"),
                metadata.get("asset_type"),
            )
        )
    )
    score = 0
    reasons: list[str] = []
    for term, points in LEAD_TERMS.items():
        if term in searchable:
            score += points
            reasons.append(f"target:{term}+{points}")
    if metadata.get("city"):
        score += 5
        reasons.append("location_present+5")
    if metadata.get("organization_number"):
        score += 5
        reasons.append("organization_number_present+5")
    if metadata.get("trustee"):
        score += 5
        reasons.append("trustee_present+5")
    return min(score, 100), reasons


def _serialize_lead(document) -> dict[str, object]:
    metadata = dict(document.metadata)
    description = str(metadata.get("description") or document.text or "").strip()
    score, reasons = _lead_score(document.title, description, metadata)
    return {
        "lead_id": document.document_id,
        "channel": "bankruptcy_lead",
        "source": document.source_name,
        "title": document.title,
        "description": description or None,
        "url": document.url,
        "city": metadata.get("city"),
        "organization_number": metadata.get("organization_number"),
        "bankruptcy_date": metadata.get("bankruptcy_date"),
        "industry_code": metadata.get("industry_code"),
        "industry_description": metadata.get("industry_description"),
        "trustee": metadata.get("trustee"),
        "lead_score": score,
        "score_reasons": reasons,
        "status": "FOLLOW_UP_LEAD" if score >= 18 else "LOW_PRIORITY_LEAD",
        "asking_price_nok": None,
        "expected_profit_nok": None,
        "roi_percent": None,
        "warning": "Discovery lead only; assets and sale availability are not confirmed.",
    }


def build_payload(actionable_payload: dict[str, object], documents, limit: int = 5) -> dict[str, object]:
    actionable = actionable_payload.get("top_opportunities", [])
    if not isinstance(actionable, list):
        actionable = []

    leads = [_serialize_lead(document) for document in documents if document.source_type == "bankruptcy_discovery_lead"]
    leads.sort(key=lambda item: (-int(item["lead_score"]), str(item.get("title") or "")))
    top_leads = leads[: max(1, limit)]

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "sale listings and bankruptcy discovery leads are ranked in separate channels; no financial values are invented",
        "actionable_opportunities": {
            "candidate_count": actionable_payload.get("candidate_count", len(actionable)),
            "top_count": len(actionable),
            "items": actionable,
        },
        "bankruptcy_leads": {
            "fetched_count": len(leads),
            "top_count": len(top_leads),
            "items": top_leads,
        },
        "source_funnel": {
            "actionable_candidates": actionable_payload.get("candidate_count", len(actionable)),
            "actionable_selected": len(actionable),
            "bankruptcy_leads_fetched": len(leads),
            "bankruptcy_leads_selected": len(top_leads),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actionable", default="data/top5_opportunities.json")
    parser.add_argument("--output", default="data/opportunity_channels.json")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    actionable_path = Path(args.actionable)
    actionable_payload = json.loads(actionable_path.read_text(encoding="utf-8")) if actionable_path.exists() else {}
    documents = KonkursAppPublicApiClient(page_size=25).fetch()
    payload = build_payload(actionable_payload, documents, limit=args.limit)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "actionable_top_count": payload["actionable_opportunities"]["top_count"],
        "bankruptcy_top_count": payload["bankruptcy_leads"]["top_count"],
        "output": str(output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
