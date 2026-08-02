from opportunity_engine.opportunity_lifecycle import (
    LifecycleReasonCode,
    classify_opportunity_lifecycle,
)


def test_reason_code_is_stable_string_value():
    decision = classify_opportunity_lifecycle(
        {
            "listing_status": "UNKNOWN",
            "opportunity_state": "",
            "top5_eligible": False,
            "analysis_eligible": False,
            "verification": [],
        }
    )

    assert decision.reason_code == LifecycleReasonCode.NEW_CANDIDATE
    assert decision.reason_code.value == "NEW_CANDIDATE"
