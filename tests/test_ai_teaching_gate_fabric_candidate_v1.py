from opportunity_engine.ai_teaching_gate_v1 import build_ai_teaching_gate_v1


SAFETY_FALSE = {
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


def test_pending_fabric_candidate_uses_deterministic_proof_not_paid_ai() -> None:
    memory = {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "current_run_id": "run-378",
        "memory_run_count": 80,
        "patterns": [],
        "project_domain_gate_enforced": True,
        **SAFETY_FALSE,
    }
    portfolio = {
        "schema_version": "market-route-portfolio-1.0",
        "status": "SUCCESS",
        "generated_from_memory_run_id": "run-378",
        "markets": [
            {
                "market_code": "NO",
                "must_continue_discovery": True,
                "routes": [
                    {
                        "slot_id": "FABRIC_PROCUREMENT",
                        "status": "CANDIDATE",
                        "axis": "COMMERCIAL_ROUTE",
                        "project_domain": "FABRIC_PROCUREMENT",
                        "tracked_targets": [],
                        "proof_pattern_ids": [],
                        "evidence_observation_count": 0,
                    }
                ],
                "unclassified_route_patterns": [],
            }
        ],
        "project_domain_gate_enforced": True,
        **SAFETY_FALSE,
    }

    report = build_ai_teaching_gate_v1(
        unified_memory=memory,
        market_route_portfolio=portfolio,
    )

    assert report["deterministic_proof_task_count"] == 1
    assert report["ai_teaching_task_count"] == 0
    task = report["deterministic_proof_tasks"][0]
    assert task["task_kind"] == "REOBSERVE_CANDIDATE_ROUTE_SLOT"
    assert task["requires_paid_ai"] is False
    assert task["context"]["market_code"] == "NO"
    assert task["context"]["slot_id"] == "FABRIC_PROCUREMENT"
    assert report["automatic_ai_invocation"] is False
