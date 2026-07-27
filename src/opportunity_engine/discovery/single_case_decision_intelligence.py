"""Bridge one Clothing Inventory report into the existing scoring and decision engines.

The bridge does not define new thresholds. It adapts the traceable single-case report
into the public scoring contract and the existing canonical decision policy. Missing
financial evidence remains missing, BUY_REVIEW always requires human approval, and no
automatic commercial action is enabled.
"""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Any, Callable


def _existing_engines() -> tuple[
    Callable[..., dict[str, object]],
    Callable[[dict[str, object]], dict[str, object]],
]:
    """Load the repository's existing script-level engines in package or CLI mode."""
    try:
        scoring = import_module("scripts.build_scored_opportunities")
        decisions = import_module("scripts.build_decision_intelligence")
    except ModuleNotFoundError:
        scoring = import_module("build_scored_opportunities")
        decisions = import_module("build_decision_intelligence")

    score = getattr(scoring, "score_opportunity", None)
    decide = getattr(decisions, "_decision", None)
    if not callable(score) or not callable(decide):
        raise RuntimeError("existing scoring or decision engine is unavailable")
    return score, decide


def _asking_price(report: dict[str, Any]) -> float | None:
    dossier = report.get("dossier")
    if isinstance(dossier, dict):
        seller_claims = dossier.get("seller_claims")
        if isinstance(seller_claims, dict):
            value = seller_claims.get("asking_price_nok")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)

    costs = report.get("acquisition_cost_evidence")
    accepted = costs.get("accepted", []) if isinstance(costs, dict) else []
    if isinstance(accepted, list):
        for item in accepted:
            if not isinstance(item, dict) or item.get("financial_field") != "auction_price_nok":
                continue
            value = item.get("amount_nok")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _listing_input(report: dict[str, Any]) -> dict[str, object]:
    dossier = report.get("dossier")
    if not isinstance(dossier, dict):
        raise ValueError("single-case report is missing dossier data")
    confirmed = dossier.get("confirmed_facts")
    if not isinstance(confirmed, dict):
        raise ValueError("single-case dossier is missing confirmed facts")

    return {
        "opportunity_id": str(
            dossier.get("opportunity_id") or "clothing-inventory-single-case"
        ),
        "title": str(
            confirmed.get("source_title") or "Clothing Inventory opportunity"
        ),
        "description": str(confirmed.get("source_text") or ""),
        "asking_price_nok": _asking_price(report),
        "city": confirmed.get("location"),
        "source": confirmed.get("source_name"),
        "source_name": confirmed.get("source_name"),
        "url": confirmed.get("source_url"),
    }


def _evaluation_input(report: dict[str, Any]) -> dict[str, object]:
    financial = report.get("financial_integration")
    financial = financial if isinstance(financial, dict) else {}
    eligibility = report.get("eligibility")
    eligibility = eligibility if isinstance(eligibility, dict) else {}
    market = report.get("market_comparables")
    market = market if isinstance(market, dict) else {}

    raw_missing = financial.get("missing_required_evidence")
    if isinstance(raw_missing, (list, tuple)):
        missing = [str(item) for item in raw_missing]
    else:
        raw_missing = eligibility.get("missing_requirements")
        missing = (
            [str(item) for item in raw_missing]
            if isinstance(raw_missing, (list, tuple))
            else []
        )

    accepted = market.get("accepted", [])
    market_prices = (
        [
            item.get("price_nok")
            for item in accepted
            if isinstance(item, dict)
            and isinstance(item.get("price_nok"), (int, float))
            and not isinstance(item.get("price_nok"), bool)
        ]
        if isinstance(accepted, list)
        else []
    )

    ready = financial.get("decision_gate") == "READY_FOR_FINANCIAL_REVIEW"
    return {
        "decision": "REVIEW_NUMBERS" if ready else "EVIDENCE_REQUIRED",
        "total_cost_nok": financial.get("true_acquisition_cost_nok"),
        "conservative_resale_value_nok": financial.get(
            "conservative_resale_value_nok"
        ),
        "expected_profit_nok": financial.get("expected_profit_nok"),
        "roi_percent": financial.get("roi_percent"),
        "missing_evidence": missing,
        "evidence": {"market_comparables_nok": market_prices},
    }


def apply_existing_scoring_and_decision(
    report: dict[str, Any],
) -> dict[str, Any]:
    """Run existing scoring and canonical decision policy without changing thresholds."""
    enriched = deepcopy(report)
    score_opportunity, decide = _existing_engines()
    scored = score_opportunity(_listing_input(enriched), _evaluation_input(enriched))
    decision = decide(scored)

    enriched["decision_intelligence"] = decision
    enriched["decision_invoked"] = True
    enriched["opportunity_score"] = decision.get("opportunity_score")
    enriched["score_grade"] = decision.get("score_grade")
    enriched["final_decision"] = decision.get("final_decision")
    enriched["final_decision_ar"] = decision.get("final_decision_ar")
    enriched["maximum_safe_bid_nok"] = decision.get("maximum_safe_bid_nok")
    enriched["requires_human_approval"] = bool(
        decision.get("requires_human_approval")
    )
    enriched["automatic_purchase_decision"] = False
    enriched["automatic_bid"] = False
    enriched["automatic_contact"] = False
    enriched["automatic_payment"] = False
    return enriched
