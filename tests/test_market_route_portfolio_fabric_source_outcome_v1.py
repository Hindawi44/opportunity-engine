from opportunity_engine.market_route_portfolio_v1 import build_market_route_portfolio_v1


def _config() -> dict:
    return {
        "schema_version": "market-route-portfolio-1.0",
        "markets": ["FR"],
        "completion_gate": {
            "minimum_proven_clothing_commercial_route_families": 2,
            "minimum_proven_fabric_procurement_route_families": 1,
            "unclassified_route_patterns_must_be_zero": True,
        },
        "route_slots": [
            {
                "slot_id": "FABRIC_PROCUREMENT",
                "axis": "COMMERCIAL_ROUTE",
                "project_domain": "FABRIC_PROCUREMENT",
            }
        ],
        "market_routes": {
            "FR": {
                "FABRIC_PROCUREMENT": {
                    "tracked_targets": [],
                    "pattern_keys": [
                        "ROUTE_SUCCESS|FR|FABRIC_PROCUREMENT|exa|SEARCH_TO_FABRIC_COMMERCIAL_PAGE|search-experiment:fabric_procurement"
                    ],
                }
            }
        },
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


def _memory(pattern_status: str, *, project_domain: str = "FABRIC_PROCUREMENT") -> dict:
    return {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "current_run_id": "run-376",
        "memory_run_count": 78,
        "patterns": [
            {
                "pattern_id": "fabric-source-proof",
                "pattern_key": (
                    "SOURCE_OUTCOME|FR|FABRIC_PROCUREMENT|cybitex.fr|"
                    "FABRIC_PROCUREMENT_ITEM|VERIFIED_COMMERCIAL_FABRIC_PAGE"
                ),
                "pattern_type": "SOURCE_OUTCOME",
                "pattern_status": pattern_status,
                "market_code": "FR",
                "project_domain": project_domain,
                "result_type": "FABRIC_PROCUREMENT_ITEM",
                "outcome": "VERIFIED_COMMERCIAL_FABRIC_PAGE",
                "checkpoint_day_count": 3,
                "distinct_evidence_count": 4,
                "converted_to_rule": False,
            }
        ],
        "evidence_memory": [],
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


def _fabric_route(portfolio: dict) -> dict:
    france = portfolio["markets"][0]
    return france["routes"][0]


def test_proven_verified_fabric_source_outcome_counts_as_fabric_route_proof() -> None:
    portfolio = build_market_route_portfolio_v1(
        unified_memory=_memory("PROVEN"),
        config=_config(),
    )
    france = portfolio["markets"][0]
    route = _fabric_route(portfolio)

    assert route["status"] == "PROVEN"
    assert route["fabric_source_outcome_proof_count"] == 1
    assert route["fabric_source_outcome_pending_proof_count"] == 0
    assert route["proof_pattern_ids"] == ["fabric-source-proof"]
    assert france["proven_fabric_procurement_route_family_count"] == 1
    assert "FABRIC_PROCUREMENT:0/1" not in france["next_priority_gaps"]
    assert portfolio["automatic_query_activation"] is False
    assert portfolio["automatic_purchase"] is False


def test_repeated_fabric_source_outcome_is_candidate_but_does_not_fake_route_proof() -> None:
    portfolio = build_market_route_portfolio_v1(
        unified_memory=_memory("REPEATED"),
        config=_config(),
    )
    france = portfolio["markets"][0]
    route = _fabric_route(portfolio)

    assert route["status"] == "CANDIDATE"
    assert route["fabric_source_outcome_proof_count"] == 0
    assert route["fabric_source_outcome_pending_proof_count"] == 1
    assert route["fabric_source_outcome_pending_pattern_ids"] == ["fabric-source-proof"]
    assert france["proven_fabric_procurement_route_family_count"] == 0
    assert "FABRIC_PROCUREMENT:0/1" in france["next_priority_gaps"]


def test_observed_fabric_source_outcome_is_candidate_pending_independent_proof() -> None:
    portfolio = build_market_route_portfolio_v1(
        unified_memory=_memory("OBSERVED"),
        config=_config(),
    )
    france = portfolio["markets"][0]
    route = _fabric_route(portfolio)

    assert route["status"] == "CANDIDATE"
    assert route["fabric_source_outcome_proof_count"] == 0
    assert route["fabric_source_outcome_pending_proof_count"] == 1
    assert france["proven_fabric_procurement_route_family_count"] == 0
    assert "FABRIC_PROCUREMENT:0/1" in france["next_priority_gaps"]


def test_out_of_domain_source_outcome_cannot_prove_or_seed_fabric_route() -> None:
    portfolio = build_market_route_portfolio_v1(
        unified_memory=_memory("PROVEN", project_domain="CLOTHING_INVENTORY"),
        config=_config(),
    )
    route = _fabric_route(portfolio)

    assert route["status"] == "GAP"
    assert route["fabric_source_outcome_proof_count"] == 0
    assert route["fabric_source_outcome_pending_proof_count"] == 0
