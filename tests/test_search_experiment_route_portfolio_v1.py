import json
from pathlib import Path

from opportunity_engine.market_route_portfolio_v1 import build_market_route_portfolio_v1


def test_search_experiment_fabric_route_is_classified_in_fabric_slot():
    config = json.loads(
        Path("config/learning/market-route-portfolio-v1.json").read_text(encoding="utf-8")
    )
    pattern_key = (
        "ROUTE_SUCCESS|IT|FABRIC_PROCUREMENT|exa|"
        "SEARCH_TO_FABRIC_COMMERCIAL_PAGE|search-experiment:fabric_procurement"
    )
    memory = {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "current_run_id": "run-1",
        "memory_run_count": 1,
        "patterns": [
            {
                "pattern_id": "experiment-route",
                "pattern_key": pattern_key,
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "CANDIDATE",
                "market_code": "IT",
                "project_domain": "FABRIC_PROCUREMENT",
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

    portfolio = build_market_route_portfolio_v1(
        unified_memory=memory,
        config=config,
    )
    italy = next(row for row in portfolio["markets"] if row["market_code"] == "IT")
    fabric = next(row for row in italy["routes"] if row["slot_id"] == "FABRIC_PROCUREMENT")

    assert fabric["status"] == "CANDIDATE"
    assert fabric["proof_pattern_keys"] == [pattern_key]
    assert italy["unclassified_route_pattern_count"] == 0
