from __future__ import annotations

from opportunity_engine.unified_memory_v2 import build_unified_memory_v2


def _record(
    evidence_id: str,
    kind: str,
    *,
    market: str,
    source: str,
    result_type: str,
    outcome: str,
    source_identity: str,
    provider: str | None = None,
    query: str | None = None,
    route: str | None = None,
    miss_reason: str | None = None,
    metadata: dict | None = None,
    supporting_run_ids: list[str] | None = None,
) -> dict:
    return {
        "learning_evidence_id": evidence_id,
        "evidence_kind": kind,
        "market_code": market,
        "project_domain": "CLOTHING_INVENTORY",
        "source_name": source,
        "provider": provider,
        "query": query,
        "url": f"https://example.test/{evidence_id}",
        "result_type": result_type,
        "outcome": outcome,
        "miss_reason": miss_reason,
        "route": route,
        "source_identity": source_identity,
        "observed_at": "2026-08-23T20:00:00Z",
        "supporting_run_ids": supporting_run_ids or [],
        "metadata": metadata or {},
    }


def _spine(generated_at: str) -> dict:
    records = [
        _record(
            "source-no-1",
            "MARKET_OBSERVATION",
            market="NO",
            source="Auksjonen.no",
            result_type="CANONICAL_OPPORTUNITY",
            outcome="ACTIVE_OPPORTUNITY",
            source_identity="no-case-1",
        ),
        _record(
            "source-no-2",
            "MARKET_OBSERVATION",
            market="NO",
            source="Auksjonen.no",
            result_type="CANONICAL_OPPORTUNITY",
            outcome="ACTIVE_OPPORTUNITY",
            source_identity="no-case-2",
        ),
        _record(
            "miss-de-1",
            "MISSED_OPPORTUNITY",
            market="DE",
            source="query-gap",
            result_type="CLOTHING_INVENTORY",
            outcome="MISSED",
            miss_reason="QUERY_GAP",
            source_identity="de-miss-1",
        ),
        _record(
            "miss-de-2",
            "MISSED_OPPORTUNITY",
            market="DE",
            source="query-gap",
            result_type="CLOTHING_INVENTORY",
            outcome="MISSED",
            miss_reason="QUERY_GAP",
            source_identity="de-miss-2",
        ),
        _record(
            "route-fr",
            "SEARCH_ROUTE_SUCCESS",
            market="FR",
            source="friptadium.com",
            provider="exa",
            query="France vêtements lot stock",
            result_type="SEARCH_ROUTE",
            outcome="REPLICATED_FOR_REVIEW",
            route="AGGREGATE_CHILD",
            source_identity="friptadium.com",
            supporting_run_ids=[
                "32655969884",
                "32657298412",
                "32659936703",
                "32661201074",
                "32663784799",
            ],
            metadata={"independent_run_count": 5},
        ),
    ]
    return {
        "schema_version": "unified-learning-spine-1.0",
        "status": "SUCCESS",
        "generated_at": generated_at,
        "evidence_record_count": len(records),
        "market_counts": {"DE": 2, "FR": 1, "NO": 2},
        "domain_counts": {"CLOTHING_INVENTORY": len(records)},
        "evidence_kind_counts": {
            "MARKET_OBSERVATION": 2,
            "MISSED_OPPORTUNITY": 2,
            "SEARCH_ROUTE_SUCCESS": 1,
        },
        "records": records,
        "project_domain_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_same_day_manual_rerun_cannot_create_new_proven_patterns() -> None:
    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=_spine("2026-08-23T20:45:15Z"),
        run_id="32665178244",
    )
    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=_spine("2026-08-23T20:53:09Z"),
        run_id="32665599088",
    )

    assert second["memory_run_count"] == 2
    assert second["reobserved_evidence_count"] == 5
    assert second["proven_pattern_count"] == 1

    route = next(row for row in second["patterns"] if row["pattern_type"] == "ROUTE_SUCCESS")
    source = next(row for row in second["patterns"] if row["pattern_type"] == "SOURCE_OUTCOME")
    miss = next(row for row in second["patterns"] if row["pattern_type"] == "MISS_REASON")

    assert route["pattern_status"] == "PROVEN"
    assert route["independent_run_count"] == 5
    assert route["checkpoint_run_count"] == 2
    assert route["checkpoint_day_count"] == 1

    assert source["pattern_status"] == "REPEATED"
    assert source["checkpoint_run_count"] == 2
    assert source["checkpoint_day_count"] == 1

    assert miss["pattern_status"] == "REPEATED"
    assert miss["checkpoint_run_count"] == 2
    assert miss["checkpoint_day_count"] == 1


def test_next_checkpoint_day_can_prove_repeated_non_route_patterns() -> None:
    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=_spine("2026-08-23T20:45:15Z"),
        run_id="32665178244",
    )
    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=_spine("2026-08-24T20:45:15Z"),
        run_id="32670000000",
    )

    source = next(row for row in second["patterns"] if row["pattern_type"] == "SOURCE_OUTCOME")
    miss = next(row for row in second["patterns"] if row["pattern_type"] == "MISS_REASON")

    assert source["pattern_status"] == "PROVEN"
    assert source["checkpoint_day_count"] == 2
    assert miss["pattern_status"] == "PROVEN"
    assert miss["checkpoint_day_count"] == 2
