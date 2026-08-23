from __future__ import annotations

from opportunity_engine.discovery.domain_market_intelligence_feed import (
    CORE_MARKETS,
    KNOWN_SIDECAR_MARKETS,
    build_domain_market_intelligence_brief,
)
from opportunity_engine.discovery.openai_hunt_case_enrichment import (
    SUPPORTED_MARKETS,
    select_hunt_signals,
)


def _signal(country: str, signal_id: str, confidence: float) -> dict:
    return {
        "signal_id": signal_id,
        "signal_type": "INSOLVENCY_OR_LIQUIDATION",
        "value": f"{country} clothing insolvency signal",
        "source": "Scope test source",
        "observed_at": "2026-08-16T20:00:00Z",
        "confidence": confidence,
        "source_country": country,
        "source_url": f"https://example.test/{country.casefold()}/signal",
        "title": f"{country} clothing insolvency",
        "company_name": f"{country} Fashion Example",
        "seller_name": None,
        "location": "Example",
        "first_observed_at": "2026-08-16T20:00:00Z",
        "latest_observed_at": "2026-08-16T20:00:00Z",
        "event_date": None,
        "evidence": [],
        "related_opportunity_id": None,
        "status": "WATCH",
        "metadata": {"signal_only": True},
    }


def _direct(country: str, identity: str) -> dict:
    return {
        "opportunity_identity": identity,
        "title": f"{country} clothing inventory lot",
        "market_code": country,
        "source_name": "Scope test auction",
        "source_url": f"https://example.test/{country.casefold()}/lot",
        "workflow_status": "ACTIVE_OPPORTUNITY",
        "listing_status": "ACTIVE",
        "discovery_score": 90,
        "location": "Example",
        "quantity": 100,
        "analysis_eligible": True,
        "top5_eligible": True,
        "missing_information": [],
    }


def _checkpoint(*direct: dict, selected_identity: str | None = None) -> dict:
    action = {
        "action": "NO_IMMEDIATE_ACTION",
        "reason": "No direct opportunity selected.",
    }
    if selected_identity:
        action = {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "reason": "Upstream selected one opportunity.",
            "opportunity_identity": selected_identity,
        }
    return {
        "generated_at": "2026-08-16T20:00:00Z",
        "market_coverage": ["NO", "SE", "DE", "FR", "IT", "NL"],
        "sources": [],
        "deduplicated_opportunities": list(direct),
        "next_human_action": action,
    }


def _persistence(*signals: dict) -> dict:
    ids = [signal["signal_id"] for signal in signals]
    return {
        "current_signals": list(signals),
        "created_signal_ids": ids,
        "changed_signal_ids": [],
    }


def test_source_tiers_do_not_limit_decision_gate_or_change_paid_enrichment_gate() -> None:
    italy = _signal("IT", "signal:it:source-tier", 0.99)
    norway = _signal("NO", "signal:no:core", 0.60)
    italy_direct = _direct("IT", "it:source-tier:lot")

    brief = build_domain_market_intelligence_brief(
        _checkpoint(italy_direct, selected_identity="it:source-tier:lot"),
        _persistence(italy, norway),
    )

    assert {item["signal_id"] for item in brief["early_signals_to_watch"]} == {
        "signal:it:source-tier",
        "signal:no:core",
    }
    assert [item["opportunity_identity"] for item in brief["current_direct_opportunities"]] == [
        "it:source-tier:lot"
    ]
    assert brief["selected_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert brief["selected_human_action"]["opportunity_identity"] == "it:source-tier:lot"
    assert brief["selected_human_action"]["signal_id"] is None

    scope = brief["decision_scope"]
    assert scope["mode"] == "UNIFIED_SIX_MARKET_DECISION_GATE"
    assert scope["decision_markets"] == ["NO", "SE", "DE", "FR", "IT", "NL"]
    assert scope["observatory_markets"] == []
    assert scope["all_supported_markets_share_decision_gate"] is True
    assert scope["core_markets"] == ["NO", "SE", "DE"]
    assert scope["known_sidecar_markets"] == ["FR", "IT", "NL"]
    assert scope["observed_sidecar_markets"] == ["IT"]
    assert scope["sidecar_records_retained"] is True
    assert scope["sidecars_drive_selected_human_action"] is True
    assert scope["sidecars_trigger_paid_targeted_enrichment"] is False
    assert scope["promotion_mode"] == "NOT_REQUIRED_UNIFIED_DECISION_SCOPE"
    assert scope["source_tiers_affect_decision_eligibility"] is False

    assert brief["counts"]["core_early_signals_to_watch"] == 1
    assert brief["counts"]["sidecar_early_signals_to_watch"] == 1
    assert brief["counts"]["core_direct_opportunities"] == 0
    assert brief["counts"]["sidecar_direct_opportunities"] == 1

    # Paid targeted enrichment is a separate cost-control gate. This change only
    # unifies decision eligibility and must not silently expand paid enrichment.
    assert SUPPORTED_MARKETS == set(CORE_MARKETS)
    paid_candidates = select_hunt_signals(brief, max_signals=10)
    assert [item["signal_id"] for item in paid_candidates] == ["signal:no:core"]


def test_source_tier_market_can_drive_daily_action_without_expanding_paid_enrichment() -> None:
    france = _signal("FR", "signal:fr:source-tier", 0.95)
    france_direct = _direct("FR", "fr:source-tier:lot")

    brief = build_domain_market_intelligence_brief(
        _checkpoint(france_direct, selected_identity="fr:source-tier:lot"),
        _persistence(france),
    )

    assert brief["selected_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert brief["selected_human_action"]["opportunity_identity"] == "fr:source-tier:lot"
    assert brief["selected_human_action"]["signal_id"] is None
    assert brief["counts"]["sidecar_early_signals_to_watch"] == 1
    assert brief["counts"]["sidecar_direct_opportunities"] == 1
    assert brief["decision_scope"]["observed_sidecar_markets"] == ["FR"]
    assert brief["decision_scope"]["observatory_markets"] == []
    assert brief["decision_scope"]["source_tiers_affect_decision_eligibility"] is False
    assert select_hunt_signals(brief, max_signals=10) == []
