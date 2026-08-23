from __future__ import annotations

import pytest

from opportunity_engine.search_success_learning import (
    build_search_success_observation,
    update_search_success_memory,
)


QUERY_FR = "France vêtements mode lot de marchandises à vendre prix quantité stock déstockage disponible"
PARENT = "https://www.sdpie.com/lots-en-vente/"
LOT_A = "https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/"
LOT_B = "https://www.sdpie.com/lots-en-vente/lot-epi-vetements-professionnels/"


def _benchmark() -> dict:
    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "query_mode": "exact_lot",
        "project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "market_results": [
            {
                "market_code": "FR",
                "query": QUERY_FR,
                "exa": {"results": [{"url": PARENT, "domain": "sdpie.com"}]},
                "brave": {"results": [{"url": "https://example.org/article"}]},
            }
        ],
    }


def _tool_learning() -> dict:
    def provider(name: str, successful: int) -> dict:
        return {
            "status": "SUCCESS",
            "provider": name,
            "shadow_only": True,
            "symmetric_provider_verification": True,
            "commercial_specificity_gate_enforced": True,
            "project_domain_gate_enforced": True,
            "required_project_domain": "CLOTHING_INVENTORY",
            "provider_unique_url_count": 1,
            "page_fetches_succeeded": successful,
            "exact_lot_candidate_count": 0,
            "verified_pages": [],
        }

    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "automatic_provider_activation": False,
        "production_mutation": False,
        "exa_verification": provider("exa", 1),
        "brave_verification": provider("brave", 1),
    }


def _exact(url: str) -> dict:
    return {
        "url": url,
        "parent_url": PARENT,
        "market_code": "FR",
        "query": QUERY_FR,
        "provider": "exa",
        "classification": "EXACT_LOT_CANDIDATE",
        "fetch_ok": True,
        "evidence": {
            "project_domain": "CLOTHING_INVENTORY",
            "page_subject_domain": "CLOTHING_INVENTORY",
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "item_specific_url_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def _child_resolution() -> dict:
    def provider(name: str, exact_lots: list[dict]) -> dict:
        return {
            "status": "SUCCESS",
            "provider": name,
            "shadow_only": True,
            "required_project_domain": "CLOTHING_INVENTORY",
            "project_domain_gate_enforced": True,
            "commercial_specificity_gate_enforced": True,
            "child_subject_domain_gate_enforced": True,
            "same_origin_child_links_only": True,
            "descendant_path_child_links_only": True,
            "exact_lot_acceptance_only": True,
            "production_mutation": False,
            "automatic_contact": False,
            "automatic_purchase": False,
            "eligible_parent_count": 1 if name == "exa" else 0,
            "parent_fetches_succeeded": 1 if name == "exa" else 0,
            "child_page_fetches_succeeded": len(exact_lots),
            "exact_lot_candidate_count": len(exact_lots),
            "exact_lots": exact_lots,
        }

    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "production_mutation": False,
        "exa": provider("exa", [_exact(LOT_A), _exact(LOT_B)]),
        "brave": provider("brave", []),
    }


def test_positive_learning_records_end_to_end_success_without_automatic_activation() -> None:
    observation = build_search_success_observation(
        run_id="32653292874",
        benchmark=_benchmark(),
        tool_learning_proof=_tool_learning(),
        child_resolution=_child_resolution(),
        observed_at="2026-08-23T16:59:21+00:00",
    )

    assert observation["status"] == "SUCCESS"
    assert observation["observed_provider_leader"] == "EXA"
    assert observation["provider_preference_status"] == "SINGLE_RUN_OBSERVATION_ONLY"
    assert observation["automatic_provider_activation"] is False
    assert observation["production_query_mutation"] is False

    assert observation["providers"]["exa"]["direct_exact_lot_count"] == 0
    assert observation["providers"]["exa"]["child_exact_lot_count"] == 2
    assert observation["providers"]["exa"]["end_to_end_exact_lot_count"] == 2
    assert observation["providers"]["brave"]["end_to_end_exact_lot_count"] == 0

    assert len(observation["successful_routes"]) == 1
    route = observation["successful_routes"][0]
    assert route["provider"] == "exa"
    assert route["market_code"] == "FR"
    assert route["query"] == QUERY_FR
    assert route["pathway"] == "AGGREGATE_CHILD"
    assert route["parent_domain"] == "sdpie.com"
    assert route["exact_lot_count"] == 2
    assert route["exact_lot_urls"] == [LOT_A, LOT_B]


def test_memory_requires_independent_replication_and_deduplicates_same_run() -> None:
    first = build_search_success_observation(
        run_id="run-1",
        benchmark=_benchmark(),
        tool_learning_proof=_tool_learning(),
        child_resolution=_child_resolution(),
    )
    second = build_search_success_observation(
        run_id="run-2",
        benchmark=_benchmark(),
        tool_learning_proof=_tool_learning(),
        child_resolution=_child_resolution(),
    )

    memory = update_search_success_memory({}, first, min_independent_runs=2)
    assert memory["run_count"] == 1
    assert memory["route_learning"][0]["status"] == "CANDIDATE"
    assert memory["provider_learning"]["exa"]["status"] == "CANDIDATE"
    assert memory["automatic_provider_activation"] is False
    assert memory["production_query_mutation"] is False

    duplicate = update_search_success_memory(memory, first, min_independent_runs=2)
    assert duplicate["run_count"] == 1
    assert duplicate["route_learning"][0]["independent_run_count"] == 1

    replicated = update_search_success_memory(duplicate, second, min_independent_runs=2)
    assert replicated["run_count"] == 2
    assert replicated["route_learning"][0]["independent_run_count"] == 2
    assert replicated["route_learning"][0]["status"] == "REPLICATED_FOR_REVIEW"
    assert replicated["provider_learning"]["exa"]["status"] == "REPLICATED_FOR_REVIEW"
    assert replicated["provider_learning"]["exa"]["automatic_activation"] is False


def test_child_learning_fails_closed_if_safety_contract_is_missing() -> None:
    child = _child_resolution()
    child["exa"]["child_subject_domain_gate_enforced"] = False

    with pytest.raises(ValueError, match="child subject domain gate"):
        build_search_success_observation(
            run_id="unsafe",
            benchmark=_benchmark(),
            tool_learning_proof=_tool_learning(),
            child_resolution=child,
        )


def test_only_strict_exact_lots_can_teach_success_memory() -> None:
    child = _child_resolution()
    child["exa"]["exact_lots"][0]["evidence"]["quantity_evidence"] = False

    observation = build_search_success_observation(
        run_id="partial",
        benchmark=_benchmark(),
        tool_learning_proof=_tool_learning(),
        child_resolution=child,
    )

    assert observation["providers"]["exa"]["child_exact_lot_count"] == 1
    assert observation["successful_routes"][0]["exact_lot_count"] == 1
    assert observation["successful_routes"][0]["exact_lot_urls"] == [LOT_B]


def test_non_exact_lot_query_mode_cannot_train_positive_exact_lot_memory() -> None:
    benchmark = _benchmark()
    benchmark["query_mode"] = "discovery"

    with pytest.raises(ValueError, match="exact_lot query mode"):
        build_search_success_observation(
            run_id="wrong-mode",
            benchmark=benchmark,
            tool_learning_proof=_tool_learning(),
            child_resolution=_child_resolution(),
        )
