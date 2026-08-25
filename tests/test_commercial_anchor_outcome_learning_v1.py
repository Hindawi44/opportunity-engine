from __future__ import annotations

from opportunity_engine.discovery.commercial_anchor_outcome_learning import (
    build_commercial_anchor_outcome_learning,
)


def _resolution(
    *,
    market: str,
    generated_at: str,
    anchor_value: str,
    outcome: str,
    urls: list[str],
    route: str = "MULTI_HOP",
) -> dict:
    anchor_type = "WHOLESALER" if anchor_value == "Salzmann Restwaren" else "BRAND"
    market_prefix = {
        "NO": "Norge klær clothing",
        "SE": "Sverige kläder clothing",
        "DE": "Deutschland Bekleidung clothing",
        "FR": "France vêtements clothing",
        "IT": "Italia abbigliamento clothing",
        "NL": "Nederland kleding clothing",
    }[market]
    query = f"{market_prefix} {anchor_value} Restposten Großhandel Lager zu verkaufen"
    exact_rows = [
        {
            "url": url,
            "final_url": url,
            "query": query,
        }
        for url in urls
    ]
    verification = {"verified_pages": exact_rows if route == "DIRECT_SEARCH_RESULT" else []}
    multihop = {"exact_lots": exact_rows if route == "MULTI_HOP" else []}
    return {
        "schema_version": "exa-exact-lot-checkpoint-resolution-1.7",
        "generated_at": generated_at,
        "market": market,
        "project_domain": "CLOTHING_INVENTORY",
        "provider": "exa",
        "commercial_anchor_outcome_evidence": {
            "schema_version": "commercial-anchor-outcome-evidence-1.0",
            "status": "SUCCESS",
            "market_code": market,
            "project_domain": "CLOTHING_INVENTORY",
            "provider": "exa",
            "outcomes": [
                {
                    "market_code": market,
                    "project_domain": "CLOTHING_INVENTORY",
                    "provider": "exa",
                    "anchor_type": anchor_type,
                    "anchor_value": anchor_value,
                    "anchor_origin": "EVIDENCE_BACKED_MARKET_ENTITY_V1",
                    "query": query,
                    "outcome": outcome,
                    "strict_exact_lot_added_count": len(urls),
                    "strict_exact_lot_urls": urls,
                    "anchor_is_qualification_evidence": False,
                    "learning_evidence_only": True,
                    "automatic_query_activation": False,
                    "automatic_source_promotion": False,
                    "production_query_mutation": False,
                    "production_mutation": False,
                }
            ],
            "anchor_is_qualification_evidence": False,
            "learning_evidence_only": True,
            "automatic_query_activation": False,
            "automatic_source_promotion": False,
            "production_query_mutation": False,
            "production_mutation": False,
        },
        "verification": verification,
        "multihop": multihop,
        "production_mutation": False,
        "automatic_provider_activation": False,
    }


def test_salzmann_multihop_success_is_candidate_combination_not_anchor_only() -> None:
    urls = [f"https://salzmann-restwaren.de/products/restposten-{index}" for index in range(3)]
    memory = build_commercial_anchor_outcome_learning(
        existing_memory={},
        current_resolutions={
            "de-exa-exact-lot/exa-exact-lot-resolution.json": _resolution(
                market="DE",
                generated_at="2026-08-25T17:00:00+00:00",
                anchor_value="Salzmann Restwaren",
                outcome="STRICT_EXACT_LOT_SUCCESS",
                urls=urls,
                route="MULTI_HOP",
            )
        },
        run_id="334",
    )

    assert memory["candidate_success_pattern_count"] == 1
    assert memory["proven_success_pattern_count"] == 0
    pattern = memory["patterns"][0]
    assert pattern["pattern_status"] == "CANDIDATE_SUCCESS"
    assert pattern["market_code"] == "DE"
    assert pattern["anchor_value"] == "Salzmann Restwaren"
    assert pattern["query_family"] == (
        "Deutschland Bekleidung clothing {ANCHOR} Restposten Großhandel Lager zu verkaufen"
    )
    assert pattern["route"] == "MULTI_HOP"
    assert pattern["verified_exact_lot_url_count"] == 3
    assert pattern["anchor_is_qualification_evidence"] is False
    assert pattern["automatic_query_activation"] is False


def test_independent_checkpoint_day_promotes_only_to_review_ready_proven_success() -> None:
    first = build_commercial_anchor_outcome_learning(
        existing_memory={},
        current_resolutions={
            "de-exa-exact-lot/exa-exact-lot-resolution.json": _resolution(
                market="DE",
                generated_at="2026-08-25T17:00:00+00:00",
                anchor_value="Salzmann Restwaren",
                outcome="STRICT_EXACT_LOT_SUCCESS",
                urls=["https://salzmann-restwaren.de/products/restposten-1"],
            )
        },
        run_id="334",
    )
    second = build_commercial_anchor_outcome_learning(
        existing_memory=first,
        current_resolutions={
            "de-exa-exact-lot/exa-exact-lot-resolution.json": _resolution(
                market="DE",
                generated_at="2026-08-26T17:00:00+00:00",
                anchor_value="Salzmann Restwaren",
                outcome="STRICT_EXACT_LOT_SUCCESS",
                urls=["https://salzmann-restwaren.de/products/restposten-2"],
            )
        },
        run_id="338",
    )

    assert second["proven_success_pattern_count"] == 1
    pattern = second["proven_success_patterns"][0]
    assert pattern["pattern_status"] == "PROVEN_SUCCESS"
    assert pattern["checkpoint_day_count"] == 2
    assert pattern["review_status"] == "READY_FOR_HUMAN_REVIEW"
    assert pattern["automatic_query_activation"] is False
    assert pattern["automatic_source_promotion"] is False
    assert pattern["production_mutation"] is False


def test_same_day_rerun_does_not_prove_anchor_pattern() -> None:
    first = build_commercial_anchor_outcome_learning(
        existing_memory={},
        current_resolutions={
            "de-exa-exact-lot/exa-exact-lot-resolution.json": _resolution(
                market="DE",
                generated_at="2026-08-25T17:00:00+00:00",
                anchor_value="Salzmann Restwaren",
                outcome="STRICT_EXACT_LOT_SUCCESS",
                urls=["https://salzmann-restwaren.de/products/restposten-1"],
            )
        },
        run_id="334",
    )
    second = build_commercial_anchor_outcome_learning(
        existing_memory=first,
        current_resolutions={
            "de-exa-exact-lot/exa-exact-lot-resolution.json": _resolution(
                market="DE",
                generated_at="2026-08-25T19:00:00+00:00",
                anchor_value="Salzmann Restwaren",
                outcome="STRICT_EXACT_LOT_SUCCESS",
                urls=["https://salzmann-restwaren.de/products/restposten-2"],
            )
        },
        run_id="337",
    )

    assert second["proven_success_pattern_count"] == 0
    assert second["candidate_success_pattern_count"] == 1
    assert second["patterns"][0]["checkpoint_run_count"] == 2
    assert second["patterns"][0]["checkpoint_day_count"] == 1


def test_zero_yield_anchor_is_learned_as_zero_not_as_success() -> None:
    memory = build_commercial_anchor_outcome_learning(
        existing_memory={},
        current_resolutions={
            "no-exa-exact-lot/exa-exact-lot-resolution.json": _resolution(
                market="NO",
                generated_at="2026-08-25T17:00:00+00:00",
                anchor_value="Jack & Jones",
                outcome="NO_NEW_STRICT_EXACT_LOT",
                urls=[],
            )
        },
        run_id="334",
    )

    assert memory["candidate_success_pattern_count"] == 0
    assert memory["proven_success_pattern_count"] == 0
    pattern = memory["patterns"][0]
    assert pattern["pattern_status"] == "OBSERVED_ZERO"
    assert pattern["route"] == "NO_EXACT_LOT_ROUTE"
    assert pattern["zero_observation_count"] == 1


def test_success_with_missing_route_provenance_is_not_success_learning_eligible() -> None:
    resolution = _resolution(
        market="DE",
        generated_at="2026-08-25T17:00:00+00:00",
        anchor_value="Salzmann Restwaren",
        outcome="STRICT_EXACT_LOT_SUCCESS",
        urls=["https://salzmann-restwaren.de/products/restposten-1"],
    )
    resolution["verification"] = {"verified_pages": []}
    resolution["multihop"] = {"exact_lots": []}

    memory = build_commercial_anchor_outcome_learning(
        existing_memory={},
        current_resolutions={
            "de-exa-exact-lot/exa-exact-lot-resolution.json": resolution,
        },
        run_id="334",
    )

    assert memory["candidate_success_pattern_count"] == 0
    assert memory["proven_success_pattern_count"] == 0
    pattern = memory["patterns"][0]
    assert pattern["pattern_status"] == "UNATTRIBUTED"
    assert pattern["route"] == "UNATTRIBUTED_ROUTE"
    assert pattern["review_status"] == "NO_AUTOMATIC_ACTION"
