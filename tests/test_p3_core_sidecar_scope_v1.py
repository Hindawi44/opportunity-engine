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
        "reason": "No direct core opportunity selected.",
    }
    if selected_identity:
        action = {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "reason": "Upstream selected one opportunity.",
            "opportunity_identity": selected_identity,
        }
    return {
        "generated_at": "2026-08-16T20:00:00Z",
        "market_coverage": ["NO", "SE", "DE"],
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


def test_sidecars_remain_visible_but_cannot_override_core_decision_or_paid_gate() -> None:
    italy = _signal("IT", "signal:it:sidecar", 0.99)
    norway = _signal("NO", "signal:no:core", 0.60)
    italy_direct = _direct("IT", "it:sidecar:lot")

    brief = build_domain_market_intelligence_brief(
        _checkpoint(italy_direct, selected_identity="it:sidecar:lot"),
        _persistence(italy, norway),
    )

    assert {item["signal_id"] for item in brief["early_signals_to_watch"]} == {
        "signal:it:sidecar",
        "signal:no:core",
    }
    assert [item["opportunity_identity"] for item in brief["current_direct_opportunities"]] == [
        "it:sidecar:lot"
    ]
    assert brief["selected_human_action"]["signal_id"] == "signal:no:core"
    assert brief["selected_human_action"]["opportunity_identity"] is None

    scope = brief["decision_scope"]
    assert scope["mode"] == "CORE_ONLY_WITH_SIDECAR_OBSERVATORY"
    assert scope["core_markets"] == ["NO", "SE", "DE"]
    assert scope["known_sidecar_markets"] == ["IT", "NL", "FR"]
    assert scope["observed_sidecar_markets"] == ["IT"]
    assert scope["sidecar_records_retained"] is True
    assert scope["sidecars_drive_selected_human_action"] is False
    assert scope["sidecars_trigger_paid_targeted_enrichment"] is False
    assert scope["promotion_mode"] == "EXPLICIT_POLICY_CHANGE_ONLY"

    assert brief["counts"]["core_early_signals_to_watch"] == 1
    assert brief["counts"]["sidecar_early_signals_to_watch"] == 1
    assert brief["counts"]["core_direct_opportunities"] == 0
    assert brief["counts"]["sidecar_direct_opportunities"] == 1

    assert SUPPORTED_MARKETS == set(CORE_MARKETS)
    paid_candidates = select_hunt_signals(brief, max_signals=10)
    assert [item["signal_id"] for item in paid_candidates] == ["signal:no:core"]


def test_sidecar_only_data_is_observatory_evidence_not_a_daily_action() -> None:
    france = _signal("FR", "signal:fr:sidecar", 0.95)
    france_direct = _direct("FR", "fr:sidecar:lot")

    brief = build_domain_market_intelligence_brief(
        _checkpoint(france_direct, selected_identity="fr:sidecar:lot"),
        _persistence(france),
    )

    assert brief["selected_human_action"]["action"] == "NO_IMMEDIATE_ACTION"
    assert brief["selected_human_action"]["opportunity_identity"] is None
    assert brief["selected_human_action"]["signal_id"] is None
    assert brief["counts"]["sidecar_early_signals_to_watch"] == 1
    assert brief["counts"]["sidecar_direct_opportunities"] == 1
    assert brief["decision_scope"]["observed_sidecar_markets"] == ["FR"]
    assert select_hunt_signals(brief, max_signals=10) == []
