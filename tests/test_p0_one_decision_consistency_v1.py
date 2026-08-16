from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.central_intelligence_orchestrator import (
    build_central_intelligence_brief,
)
from opportunity_engine.discovery.domain_market_intelligence_feed import (
    build_domain_market_intelligence_brief,
)
from opportunity_engine.discovery.one_opportunity_daily_analysis import build_daily_analysis
from opportunity_engine.discovery.unified_market_intelligence_river import (
    build_unified_market_intelligence_river,
)


NOW = datetime(2026, 8, 16, 19, 30, tzinfo=timezone.utc)
BAUER_ID = "https://ny.auksjonen.no/auksjon/torget/test/bauer-jakker"
RIVAL_ID = "https://ny.auksjonen.no/auksjon/torget/test/higher-score-lot"


def _opportunity(identity: str, title: str, score: float) -> dict:
    return {
        "opportunity_identity": identity,
        "title": title,
        "market_code": "NO",
        # Match the real checkpoint projection: plural source names + canonical URL.
        "source_names": ["Auksjonen.no"],
        "canonical_url": identity,
        "listing_status": "ACTIVE",
        "workflow_status": "ACTIVE_OPPORTUNITY",
        "top5_eligible": True,
        "analysis_eligible": True,
        "discovery_score": score,
        "missing_evidence": [],
    }


def _checkpoint() -> dict:
    return {
        "generated_at": NOW.isoformat(),
        "market_coverage": ["NO", "SE", "DE"],
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "execution_status": "SUCCESS",
                "persistence_status": "NOT_ENABLED",
            }
        ],
        "deduplicated_opportunities": [
            _opportunity(BAUER_ID, "Halv pall med Bauer jakker", 80),
            # Deliberately stronger score. Central must still honour the checkpoint
            # selection rather than silently creating a second decision.
            _opportunity(RIVAL_ID, "Higher score clothing lot", 99),
        ],
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": BAUER_ID,
            "workflow_status": "ACTIVE_OPPORTUNITY",
            "reason": "Checkpoint canonical selection for operator review.",
        },
    }


def _empty_signal_persistence() -> dict:
    return {
        "current_signals": [],
        "created_signal_ids": [],
        "changed_signal_ids": [],
    }


def test_bauer_remains_the_one_decision_through_central_even_against_higher_score() -> None:
    checkpoint = _checkpoint()

    daily = build_daily_analysis(checkpoint, generated_at=NOW)
    assert daily["selection_status"] == "SELECTED"
    assert daily["selection_reason"] == "CHECKPOINT_NEXT_HUMAN_ACTION"
    assert daily["selected_opportunity"]["opportunity_identity"] == BAUER_ID
    assert daily["selected_opportunity"]["workflow_status"] == "ACTIVE_OPPORTUNITY"

    domain = build_domain_market_intelligence_brief(
        checkpoint,
        _empty_signal_persistence(),
    )
    assert domain["selected_human_action"]["opportunity_identity"] == BAUER_ID
    by_identity = {
        item["opportunity_identity"]: item
        for item in domain["current_direct_opportunities"]
    }
    assert by_identity[BAUER_ID]["source_name"] == "Auksjonen.no"
    assert by_identity[BAUER_ID]["source_url"] == BAUER_ID
    assert by_identity[BAUER_ID]["analysis_eligible"] is True
    assert by_identity[BAUER_ID]["missing_information"] == []

    river = build_unified_market_intelligence_river(
        {"domain-market-intelligence-brief.json": domain},
        generated_at=NOW,
    )
    brief = river["brief"]
    actionable = brief["actionable_now"]
    assert len(actionable) == 2
    assert {card["opportunity_identity"] for card in actionable} == {BAUER_ID, RIVAL_ID}
    assert all(card["workflow_status"] == "ACTIVE_OPPORTUNITY" for card in actionable)
    # The river is allowed to rank the higher-score case first. It is a ranking
    # projection, not a second canonical operator decision.
    assert brief["top_actionable_card"]["opportunity_identity"] == RIVAL_ID

    central = build_central_intelligence_brief(domain, brief)
    top = central["top_actionable_opportunity"]
    action = central["primary_human_action"]

    assert central["canonical_decision_truth_preserved"] is True
    assert central["checkpoint_preferred_opportunity_identity"] == BAUER_ID
    assert top["opportunity_identity"] == BAUER_ID
    assert top["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert action["opportunity_identity"] == BAUER_ID
    assert action["workflow_status"] == "ACTIVE_OPPORTUNITY"

    assert (
        checkpoint["next_human_action"]["opportunity_identity"]
        == daily["selected_opportunity"]["opportunity_identity"]
        == domain["selected_human_action"]["opportunity_identity"]
        == top["opportunity_identity"]
        == action["opportunity_identity"]
        == BAUER_ID
    )
    assert (
        checkpoint["next_human_action"]["workflow_status"]
        == daily["selected_opportunity"]["workflow_status"]
        == top["workflow_status"]
        == action["workflow_status"]
        == "ACTIVE_OPPORTUNITY"
    )
