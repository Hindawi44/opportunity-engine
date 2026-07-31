from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
)
from opportunity_engine.discovery.norway_textile_verification_orchestration import (
    apply_norway_textile_page_verification_policy,
)


def _candidate(*, query_id: str = "sale-03", status: str = ACTIVE) -> dict:
    return {
        "title": "Industrisymaskiner fra systue selges",
        "found_by_queries": [query_id],
        "top5_eligible": True,
        "discovery_score": 88,
        "source_urls": ["https://example.invalid/listing/12345"],
        "verification": [{
            "url": "https://example.invalid/listing/12345",
            "title": "Industrisymaskiner fra systue selges",
            "listing_status": status,
            "page_role": ITEM_LISTING,
            "opportunity_identity": "url-id:12345",
            "identity_stable": True,
            "clothing_inventory_evidence": True,
            "sale_evidence": True,
            "verified": True,
        }],
    }


def _result(candidate: dict) -> dict:
    return {
        "all_discovered_candidates": [candidate],
        "top5_opportunities": [candidate],
        "search_run_report": {
            "top5_count": 1,
            "top5_eligible_count": 1,
            "no_opportunities_found": False,
        },
    }


def test_accepts_active_verified_taxonomy_candidate_into_top5() -> None:
    output = apply_norway_textile_page_verification_policy(
        _result(_candidate())
    )

    candidate = output["all_discovered_candidates"][0]
    assert candidate["textile_category"] == "SEWING_MACHINERY"
    assert candidate["textile_page_verification_accepted"] is True
    assert len(output["top5_opportunities"]) == 1
    assert output["search_run_report"][
        "norway_textile_page_verification_policy_applied"
    ] is True


def test_ended_page_is_removed_from_top5_fail_closed() -> None:
    output = apply_norway_textile_page_verification_policy(
        _result(_candidate(status=ENDED))
    )

    candidate = output["all_discovered_candidates"][0]
    assert candidate["textile_page_verification_accepted"] is False
    assert candidate["top5_eligible"] is False
    assert candidate["post_verification_top5_block_reason"] == (
        "norway_textile_page_verification_failed"
    )
    assert output["top5_opportunities"] == []
    assert output["search_run_report"]["no_opportunities_found"] is True


def test_missing_verification_is_removed_from_top5() -> None:
    candidate = _candidate()
    candidate["verification"] = []

    output = apply_norway_textile_page_verification_policy(_result(candidate))

    evaluated = output["all_discovered_candidates"][0]
    assert evaluated["textile_page_verification_accepted"] is False
    assert "no completed public-page verification" in (
        evaluated["textile_page_verification"][0]["reason"]
    )
    assert output["top5_opportunities"] == []


def test_ambiguous_multi_category_candidate_fails_closed() -> None:
    candidate = _candidate()
    candidate["found_by_queries"] = ["sale-02", "sale-03"]

    output = apply_norway_textile_page_verification_policy(_result(candidate))

    evaluated = output["all_discovered_candidates"][0]
    assert evaluated["textile_category"] is None
    assert evaluated["textile_page_verification_accepted"] is False
    assert "multiple textile categories" in (
        evaluated["textile_page_verification"][0]["reason"]
    )
