from __future__ import annotations

from typing import Any

from opportunity_engine.discovery.hunt_case_targeted_followup import (
    attach_targeted_followup_intelligence,
    render_hunt_case_targeted_followup,
    run_hunt_case_targeted_followup,
    select_targeted_hunt_cases,
)
from opportunity_engine.discovery.search_provider import SearchHit


def _case(index: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hunt_case_id": f"hunt:no:{index}",
        "case_title": f"Example Fashion case {index}",
        "market_code": "NO",
        "normalized_company_name": "Example Fashion AS",
        "organisation_number": "921860935",
        "signal_ids": [f"signal:{index}"],
        "priority_score": 100 - index,
        "deep_analysis_status": "SUCCESS",
        "deep_analysis": {
            "targeted_search_queries": [
                '"Example Fashion AS" varelager',
                '"Example Fashion AS" auksjon klær',
                '"Example Fashion AS" avvikling',
                '"Example Fashion AS" fourth query',
            ]
        },
    }
    payload.update(overrides)
    return payload


def _hunt(case_count: int = 2) -> dict[str, Any]:
    return {
        "generated_at": "2026-08-05T19:00:00Z",
        "status": "SUCCESS",
        "cases": [_case(index) for index in range(case_count)],
    }


def _brief(case_count: int = 2) -> dict[str, Any]:
    signals = [
        {
            "signal_id": f"signal:{index}",
            "source_url": f"https://example.test/known/{index}?utm_source=x",
        }
        for index in range(case_count)
    ]
    return {
        "generated_at": "2026-08-05T19:00:00Z",
        "early_signals_to_watch": signals,
        "selected_human_action": {"action": "REVIEW_ONE_OPPORTUNITY"},
        "counts": {},
    }


class FakeProvider:
    name = "Fake Brave"

    def __init__(self, market: str, calls: list[tuple[str, str, int]]) -> None:
        self.market = market
        self.calls = calls

    def search(self, query: str, *, count: int = 10):
        self.calls.append((self.market, query, count))
        return [
            SearchHit(
                title="Example Fashion AS varelager selges på auksjon",
                url="https://auction.test/lot/1?utm_source=brave",
                description="Org.nr 921 860 935. Parti klær og arbeidsklær selges.",
                provider="Brave Search",
            ),
            SearchHit(
                title="Unrelated liquidation inventory",
                url="https://other.test/story",
                description="Varelager og auksjon, men ingen kobling til selskapet.",
                provider="Brave Search",
            ),
            SearchHit(
                title="Existing source",
                url="https://example.test/known/0?utm_medium=x",
                description="Example Fashion AS avvikling.",
                provider="Brave Search",
            ),
        ][:count]


class FailingProvider(FakeProvider):
    def search(self, query: str, *, count: int = 10):
        self.calls.append((self.market, query, count))
        if "auksjon" in query:
            raise RuntimeError("temporary provider failure")
        return super().search(query, count=count)


def test_missing_key_skips_without_search() -> None:
    report = run_hunt_case_targeted_followup(_hunt(), _brief(), environment={})
    assert report["status"] == "SKIPPED_NO_BRAVE_KEY"
    assert report["search_request_count"] == 0
    assert report["automatic_purchase"] is False


def test_no_eligible_cases_is_truthful_zero() -> None:
    report = run_hunt_case_targeted_followup(
        {"generated_at": "2026-08-05T19:00:00Z", "cases": []},
        _brief(),
        environment={},
        provider_factory=lambda market: FakeProvider(market, []),
    )
    assert report["status"] == "NO_ELIGIBLE_CASES"
    assert report["case_followups"] == []


def test_selection_is_bounded_to_two_highest_priority_cases() -> None:
    selected = select_targeted_hunt_cases(_hunt(4), max_cases=2)
    assert [case["hunt_case_id"] for case in selected] == ["hunt:no:0", "hunt:no:1"]


def test_search_is_bounded_to_two_cases_three_queries_and_five_results() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(4),
        _brief(4),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    assert report["selected_case_count"] == 2
    assert report["search_request_count"] == 6
    assert len(calls) == 6
    assert all(count == 5 for _, _, count in calls)
    assert all(len(case["queries"]) == 3 for case in report["case_followups"])


def test_exact_org_and_commercial_terms_create_only_evidence_candidate() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(1),
        _brief(1),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    assert report["status"] == "SUCCESS"
    assert report["evidence_candidate_count"] == 1
    candidate = report["case_followups"][0]["evidence_candidates"][0]
    assert candidate["identity_match_method"] == "EXACT_ORGANISATION_NUMBER"
    assert candidate["evidence_class"] == "IDENTITY_AND_COMMERCIAL_SIGNAL"
    assert candidate["verification_state"] == "EVIDENCE_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
    assert candidate["page_verified"] is False
    assert candidate["promotion_to_opportunity_allowed"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["top5_eligible"] is False


def test_unlinked_commercial_result_is_not_evidence_candidate() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(1),
        _brief(1),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    results = report["case_followups"][0]["results"]
    unlinked = next(item for item in results if item["url"] == "https://other.test/story")
    assert unlinked["evidence_class"] == "COMMERCIAL_SIGNAL_UNLINKED"
    assert unlinked["identity_matched"] is False
    assert unlinked not in report["case_followups"][0]["evidence_candidates"]


def test_known_source_url_is_not_counted_as_new_evidence() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(1),
        _brief(1),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    known = next(
        item
        for item in report["case_followups"][0]["results"]
        if item["url"] == "https://example.test/known/0"
    )
    assert known["already_known_source_url"] is True
    assert known["evidence_class"] == "ALREADY_KNOWN_SOURCE"


def test_provider_failure_is_isolated_as_partial() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(1),
        _brief(1),
        environment={},
        provider_factory=lambda market: FailingProvider(market, calls),
    )
    assert report["status"] == "PARTIAL"
    assert report["query_failure_count"] == 1
    assert report["query_success_count"] == 2
    assert report["case_followups"][0]["status"] == "PARTIAL"


def test_long_and_duplicate_queries_are_rejected_before_search() -> None:
    case = _case(
        0,
        deep_analysis={
            "targeted_search_queries": [
                "x" * 321,
                '"Example Fashion AS" varelager',
                '"Example Fashion AS" varelager',
                "https://unsafe.test/query",
            ]
        },
    )
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        {"generated_at": "2026-08-05T19:00:00Z", "cases": [case]},
        _brief(1),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    assert report["search_request_count"] == 1
    assert [query for _, query, _ in calls] == ['"Example Fashion AS" varelager']


def test_attach_preserves_existing_human_action_and_adds_counts() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(1),
        _brief(1),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    enriched = attach_targeted_followup_intelligence(_brief(1), report)
    assert enriched["selected_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert enriched["counts"]["targeted_followup_cases"] == 1
    assert enriched["counts"]["targeted_evidence_candidates"] == 1
    assert enriched["targeted_followup_intelligence"]["promotion_to_opportunity_allowed"] is False


def test_rendered_report_exposes_links_and_safety_boundary() -> None:
    calls: list[tuple[str, str, int]] = []
    report = run_hunt_case_targeted_followup(
        _hunt(1),
        _brief(1),
        environment={},
        provider_factory=lambda market: FakeProvider(market, calls),
    )
    rendered = render_hunt_case_targeted_followup(report)
    assert "طلبات Brave: 3" in rendered
    assert "https://auction.test/lot/1" in rendered
    assert "يجب فتح صفحة المصدر والتحقق منها" in rendered
    assert "لا ترقية تلقائية إلى فرصة" in rendered
