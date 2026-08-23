from __future__ import annotations

import json

from opportunity_engine.auksjonen_route_learning import (
    AUKSJONEN_EXACT_ITEM_RELATIVE_PATH,
    AUKSJONEN_PARENT_DOMAIN,
    AUKSJONEN_PATHWAY,
    AUKSJONEN_PROVIDER,
    build_auksjonen_native_route_candidate,
    write_unified_learning_spine_with_native_routes,
)
from opportunity_engine.unified_memory_v2 import build_unified_memory_v2


def _verification() -> dict:
    return {
        "schema_version": "auksjonen-exact-item-verification-1.0",
        "attempted_count": 2,
        "verified_count": 2,
        "failed_count": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "items": [
            {
                "object_id": 611144,
                "title": "280 stk GSA jakke oransje str 56/60",
                "description": "280 nye arbeidsjakker i original emballasje",
                "status": "VERIFIED",
                "exact_item_page_verified": True,
                "url": "https://ny.auksjonen.no/auksjon/torget/gsa-jakke/611144",
                "final_url": "https://www.auksjonen.no/auksjon/torget/gsa-jakke/611144",
                "quantity": 280,
                "condition": "NEW_OR_UNUSED",
            },
            {
                "object_id": 999999,
                "title": "Granitt stein parti",
                "description": "Pall med granitt og belegningsstein",
                "status": "VERIFIED",
                "exact_item_page_verified": True,
                "url": "https://ny.auksjonen.no/auksjon/torget/granitt/999999",
                "final_url": "https://www.auksjonen.no/auksjon/torget/granitt/999999",
                "quantity": 100,
            },
        ],
    }


def _write_inputs(tmp_path, generated_at: str) -> tuple[object, object]:
    output = tmp_path / "checkpoint"
    root = tmp_path / "inputs"
    output.mkdir(parents=True, exist_ok=True)
    exact = root / AUKSJONEN_EXACT_ITEM_RELATIVE_PATH
    exact.parent.mkdir(parents=True, exist_ok=True)
    exact.write_text(json.dumps(_verification()), encoding="utf-8")
    (output / "daily-learning-cycle.json").write_text(
        json.dumps({"generated_at": generated_at}),
        encoding="utf-8",
    )
    (output / "unified-intelligence-items.json").write_text(
        json.dumps({"generated_at": generated_at, "items": []}),
        encoding="utf-8",
    )
    return output, root


def test_auksjonen_route_candidate_uses_only_verified_clothing_lots() -> None:
    route = build_auksjonen_native_route_candidate(_verification())

    assert route is not None
    assert route["provider"] == AUKSJONEN_PROVIDER
    assert route["market_code"] == "NO"
    assert route["parent_domain"] == AUKSJONEN_PARENT_DOMAIN
    assert route["pathway"] == AUKSJONEN_PATHWAY
    assert route["status"] == "CANDIDATE"
    assert route["independent_run_count"] == 0
    assert route["verified_exact_lot_url_count"] == 1
    assert route["verified_exact_lot_urls"] == [
        "https://www.auksjonen.no/auksjon/torget/gsa-jakke/611144"
    ]
    assert route["automatic_activation"] is False
    assert route["production_mutation"] is False


def test_no_verified_clothing_means_no_native_route_candidate() -> None:
    payload = _verification()
    payload["items"] = [payload["items"][1]]
    payload["verified_count"] = 1

    assert build_auksjonen_native_route_candidate(payload) is None


def test_spine_emits_norway_route_candidate_without_persisting_search_success(tmp_path) -> None:
    output, root = _write_inputs(tmp_path, "2026-08-23T21:30:00Z")

    spine = write_unified_learning_spine_with_native_routes(
        output,
        input_root=root,
    )

    routes = [
        row
        for row in spine["records"]
        if row["evidence_kind"] == "SEARCH_ROUTE_SUCCESS" and row["market_code"] == "NO"
    ]
    assert len(routes) == 1
    route = routes[0]
    assert route["project_domain"] == "CLOTHING_INVENTORY"
    assert route["provider"] == AUKSJONEN_PROVIDER
    assert route["route"] == AUKSJONEN_PATHWAY
    assert route["source_identity"] == AUKSJONEN_PARENT_DOMAIN
    assert route["outcome"] == "CANDIDATE"
    assert route["metadata"]["verified_exact_lot_url_count"] == 1
    assert not (root / "learning" / "search-success-memory.json").exists()
    assert spine["automatic_provider_activation"] is False
    assert spine["automatic_source_promotion"] is False
    assert spine["production_mutation"] is False


def test_memory_proves_norway_native_route_only_on_next_checkpoint_day(tmp_path) -> None:
    output, root = _write_inputs(tmp_path, "2026-08-23T21:30:00Z")
    first_spine = write_unified_learning_spine_with_native_routes(output, input_root=root)
    first_memory = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=first_spine,
        run_id="32667262170",
    )
    first_route = next(
        row
        for row in first_memory["patterns"]
        if row["pattern_type"] == "ROUTE_SUCCESS" and row["market_code"] == "NO"
    )
    assert first_route["pattern_status"] == "CANDIDATE"
    assert first_route["checkpoint_day_count"] == 1

    (output / "daily-learning-cycle.json").write_text(
        json.dumps({"generated_at": "2026-08-24T21:30:00Z"}),
        encoding="utf-8",
    )
    (output / "unified-intelligence-items.json").write_text(
        json.dumps({"generated_at": "2026-08-24T21:30:00Z", "items": []}),
        encoding="utf-8",
    )
    second_spine = write_unified_learning_spine_with_native_routes(output, input_root=root)
    second_memory = build_unified_memory_v2(
        existing_memory=first_memory,
        unified_learning_spine=second_spine,
        run_id="32680000000",
    )
    second_route = next(
        row
        for row in second_memory["patterns"]
        if row["pattern_type"] == "ROUTE_SUCCESS" and row["market_code"] == "NO"
    )

    assert second_route["pattern_status"] == "PROVEN"
    assert second_route["checkpoint_day_count"] == 2
    assert second_route["independent_run_count"] == 2
    assert second_route["converted_to_rule"] is False
    assert second_route["ai_still_needed"] is True
    assert second_memory["automatic_provider_activation"] is False
    assert second_memory["production_mutation"] is False
