import json
from pathlib import Path

from opportunity_engine.market_route_portfolio_v1 import (
    build_market_route_portfolio_v1,
    render_market_route_portfolio_v1,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (ROOT / "config/learning/market-route-portfolio-v1.json").read_text(encoding="utf-8")
)


def _memory() -> dict:
    return {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "current_run_id": "search-exit-semantics-test",
        "memory_run_count": 1,
        "patterns": [],
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


def test_route_portfolio_learning_never_blocks_search_engine_exit() -> None:
    portfolio = build_market_route_portfolio_v1(
        unified_memory=_memory(),
        config=CONFIG,
    )

    assert portfolio["portfolio_role"] == "ROUTE_DIVERSITY_LEARNING_ONLY"
    assert portfolio["blocks_search_engine_v1_exit"] is False
    assert portfolio["search_engine_exit_authority"] == "SEARCH_MATURITY_ROUTE_EVIDENCE_GATE_V1"
    assert portfolio["market_must_continue_discovery_count"] == 6

    for market in portfolio["markets"]:
        assert market["route_learning_continues"] == market["must_continue_discovery"]
        assert market["blocks_search_engine_v1_exit"] is False

    text = render_market_route_portfolio_v1(portfolio)
    assert "does not block Search Engine V1 exit" in text
    assert "continue_route_learning=true" in text
    assert "blocks_search_exit=false" in text
    assert "not a Search Engine V1 development blocker" in text
