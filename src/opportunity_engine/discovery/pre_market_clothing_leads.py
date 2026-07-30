"""Conservative pre-market review queue for clothing bankruptcy leads.

The pilot ranks already-collected Konkurs.app clothing bankruptcy leads using
company-level signals only. The score is a review-priority heuristic, not a
verified inventory probability and not evidence that stock is for sale.

No personal data, browser automation, paid search, AI API, seller contact, bid,
purchase, reservation, payment, or automatic investment decision is added.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    KonkursAppClothingCollection,
    KonkursAppClothingLead,
)

DEFAULT_REVIEW_LIMIT = 5
MAX_REVIEW_LIMIT = 20


def _opened_age_days(opened_date: str | None, *, today: date) -> int | None:
    if not opened_date:
        return None
    try:
        opened = date.fromisoformat(opened_date)
    except ValueError:
        return None
    return max(0, (today - opened).days)


def _financial_signal_points(
    value: float | None,
    thresholds: tuple[tuple[float, int], ...],
) -> int:
    if value is None:
        return 0
    for threshold, points in thresholds:
        if value >= threshold:
            return points
    return 0


def score_pre_market_lead(
    lead: KonkursAppClothingLead,
    *,
    today: date | None = None,
) -> tuple[int, dict[str, int], tuple[str, ...]]:
    """Return a bounded review-priority score and its explicit evidence basis."""
    today = today or datetime.now(timezone.utc).date()
    breakdown: dict[str, int] = {}
    reasons: list[str] = []

    age_days = _opened_age_days(lead.opened_date, today=today)
    if age_days is None:
        breakdown["recency"] = 0
        reasons.append("bankruptcy opening date unavailable")
    elif age_days <= 30:
        breakdown["recency"] = 30
        reasons.append("bankruptcy opened within 30 days")
    elif age_days <= 90:
        breakdown["recency"] = 20
        reasons.append("bankruptcy opened within 90 days")
    elif age_days <= 180:
        breakdown["recency"] = 10
        reasons.append("bankruptcy opened within 180 days")
    else:
        breakdown["recency"] = 0
        breakdown["stale_lead_penalty"] = -30
        reasons.append("bankruptcy is older than 180 days and is stale for early access")

    if lead.industry_code == "46.420":
        breakdown["industry"] = 25
        reasons.append("clothing and footwear wholesale industry")
    else:
        breakdown["industry"] = 15
        reasons.append("clothing retail industry")

    breakdown["mva_registration"] = 10 if lead.mva_registered else 0
    if lead.mva_registered:
        reasons.append("company was MVA registered")

    breakdown["asset_scale"] = _financial_signal_points(
        lead.total_assets,
        ((10_000_000, 20), (2_000_000, 12), (500_000, 5)),
    )
    if breakdown["asset_scale"]:
        reasons.append("reported assets add company-scale evidence")

    breakdown["revenue_scale"] = _financial_signal_points(
        lead.revenue,
        ((10_000_000, 15), (2_000_000, 8), (1, 3)),
    )
    if breakdown["revenue_scale"]:
        reasons.append("reported revenue adds trading-activity evidence")

    score = max(0, min(sum(breakdown.values()), 100))
    return score, breakdown, tuple(reasons)


def signal_band(score: int) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True, slots=True)
class PreMarketClothingLead:
    source_lead: KonkursAppClothingLead
    inventory_signal_score: int
    inventory_signal_band: str
    score_breakdown: Mapping[str, int]
    score_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        lead = self.source_lead
        return {
            "estate_orgnr": lead.estate_orgnr,
            "estate_name": lead.estate_name,
            "debtor_name": lead.debtor_name,
            "url": lead.url,
            "opened_date": lead.opened_date,
            "registered_date": lead.registered_date,
            "industry_code": lead.industry_code,
            "industry_description": lead.industry_description,
            "municipality": lead.municipality,
            "postal_place": lead.postal_place,
            "mva_registered": lead.mva_registered,
            "accounting_year": lead.accounting_year,
            "accounting_currency": lead.accounting_currency,
            "revenue": lead.revenue,
            "total_assets": lead.total_assets,
            "total_debt": lead.total_debt,
            "inventory_signal_score": self.inventory_signal_score,
            "inventory_signal_band": self.inventory_signal_band,
            "score_breakdown": dict(self.score_breakdown),
            "score_reasons": list(self.score_reasons),
            "score_basis": (
                "HEURISTIC_COMPANY_SIGNAL_NOT_VERIFIED_INVENTORY_PROBABILITY"
            ),
            "lead_stage": "PRE_MARKET_LEAD",
            "opportunity_state": (
                "EARLY_LEAD_REQUIRES_INVENTORY_AND_SALE_VERIFICATION"
            ),
            "listing_status": "UNKNOWN",
            "public_sale_found": False,
            "inventory_sale_verified": False,
            "inventory_quantity_verified": False,
            "estate_manager_identified": False,
            "liquidation_channel_identified": False,
            "operator_review_required": True,
            "top5_eligible": False,
            "analysis_eligible": False,
            "person_data_retained": False,
            "source": lead.source,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


@dataclass(frozen=True, slots=True)
class PreMarketClothingPilotResult:
    captured_at: str
    source_from_date: str
    items_received: int
    leads: tuple[PreMarketClothingLead, ...]
    review_limit: int
    scan_complete: bool
    errors: tuple[dict[str, str], ...] = ()

    @property
    def review_top(self) -> tuple[PreMarketClothingLead, ...]:
        return self.leads[: self.review_limit]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "pre-market-clothing-leads-pilot-1.0",
            "captured_at": self.captured_at,
            "source_from_date": self.source_from_date,
            "items_received": self.items_received,
            "lead_count": len(self.leads),
            "review_top_count": len(self.review_top),
            "commercial_top5_count": 0,
            "scan_complete": self.scan_complete,
            "leads": [lead.to_dict() for lead in self.leads],
            "errors": list(self.errors),
            "score_is_verified_probability": False,
            "paid_search_used": False,
            "openai_api_used": False,
            "playwright_used": False,
            "person_data_retained": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def build_pre_market_pilot(
    collection: KonkursAppClothingCollection,
    *,
    review_limit: int = DEFAULT_REVIEW_LIMIT,
    today: date | None = None,
) -> PreMarketClothingPilotResult:
    if not 1 <= review_limit <= MAX_REVIEW_LIMIT:
        raise ValueError(f"review_limit must be between 1 and {MAX_REVIEW_LIMIT}")
    today = today or datetime.now(timezone.utc).date()

    ranked: list[PreMarketClothingLead] = []
    for source_lead in collection.leads:
        score, breakdown, reasons = score_pre_market_lead(source_lead, today=today)
        ranked.append(
            PreMarketClothingLead(
                source_lead=source_lead,
                inventory_signal_score=score,
                inventory_signal_band=signal_band(score),
                score_breakdown=breakdown,
                score_reasons=reasons,
            )
        )

    def sort_key(item: PreMarketClothingLead) -> tuple[int, int, str]:
        opened = item.source_lead.opened_date
        try:
            opened_ordinal = date.fromisoformat(opened).toordinal() if opened else 0
        except ValueError:
            opened_ordinal = 0
        return (
            -item.inventory_signal_score,
            -opened_ordinal,
            item.source_lead.estate_orgnr,
        )

    ranked.sort(key=sort_key)
    return PreMarketClothingPilotResult(
        captured_at=collection.captured_at,
        source_from_date=collection.from_date,
        items_received=collection.items_received,
        leads=tuple(ranked),
        review_limit=review_limit,
        scan_complete=collection.scan_complete,
        errors=collection.errors,
    )


def write_pre_market_artifacts(
    result: PreMarketClothingPilotResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "pre-market-clothing-leads.json"
    review_top_path = target / "pre-market-leads-top5.json"
    commercial_top5_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    report_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    review_top_path.write_text(
        json.dumps(
            [lead.to_dict() for lead in result.review_top],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commercial_top5_path.write_text("[]\n", encoding="utf-8")

    lines = [
        "Pre-market clothing bankruptcy lead pilot",
        f"Lookback from: {result.source_from_date}",
        f"Items received: {result.items_received}",
        f"Pre-market leads ranked: {len(result.leads)}",
        f"Review queue count: {len(result.review_top)}",
        "Verified inventory sales: 0",
        "Commercial Top 5 count: 0",
        f"Scan complete: {result.scan_complete}",
        f"Errors: {len(result.errors)}",
        "Score type: heuristic company signal, not verified inventory probability",
        "Automatic contact/bid/purchase/payment: false",
        "",
    ]
    if result.review_top:
        lines.append("Highest-priority pre-market leads requiring human review:")
        for lead in result.review_top:
            source = lead.source_lead
            lines.append(
                f"- {source.debtor_name} | {source.municipality or 'unknown'} | "
                f"opened {source.opened_date or 'unknown'} | "
                f"signal {lead.inventory_signal_score}/100 "
                f"({lead.inventory_signal_band}) | {source.url}"
            )
    else:
        lines.append("No recent clothing bankruptcy leads were available for review.")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "review_top": review_top_path,
        "commercial_top5": commercial_top5_path,
        "summary": summary_path,
    }
