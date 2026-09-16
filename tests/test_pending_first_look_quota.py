"""First-look coverage must survive a large durable enrichment backlog."""
from types import SimpleNamespace

from scripts.run_pending_opportunity_investigation import (
    investigate_pending_opportunities,
    select_pending_opportunities,
)
from opportunity_engine.discovery.pending_evidence_enrichment import QUANTITY_BLOCKER


def _row(index: int, *, exact: bool = False, urgent: bool = False) -> dict:
    return {
        "opportunity_identity": f"case-{index}",
        "source_url": f"https://example.test/product/{index}",
        "title": f"Stock {index}",
        "market_code": "DE",
        "listing_status": "ACTIVE",
        "workflow_status": "REQUIRES_VERIFICATION",
        "missing_evidence": (
            ["verified exact item-page evidence"] if urgent else
            [QUANTITY_BLOCKER] if exact else ["seller identity"]
        ),
        "discovery_score": 100 - index / 1000,
    }


def _backlog():
    # Baseline reproduction: 41 priority-1 old items, 33 never seen.
    seen = [_row(i, exact=True) for i in range(41)]
    unseen = [_row(i) for i in range(41, 74)]
    state = {"records": {
        f"case-{i}": {
            "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
            "attempt_count": 1,
            "last_investigated_at": "2026-09-15T00:00:00+00:00",
        } for i in range(41)
    }}
    return {"deduplicated_opportunities": seen + unseen}, state


def test_first_look_reservation_breaks_enrichment_starvation():
    report, state = _backlog()
    selected = select_pending_opportunities(report, limit=10, investigation_state=state)
    identities = [row["opportunity_identity"] for row in selected]
    assert len(identities) == len(set(identities)) == 10
    assert sum(identity not in state["records"] for identity in identities) >= 2
    assert sum(identity in state["records"] for identity in identities) >= 1
    assert identities == [row["opportunity_identity"] for row in select_pending_opportunities(
        report, limit=10, investigation_state=state
    )]


def test_urgent_cases_keep_priority_and_can_exhaust_budget():
    report, state = _backlog()
    urgent = [_row(100 + i, urgent=True) for i in range(10)]
    report["deduplicated_opportunities"] = urgent + report["deduplicated_opportunities"]
    selected = select_pending_opportunities(report, limit=10, investigation_state=state)
    assert [row["opportunity_identity"] for row in selected] == [
        row["opportunity_identity"] for row in urgent
    ]


def test_small_limits_preserve_existing_priority_and_empty_unseen():
    report, state = _backlog()
    for limit in (1, 2, 4):
        selected = select_pending_opportunities(report, limit=limit, investigation_state=state)
        assert all(row["opportunity_identity"] in state["records"] for row in selected)
    selected = select_pending_opportunities(
        {"deduplicated_opportunities": report["deduplicated_opportunities"][:41]},
        limit=10, investigation_state=state,
    )
    assert len(selected) == 10
    assert all(row["opportunity_identity"] in state["records"] for row in selected)


def test_same_url_not_fetched_twice_and_counters_match():
    report, state = _backlog()
    duplicate = dict(report["deduplicated_opportunities"][42])
    duplicate["opportunity_identity"] = "duplicate-identity"
    report["deduplicated_opportunities"].append(duplicate)
    selected = select_pending_opportunities(report, limit=10, investigation_state=state)
    assert len({row["source_url"] for row in selected}) == len(selected)

    calls = []
    def fetch(url: str):
        calls.append(url)
        return SimpleNamespace(ok=False, error="test-blocked", final_url=url, status_code=403)

    result = investigate_pending_opportunities(
        report, limit=10, investigation_state=state, page_fetcher=fetch
    )
    assert len(calls) == len(set(calls)) == 10
    assert result["reserved_first_look_target"] >= 2
    assert result["selected_first_look_count"] >= 2
    assert result["newly_investigated_count"] >= 2
    assert result["unseen_pending_after_selection"] < result["unseen_pending_before_selection"]
    assert result["priority_candidate_counts"]["1"] >= 41
    assert result["promotion_to_opportunity_allowed"] is False
    assert result["automatic_purchase"] is False


def test_invalid_limits_still_fail_closed():
    report, state = _backlog()
    for limit in (0, 21):
        try:
            select_pending_opportunities(report, limit=limit, investigation_state=state)
        except ValueError:
            continue
        raise AssertionError("Expected bounded limit validation")
