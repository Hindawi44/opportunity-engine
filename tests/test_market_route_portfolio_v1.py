import copy
import json
from pathlib import Path

from opportunity_engine.market_route_portfolio_v1 import (
    OUTPUT_FILENAME,
    TEXT_FILENAME,
    build_market_route_portfolio_v1,
    write_market_route_portfolio_v1,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (ROOT / "config/learning/market-route-portfolio-v1.json").read_text(encoding="utf-8")
)
FR_KEY = "ROUTE_SUCCESS|FR|CLOTHING_INVENTORY|exa|AGGREGATE_CHILD|friptadium.com"
NO_KEY = "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|direct_public_source|PUBLIC_CATEGORY_TO_EXACT_ITEM|auksjonen.no"


def _memory() -> dict:
    return {
        "schema_version": "unified-memory-2.0",
        "status": "SUCCESS",
        "current_run_id": "live-1",
        "memory_run_count": 5,
        "patterns": [
            {
                "pattern_id": "fr-route",
                "pattern_key": FR_KEY,
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "PROVEN",
                "market_code": "FR",
                "project_domain": "CLOTHING_INVENTORY",
                "converted_to_rule": True,
            },
            {
                "pattern_id": "no-route",
                "pattern_key": NO_KEY,
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "CANDIDATE",
                "market_code": "NO",
                "project_domain": "CLOTHING_INVENTORY",
                "converted_to_rule": False,
            },
        ],
        "evidence_memory": [
            {
                "learning_evidence_id": "no-auksjonen",
                "market_code": "NO",
                "project_domain": "CLOTHING_INVENTORY",
                "source_name": "Auksjonen.no",
                "provider": "direct_public_source",
                "source_identity": "auksjonen.no",
            },
            {
                "learning_evidence_id": "de-brave",
                "market_code": "DE",
                "project_domain": "CLOTHING_INVENTORY",
                "source_name": "Brave Search market signal radar",
                "provider": "brave",
                "source_identity": "example.de",
            },
        ],
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


def _market(portfolio: dict, code: str) -> dict:
    return next(row for row in portfolio["markets"] if row["market_code"] == code)


def _route(market: dict, slot_id: str) -> dict:
    return next(row for row in market["routes"] if row["slot_id"] == slot_id)


def test_one_fixed_route_never_closes_market() -> None:
    portfolio = build_market_route_portfolio_v1(
        unified_memory=_memory(),
        config=CONFIG,
    )

    assert [row["market_code"] for row in portfolio["markets"]] == [
        "NO",
        "SE",
        "DE",
        "FR",
        "NL",
        "IT",
    ]
    assert portfolio["market_route_complete_count"] == 0
    assert portfolio["market_must_continue_discovery_count"] == 6

    france = _market(portfolio, "FR")
    assert _route(france, "WHOLESALE_STOCK_LOTS")["status"] == "FIXED_RULE_ACTIVE"
    assert _route(france, "SEARCH_PROVIDER_ROUTE")["status"] == "FIXED_RULE_ACTIVE"
    assert france["proven_clothing_commercial_route_family_count"] == 1
    assert france["proven_fabric_procurement_route_family_count"] == 0
    assert france["portfolio_status"] == "SINGLE_PROVEN_CLOTHING_ROUTE"
    assert france["route_portfolio_complete"] is False
    assert france["must_continue_discovery"] is True
    assert france["single_route_dependency"] is True

    norway = _market(portfolio, "NO")
    assert _route(norway, "AUCTION")["status"] == "CANDIDATE"
    assert norway["portfolio_status"] == "ROUTES_UNDER_PROOF"
    assert norway["route_portfolio_complete"] is False

    germany = _market(portfolio, "DE")
    assert _route(germany, "SEARCH_PROVIDER_ROUTE")["status"] == "OBSERVED_NO_ROUTE_PROOF"
    assert _route(germany, "AUCTION")["status"] == "TRACKED_NO_ROUTE_PROOF"

    sweden = _market(portfolio, "SE")
    assert _route(sweden, "AUCTION")["status"] == "TRACKED_NO_ROUTE_PROOF"
    assert _route(sweden, "FABRIC_PROCUREMENT")["status"] == "GAP"

    assert portfolio["project_domain_gate_enforced"] is True
    assert portfolio["automatic_query_activation"] is False
    assert portfolio["automatic_provider_activation"] is False
    assert portfolio["automatic_source_promotion"] is False
    assert portfolio["production_mutation"] is False
    assert portfolio["automatic_purchase"] is False


def test_completion_requires_two_proven_clothing_families_and_one_fabric_route() -> None:
    config = copy.deepcopy(CONFIG)
    config["market_routes"]["NO"]["DIRECT_INVENTORY"]["pattern_keys"] = [
        "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|direct|EXACT_LISTING|finn.no"
    ]
    config["market_routes"]["NO"]["FABRIC_PROCUREMENT"]["pattern_keys"] = [
        "ROUTE_SUCCESS|NO|FABRIC_PROCUREMENT|direct|EXACT_PRODUCT|fabric.example"
    ]
    memory = _memory()
    memory["patterns"][1]["pattern_status"] = "PROVEN"
    memory["patterns"].extend(
        [
            {
                "pattern_id": "no-direct",
                "pattern_key": "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|direct|EXACT_LISTING|finn.no",
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "PROVEN",
                "market_code": "NO",
                "project_domain": "CLOTHING_INVENTORY",
                "converted_to_rule": False,
            },
            {
                "pattern_id": "no-fabric",
                "pattern_key": "ROUTE_SUCCESS|NO|FABRIC_PROCUREMENT|direct|EXACT_PRODUCT|fabric.example",
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "PROVEN",
                "market_code": "NO",
                "project_domain": "FABRIC_PROCUREMENT",
                "converted_to_rule": False,
            },
        ]
    )

    portfolio = build_market_route_portfolio_v1(
        unified_memory=memory,
        config=config,
    )
    norway = _market(portfolio, "NO")

    assert norway["proven_clothing_commercial_route_family_count"] == 2
    assert norway["proven_fabric_procurement_route_family_count"] == 1
    assert norway["unclassified_route_pattern_count"] == 0
    assert norway["route_portfolio_complete"] is True
    assert norway["must_continue_discovery"] is False
    assert norway["single_route_dependency"] is False
    assert norway["portfolio_status"] == "DIVERSIFIED_ROUTE_PORTFOLIO"


def test_unclassified_route_is_surfaced_and_blocks_completion() -> None:
    config = copy.deepcopy(CONFIG)
    config["market_routes"]["NO"]["DIRECT_INVENTORY"]["pattern_keys"] = [
        "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|direct|EXACT_LISTING|finn.no"
    ]
    config["market_routes"]["NO"]["FABRIC_PROCUREMENT"]["pattern_keys"] = [
        "ROUTE_SUCCESS|NO|FABRIC_PROCUREMENT|direct|EXACT_PRODUCT|fabric.example"
    ]
    memory = _memory()
    memory["patterns"][1]["pattern_status"] = "PROVEN"
    memory["patterns"].extend(
        [
            {
                "pattern_id": "no-direct",
                "pattern_key": "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|direct|EXACT_LISTING|finn.no",
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "PROVEN",
                "market_code": "NO",
                "project_domain": "CLOTHING_INVENTORY",
            },
            {
                "pattern_id": "no-fabric",
                "pattern_key": "ROUTE_SUCCESS|NO|FABRIC_PROCUREMENT|direct|EXACT_PRODUCT|fabric.example",
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "PROVEN",
                "market_code": "NO",
                "project_domain": "FABRIC_PROCUREMENT",
            },
            {
                "pattern_id": "no-new-unclassified",
                "pattern_key": "ROUTE_SUCCESS|NO|CLOTHING_INVENTORY|new_provider|NEW_ROUTE|new.example",
                "pattern_type": "ROUTE_SUCCESS",
                "pattern_status": "CANDIDATE",
                "market_code": "NO",
                "project_domain": "CLOTHING_INVENTORY",
            },
        ]
    )

    portfolio = build_market_route_portfolio_v1(
        unified_memory=memory,
        config=config,
    )
    norway = _market(portfolio, "NO")

    assert norway["unclassified_route_pattern_count"] == 1
    assert norway["unclassified_route_patterns"][0]["pattern_id"] == "no-new-unclassified"
    assert norway["route_portfolio_complete"] is False
    assert "UNCLASSIFIED_ROUTE_PATTERNS:1" in norway["next_priority_gaps"]


def test_writer_emits_json_and_phone_friendly_text(tmp_path: Path) -> None:
    portfolio = write_market_route_portfolio_v1(
        tmp_path,
        unified_memory=_memory(),
        config_path=ROOT / "config/learning/market-route-portfolio-v1.json",
    )

    assert portfolio["status"] == "SUCCESS"
    assert (tmp_path / OUTPUT_FILENAME).exists()
    text = (tmp_path / TEXT_FILENAME).read_text(encoding="utf-8")
    assert "MARKET ROUTE PORTFOLIO V1" in text
    assert "FR: SINGLE_PROVEN_CLOTHING_ROUTE" in text
    assert "NO: ROUTES_UNDER_PROOF" in text
    assert "A fixed rule handles one exact solved route only" in text
