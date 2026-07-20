import json

from opportunity_engine.ods.capital_allocation import (
    CapitalAllocationCandidate,
    CapitalAllocationEngine,
    CapitalAllocationPolicy,
)
from opportunity_engine.ods.capital_allocation_snapshot import SnapshotCapitalAllocator


def _candidate(
    opportunity_id: str,
    *,
    discovery_score: float = 85,
    max_bid: float | None = 8_000,
    total_cost: float | None = 10_000,
    decision: str = "buy",
    actionable: bool = True,
):
    return CapitalAllocationCandidate(
        opportunity_id=opportunity_id,
        decision=decision,
        discovery_score=discovery_score,
        maximum_purchase_price_nok=max_bid,
        total_cost_nok=total_cost,
        expected_profit_nok=5_000,
        roi=0.50,
        is_actionable=actionable,
    )


def test_allocates_only_within_reserve_and_position_limits() -> None:
    plan = CapitalAllocationEngine().allocate(
        (_candidate("a"), _candidate("b")),
        CapitalAllocationPolicy(
            total_capital_nok=40_000,
            reserve_fraction=0.25,
            max_single_opportunity_fraction=0.25,
        ),
    )

    assert plan.reserve_capital_nok == 10_000
    assert plan.investable_capital_nok == 30_000
    assert plan.allocated_capital_nok == 20_000
    assert plan.unallocated_capital_nok == 10_000
    assert plan.allocation_count == 2
    assert all(item.suggested_max_bid_nok == 8_000 for item in plan.allocations)
    assert all(item.reserved_capital_nok == 10_000 for item in plan.allocations)


def test_rejects_incomplete_or_non_buy_candidates() -> None:
    plan = CapitalAllocationEngine().allocate(
        (
            _candidate("monitor", decision="monitor"),
            _candidate("missing", total_cost=None),
            _candidate("weak", discovery_score=40),
        ),
        CapitalAllocationPolicy(total_capital_nok=50_000),
    )

    assert plan.allocation_count == 0
    assert all(item.eligible is False for item in plan.allocations)
    assert "decision_not_buy" in plan.allocations[0].blockers
    assert "total_cost_nok" in plan.allocations[1].blockers
    assert "discovery_score_below_65" in plan.allocations[2].blockers


def test_snapshot_processor_writes_auditable_plan(tmp_path) -> None:
    snapshot = tmp_path / "today.json"
    output = tmp_path / "allocation.json"
    snapshot.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "opportunity_id": "x",
                        "decision": "buy",
                        "maximum_purchase_price_nok": 7_000,
                        "total_cost_nok": 9_000,
                        "expected_profit_nok": 4_000,
                        "roi": 0.44,
                        "blockers": [],
                    }
                ],
                "discovery_by_id": {
                    "x": {
                        "discovery_score": 82,
                        "is_exceptional": True,
                        "requires_immediate_review": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    plan = SnapshotCapitalAllocator().process(
        snapshot,
        total_capital_nok=40_000,
        output_path=output,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert plan.allocation_count == 1
    assert payload["schema_version"] == 1
    assert payload["allocations"][0]["suggested_max_bid_nok"] == 7_000
    assert payload["allocations"][0]["reserved_capital_nok"] == 9_000
