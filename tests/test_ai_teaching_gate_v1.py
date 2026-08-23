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


def _memory(patterns):
    return {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "current_run_id": "run-10",
        "memory_run_count": 10,
        "patterns": patterns,
        "project_domain_gate_enforced": True,
        **SAFETY_FALSE,
    }


def _portfolio(markets):
    return {
        "schema_version": "market-route-portfolio-1.0",
        "status": "SUCCESS",
        "generated_from_memory_run_id": "run-10",
        "markets": markets,
        "project_domain_gate_enforced": True,
        **SAFETY_FALSE,
    }


def _route(slot_id, status, *, domain="CLOTHING_INVENTORY", axis="COMMERCIAL_ROUTE", proof_ids=None):
    return {
        "slot_id": slot_id,
        "status": status,
        "axis": axis,
        "project_domain": domain,
        "tracked_targets": [],
        "proof_pattern_ids": proof_ids or [],
        "evidence_observation_count": 0,
    }


def test_fixed_rule_is_bypassed_while_candidate_route_uses_deterministic_proof():
    france = {
        "pattern_id": "fr-fixed",
        "pattern_key": "ROUTE_SUCCESS|FR|CLOTHING_INVENTORY|exa|AGGREGATE_CHILD|friptadium.com",
        "pattern_type": "ROUTE_SUCCESS",
        "pattern_status": "PROVEN",
        "market_code": "FR",
        "project_domain": "CLOTHING_INVENTORY",
        "provider": "exa",
        "route": "AGGREGATE_CHILD",
        "source_identity": "friptadium.com",
        "converted_to_rule": True,
        "rule_id": "rule:fr-exa-friptadium-aggregate-child-v1",
        "rule_review_status": "FIXED_RULE_ACTIVE",
        "ai_still_needed": False,
    }
    norway = {
        "pattern_id": "no-candidate",
        "pattern_key": "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|direct_public_source|PUBLIC_CATEGORY_TO_EXACT_ITEM|auksjonen.no",
        "pattern_type": "ROUTE_SUCCESS",
        "pattern_status": "CANDIDATE",
        "market_code": "NO",
        "project_domain": "CLOTHING_INVENTORY",
        "provider": "direct_public_source",
        "route": "PUBLIC_CATEGORY_TO_EXACT_ITEM",
        "source_identity": "auksjonen.no",
        "converted_to_rule": False,
        "rule_review_status": "NOT_PROVEN",
        "ai_still_needed": True,
    }
    report = build_ai_teaching_gate_v1(
        unified_memory=_memory([france, norway]),
        market_route_portfolio=_portfolio([]),
    )

    assert report["safely_learned_pattern_count"] == 1
    assert report["safely_learned_patterns"][0]["pattern_id"] == "fr-fixed"
    assert report["deterministic_proof_task_count"] == 1
    assert report["deterministic_proof_tasks"][0]["context"]["pattern_id"] == "no-candidate"
    assert report["deterministic_proof_tasks"][0]["requires_paid_ai"] is False
    assert report["ai_teaching_task_count"] == 0
    assert report["automatic_ai_invocation"] is False


def test_market_gap_becomes_manual_ai_teaching_without_any_automatic_invocation():
    report = build_ai_teaching_gate_v1(
        unified_memory=_memory([]),
        market_route_portfolio=_portfolio(
            [
                {
                    "market_code": "NO",
                    "must_continue_discovery": True,
                    "routes": [
                        _route(
                            "FABRIC_PROCUREMENT",
                            "GAP",
                            domain="FABRIC_PROCUREMENT",
                        )
                    ],
                    "unclassified_route_patterns": [],
                }
            ]
        ),
    )

    assert report["ai_teaching_task_count"] == 1
    task = report["ai_teaching_tasks"][0]
    assert task["execution_mode"] == "AI_TEACHING"
    assert task["task_kind"] == "DISCOVER_NEW_ROUTE"
    assert task["priority"] == 100
    assert task["requires_paid_ai"] is True
    assert "FABRIC_PROCUREMENT" in task["mind_forge_seed"]
    assert report["mind_forge_contract"]["manual_paid_run_required"] is True
    assert report["mind_forge_contract"]["automatic_ai_invocation"] is False
    assert report["mind_forge_contract"]["existing_runtime_reused"] is True
    assert report["mind_forge_contract"]["existing_cross_run_learning_reused"] is True


def test_unproven_rule_mapping_fails_closed_toward_ai_instead_of_bypassing_it():
    malformed_old_memory_pattern = {
        "pattern_id": "unsafe-old-row",
        "pattern_key": "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|x|Y|example.no",
        "pattern_type": "ROUTE_SUCCESS",
        "pattern_status": "CANDIDATE",
        "market_code": "NO",
        "project_domain": "CLOTHING_INVENTORY",
        "converted_to_rule": True,
        "rule_id": "rule:should-not-bypass",
        "rule_review_status": "FIXED_RULE_ACTIVE",
        "ai_still_needed": False,
    }
    report = build_ai_teaching_gate_v1(
        unified_memory=_memory([malformed_old_memory_pattern]),
        market_route_portfolio=_portfolio([]),
    )

    assert report["safely_learned_pattern_count"] == 0
    assert report["ai_teaching_task_count"] == 1
    assert report["ai_teaching_tasks"][0]["task_kind"] == "RULE_MAPPING_BLOCKED_UNPROVEN"
    assert report["ai_teaching_tasks"][0]["priority"] == 100


def test_proven_pattern_without_fixed_rule_is_sent_only_to_rule_design_review():
    proven = {
        "pattern_id": "proven-no-rule",
        "pattern_key": "ROUTE_SUCCESS|SE|CLOTHING_INVENTORY|provider|EXACT_ITEM|seller.se",
        "pattern_type": "ROUTE_SUCCESS",
        "pattern_status": "PROVEN",
        "market_code": "SE",
        "project_domain": "CLOTHING_INVENTORY",
        "converted_to_rule": False,
        "rule_review_status": "READY_FOR_RULE_REVIEW",
        "ai_still_needed": True,
    }
    report = build_ai_teaching_gate_v1(
        unified_memory=_memory([proven]),
        market_route_portfolio=_portfolio([]),
    )

    assert report["ai_teaching_task_count"] == 1
    assert report["ai_teaching_tasks"][0]["task_kind"] == "RULE_DESIGN_REVIEW"
    assert report["ai_teaching_tasks"][0]["priority"] == 45


def test_gate_refuses_out_of_domain_memory_patterns():
    bad = {
        "pattern_id": "bad",
        "pattern_key": "SOURCE_OUTCOME|NO|CARS|x",
        "pattern_type": "SOURCE_OUTCOME",
        "pattern_status": "OBSERVED",
        "market_code": "NO",
        "project_domain": "CARS",
        "converted_to_rule": False,
        "ai_still_needed": True,
    }

    try:
        build_ai_teaching_gate_v1(
            unified_memory=_memory([bad]),
            market_route_portfolio=_portfolio([]),
        )
    except ValueError as exc:
        assert "escaped project domain" in str(exc)
    else:
        raise AssertionError("out-of-domain pattern must be rejected")
