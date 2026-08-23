from __future__ import annotations

import pytest

from opportunity_engine.provider_route_success_learning import (
    build_provider_route_success_observation,
)
from opportunity_engine.search_success_learning import update_search_success_memory

QUERY_FR = "France vêtements mode lot de marchandises à vendre prix quantité stock déstockage disponible"
PARENT = "https://www.sdpie.com/lots-en-vente/"
LOT_A = "https://www.sdpie.com/lots-en-vente/lot-de-vestes-et-costumes/"
LOT_B = "https://www.sdpie.com/lots-en-vente/lot-epi-vetements-professionnels/"


def _benchmark() -> dict:
    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "provider_mode": "exa",
        "query_mode": "exact_lot",
        "project_domain": "CLOTHING_INVENTORY",
        "project_domain_gate_enforced": True,
        "market_results": [
            {
                "market_code": "FR",
                "query": QUERY_FR,
                "exa": {
                    "results": [
                        {"url": PARENT, "domain": "sdpie.com", "provider": "exa"}
                    ]
                },
                "brave": {"results": []},
            }
        ],
    }


def _verification() -> dict:
    return {
        "status": "SUCCESS",
        "provider": "exa",
        "shadow_only": True,
        "symmetric_provider_verification": True,
        "commercial_specificity_gate_enforced": True,
        "project_domain_gate_enforced": True,
        "required_project_domain": "CLOTHING_INVENTORY",
        "provider_unique_url_count": 1,
        "page_fetches_succeeded": 1,
        "verified_pages": [],
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
    return {
        "status": "SUCCESS",
        "provider": "exa",
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
        "eligible_parent_count": 1,
        "child_page_fetches_succeeded": 2,
        "exact_lot_candidate_count": 2,
        "exact_lots": [_exact(LOT_A), _exact(LOT_B)],
    }


def test_single_provider_route_learning_never_claims_provider_leadership() -> None:
    observation = build_provider_route_success_observation(
        run_id="fresh-exa-run",
        provider="exa",
        benchmark=_benchmark(),
        provider_verification=_verification(),
        child_resolution=_child_resolution(),
        observed_at="2026-08-23T17:20:00+00:00",
    )

    assert observation["status"] == "SUCCESS"
    assert observation["observation_scope"] == "SINGLE_PROVIDER_ROUTE_REPLICATION"
    assert observation["observed_provider_leader"] == "NOT_EVALUATED"
    assert observation["provider_preference_status"] == "PROVIDER_COMPARISON_NOT_EVALUATED"
    assert observation["providers"]["exa"]["end_to_end_exact_lot_count"] == 2
    assert observation["providers"]["brave"]["evaluation_status"] == "NOT_EVALUATED"
    assert observation["automatic_provider_activation"] is False
    assert observation["production_query_mutation"] is False

    route = observation["successful_routes"][0]
    assert route["provider"] == "exa"
    assert route["market_code"] == "FR"
    assert route["pathway"] == "AGGREGATE_CHILD"
    assert route["parent_domain"] == "www.sdpie.com"
    assert route["exact_lot_count"] == 2


def test_single_provider_observation_can_replicate_prior_route_without_claiming_tool_win() -> None:
    first = build_provider_route_success_observation(
        run_id="run-1",
        provider="exa",
        benchmark=_benchmark(),
        provider_verification=_verification(),
        child_resolution=_child_resolution(),
    )
    second = build_provider_route_success_observation(
        run_id="run-2",
        provider="exa",
        benchmark=_benchmark(),
        provider_verification=_verification(),
        child_resolution=_child_resolution(),
    )

    memory = update_search_success_memory({}, first, min_independent_runs=2)
    assert memory["route_learning"][0]["status"] == "CANDIDATE"

    memory = update_search_success_memory(memory, second, min_independent_runs=2)
    assert memory["route_learning"][0]["status"] == "REPLICATED_FOR_REVIEW"
    assert memory["route_learning"][0]["independent_run_count"] == 2
    assert memory["provider_learning"]["exa"]["status"] == "REPLICATED_FOR_REVIEW"
    assert second["observed_provider_leader"] == "NOT_EVALUATED"
    assert memory["automatic_provider_activation"] is False


def test_provider_route_learning_requires_exa_only_benchmark_mode() -> None:
    benchmark = _benchmark()
    benchmark["provider_mode"] = "both"

    with pytest.raises(ValueError, match="provider_mode=exa"):
        build_provider_route_success_observation(
            run_id="wrong-mode",
            provider="exa",
            benchmark=benchmark,
            provider_verification=_verification(),
            child_resolution=_child_resolution(),
        )


def test_provider_route_learning_rejects_incomplete_exact_lot_evidence() -> None:
    child = _child_resolution()
    child["exact_lots"][0]["evidence"]["price_evidence"] = False
    child["exact_lots"][1]["evidence"]["quantity_evidence"] = False

    observation = build_provider_route_success_observation(
        run_id="no-strict-lots",
        provider="exa",
        benchmark=_benchmark(),
        provider_verification=_verification(),
        child_resolution=child,
    )

    assert observation["providers"]["exa"]["end_to_end_exact_lot_count"] == 0
    assert observation["successful_routes"] == []
    assert observation["provider_preference_status"] == "PROVIDER_COMPARISON_NOT_EVALUATED"


def test_provider_route_learning_fails_closed_without_child_subject_guard() -> None:
    child = _child_resolution()
    child["child_subject_domain_gate_enforced"] = False

    with pytest.raises(ValueError, match="child subject domain gate"):
        build_provider_route_success_observation(
            run_id="unsafe",
            provider="exa",
            benchmark=_benchmark(),
            provider_verification=_verification(),
            child_resolution=child,
        )
