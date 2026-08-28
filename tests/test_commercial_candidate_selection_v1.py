import pytest

from opportunity_engine.discovery.commercial_candidate_selection_v1 import (
    select_eligible_commercial_analysis,
)
from opportunity_engine.discovery.one_opportunity_commercial_analysis import CommercialInputError
from opportunity_engine.discovery.one_opportunity_daily_analysis import build_daily_analysis


FIRST = "https://example.test/coveralls"
SECOND = "https://example.test/shoes-3600"


def _checkpoint() -> dict:
    return {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": FIRST,
                "title": "50 coveralls",
                "market_code": "NO",
                "source_names": ["Auksjonen.no"],
                "source_urls": [FIRST],
                "listing_status": "ACTIVE",
                "workflow_status": "ACTIVE_OPPORTUNITY",
                "analysis_eligible": True,
                "top5_eligible": True,
                "discovery_score": 0.0,
            },
            {
                "opportunity_identity": SECOND,
                "title": "Sko Parti på 3600 par",
                "market_code": "NO",
                "source_names": ["Auksjonen.no"],
                "source_urls": [SECOND],
                "listing_status": "ACTIVE",
                "workflow_status": "ACTIVE_OPPORTUNITY",
                "analysis_eligible": True,
                "top5_eligible": True,
                "discovery_score": 0.0,
            },
        ],
        "next_human_action": {"opportunity_identity": FIRST},
    }


def test_manual_override_can_select_second_existing_eligible_candidate() -> None:
    checkpoint = _checkpoint()
    daily = build_daily_analysis(checkpoint)
    assert daily["selected_opportunity"]["opportunity_identity"] == FIRST

    report = select_eligible_commercial_analysis(
        daily,
        checkpoint,
        opportunity_identity=SECOND,
    )

    assert report["selected_opportunity"]["opportunity_identity"] == SECOND
    assert report["selection_reason"] == "MANUAL_ELIGIBLE_CANDIDATE_OVERRIDE"
    assert report["known_facts"]["title"] == "Sko Parti på 3600 par"
    assert report["known_facts"]["source_url"] == SECOND
    selection = report["commercial_candidate_selection"]
    assert selection["checkpoint_eligibility_verified"] is True
    assert selection["search_requests_made"] == 0
    assert selection["page_fetches_made"] == 0
    assert report["automatic_purchase"] is False
    assert report["automatic_bid"] is False


def test_current_daily_selection_is_preserved_without_override_rebuild() -> None:
    checkpoint = _checkpoint()
    daily = build_daily_analysis(checkpoint)
    report = select_eligible_commercial_analysis(
        daily,
        checkpoint,
        opportunity_identity=FIRST,
    )

    assert report["selected_opportunity"]["opportunity_identity"] == FIRST
    assert report["commercial_candidate_selection"]["selection_mode"] == "CURRENT_DAILY_SELECTION"


def test_unknown_identity_is_rejected_fail_closed() -> None:
    checkpoint = _checkpoint()
    daily = build_daily_analysis(checkpoint)
    with pytest.raises(CommercialInputError, match="not an active analysis-eligible"):
        select_eligible_commercial_analysis(
            daily,
            checkpoint,
            opportunity_identity="https://outside.example/unknown",
        )


def test_inactive_or_noneligible_candidate_is_rejected() -> None:
    checkpoint = _checkpoint()
    checkpoint["deduplicated_opportunities"][1]["analysis_eligible"] = False
    daily = build_daily_analysis(checkpoint)
    with pytest.raises(CommercialInputError, match="not an active analysis-eligible"):
        select_eligible_commercial_analysis(
            daily,
            checkpoint,
            opportunity_identity=SECOND,
        )
