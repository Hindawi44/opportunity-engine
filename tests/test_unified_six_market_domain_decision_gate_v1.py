from __future__ import annotations

from opportunity_engine.discovery.domain_market_intelligence_feed import (
    build_domain_market_intelligence_brief,
)


SIX_MARKETS = ["NO", "SE", "DE", "FR", "IT", "NL"]


def _checkpoint(*, next_human_action: dict | None = None, opportunities: list[dict] | None = None) -> dict:
    return {
        "generated_at": "2026-08-23T11:30:00Z",
        "market_coverage": list(SIX_MARKETS),
        "sources": [
            {
                "market_code": market,
                "source_name": f"{market} source",
                "execution_status": "SUCCESS",
                "persistence_status": "SUCCESS",
            }
            for market in SIX_MARKETS
        ],
        "deduplicated_opportunities": list(opportunities or []),
        "next_human_action": next_human_action
        or {
            "action": "NO_IMMEDIATE_ACTION",
            "reason": "No direct opportunity selected upstream.",
        },
    }


def _closure_signal(market: str) -> dict:
    return {
        "signal_id": f"closure:{market}:example",
        "signal_type": "BUSINESS_CLOSURE",
        "value": "Business closure with possible clothing inventory release.",
        "source": f"{market} source",
        "observed_at": "2026-08-23T11:30:00Z",
        "confidence": 0.9,
        "source_country": market,
        "source_url": f"https://example.test/{market.lower()}/closure",
        "title": f"{market} clothing business closure",
        "company_name": f"Example {market}",
        "seller_name": None,
        "location": None,
        "first_observed_at": "2026-08-23T11:30:00Z",
        "latest_observed_at": "2026-08-23T11:30:00Z",
        "event_date": None,
        "evidence": [],
        "related_opportunity_id": None,
        "status": "WATCH",
        "metadata": {"signal_only": True},
    }


def _persistence(*signals: dict) -> dict:
    return {
        "current_signals": list(signals),
        "created_signal_ids": [signal["signal_id"] for signal in signals],
        "changed_signal_ids": [],
    }


def test_all_six_markets_share_one_domain_decision_scope() -> None:
    brief = build_domain_market_intelligence_brief(
        _checkpoint(),
        _persistence(_closure_signal("FR")),
    )

    assert brief["decision_scope"]["mode"] == "UNIFIED_SIX_MARKET_DECISION_GATE"
    assert brief["decision_scope"]["decision_markets"] == SIX_MARKETS
    assert brief["decision_scope"]["observatory_markets"] == []
    assert brief["decision_scope"]["all_supported_markets_share_decision_gate"] is True

    # A valid French market signal must be able to drive the same human decision
    # as an equivalent Norwegian, Swedish, or German signal.
    assert brief["selected_human_action"]["action"] == "MONITOR_INVENTORY_RELEASE"
    assert brief["selected_human_action"]["signal_id"] == "closure:FR:example"


def test_existing_italian_human_action_is_not_rejected_by_market_tier() -> None:
    opportunity = {
        "opportunity_identity": "it:exact-lot:1",
        "title": "Verified Italian clothing stock lot",
        "market_code": "IT",
        "source_name": "Example IT source",
        "source_url": "https://example.test/it/lot/1",
        "workflow_status": "REQUIRES_VERIFICATION",
        "listing_status": "ACTIVE",
        "analysis_eligible": False,
        "top5_eligible": True,
        "missing_information": ["landed_cost"],
    }
    checkpoint = _checkpoint(
        opportunities=[opportunity],
        next_human_action={
            "action": "REVIEW_ONE_OPPORTUNITY",
            "reason": "Review the verified lot before commercial qualification.",
            "market_code": "IT",
            "opportunity_identity": "it:exact-lot:1",
        },
    )

    brief = build_domain_market_intelligence_brief(checkpoint, _persistence())

    assert brief["selected_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert brief["selected_human_action"]["opportunity_identity"] == "it:exact-lot:1"
    assert brief["automatic_contact"] is False
    assert brief["automatic_bid"] is False
    assert brief["automatic_purchase"] is False
    assert brief["automatic_payment"] is False
