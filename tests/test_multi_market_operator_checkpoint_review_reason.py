from __future__ import annotations

from scripts.run_multi_market_daily_operator_checkpoint import _correct_review_reason


def test_review_reason_does_not_overstate_verification() -> None:
    report = {
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": "no:1",
            "reason": "A verified active Top 5 eligible opportunity is available.",
        },
        "deduplicated_opportunities": [
            {
                "opportunity_identity": "no:1",
                "listing_status": "ACTIVE",
                "top5_eligible": True,
                "analysis_eligible": False,
                "missing_evidence": ["verified exact item-page evidence"],
            }
        ],
    }

    _correct_review_reason(report)

    reason = report["next_human_action"]["reason"]
    assert reason == (
        "An active Top 5 candidate requires human verification and evidence "
        "completion before analysis."
    )
    assert "verified active" not in reason.lower()


def test_review_reason_marks_analysis_ready_record_without_purchase_language() -> None:
    report = {
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": "no:2",
            "reason": "stale reason",
        },
        "deduplicated_opportunities": [
            {
                "opportunity_identity": "no:2",
                "listing_status": "ACTIVE",
                "top5_eligible": True,
                "analysis_eligible": True,
                "missing_evidence": [],
            }
        ],
    }

    _correct_review_reason(report)

    reason = report["next_human_action"]["reason"]
    assert reason == "An active Top 5 opportunity is ready for human analysis review."
    assert "buy" not in reason.lower()
    assert "bid" not in reason.lower()
