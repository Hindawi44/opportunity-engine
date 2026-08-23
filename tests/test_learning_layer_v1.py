from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.learning_layer import (
    build_learning_layer_review,
    write_learning_layer_review,
)


INIT = Path("src/opportunity_engine/discovery/__init__.py")
HOOK = Path("src/opportunity_engine/discovery/learning_layer_review_cli_hook.py")


def _search_success_memory() -> dict:
    return {
        "schema_version": "search-success-memory-1.0",
        "run_count": 3,
        "replicated_route_count": 1,
        "route_learning": [
            {
                "provider": "exa",
                "market_code": "FR",
                "parent_domain": "friptadium.com",
                "pathway": "AGGREGATE_CHILD",
                "query": "France vêtements lot prix quantité stock",
                "independent_run_count": 2,
                "supporting_run_ids": ["run-1", "run-2"],
                "status": "REPLICATED_FOR_REVIEW",
                "exact_lot_urls": ["https://friptadium.com/products/example"],
            }
        ],
        "provider_learning": {
            "exa": {"status": "REPLICATED_FOR_REVIEW"},
            "brave": {"status": "NOT_EVALUATED"},
        },
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "production_query_mutation": False,
        "production_mutation": False,
    }


def _root_cause_feedback() -> dict:
    return {
        "schema_version": "root-cause-feedback-router-1.0",
        "status": "ACTION_REQUIRED",
        "active_route_count": 1,
        "routes": [
            {
                "case_id": "MISS-1",
                "market_code": "NO",
                "root_cause": "QUERY_GAP",
                "mechanism": "ADAPTIVE_KEYWORD_LEARNING",
                "action": "RUN_BOUNDED_SHADOW_KEYWORD_LEARNING",
                "priority": "HIGH",
                "route_status": "ACTIVE",
                "repeat_miss": False,
                "learning_status": "DIAGNOSED",
                "keyword_learning_eligible": True,
                "automatic_adaptation_available": True,
            }
        ],
        "automatic_source_policy_mutation": False,
        "automatic_code_change": False,
    }


def _daily_learning() -> dict:
    return {
        "schema_version": "daily-learning-operator-1.1",
        "generated_at": "2026-08-23T18:40:00+00:00",
        "search_status": "SUCCESS",
        "known_missed_opportunity_count": 1,
        "candidate_count": 1,
        "evaluated_candidate_count": 1,
        "proven_term_count_this_run": 1,
        "shadow_proven_term_count": 1,
        "active_learned_term_count": 0,
        "safe_learning_promotion_eligible_count": 1,
        "promotion_gate_enforced": True,
        "automatic_query_activation": False,
    }


def test_learning_layer_unifies_success_and_miss_learning_without_mutation() -> None:
    review = build_learning_layer_review(
        search_success_memory=_search_success_memory(),
        root_cause_feedback=_root_cause_feedback(),
        daily_learning=_daily_learning(),
    )

    assert review["schema_version"] == "learning-layer-review-1.0"
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["review_item_count"] == 3
    assert review["what_worked_count"] >= 2
    assert review["what_failed_count"] == 1

    kinds = {item["kind"] for item in review["review_queue"]}
    assert kinds == {
        "REPLICATED_SEARCH_ROUTE",
        "MISSED_OPPORTUNITY_ROOT_CAUSE",
        "SHADOW_KEYWORD_PROMOTION_REVIEW",
    }

    route = next(
        item for item in review["review_queue"]
        if item["kind"] == "REPLICATED_SEARCH_ROUTE"
    )
    assert route["provider"] == "exa"
    assert route["market_code"] == "FR"
    assert route["independent_run_count"] == 2
    assert route["review_action"] == "REVIEW_REPLICATED_ROUTE"

    miss = next(
        item for item in review["review_queue"]
        if item["kind"] == "MISSED_OPPORTUNITY_ROOT_CAUSE"
    )
    assert miss["root_cause"] == "QUERY_GAP"
    assert miss["mechanism"] == "ADAPTIVE_KEYWORD_LEARNING"

    assert review["automatic_query_activation"] is False
    assert review["automatic_provider_activation"] is False
    assert review["automatic_source_promotion"] is False
    assert review["automatic_code_change"] is False
    assert review["production_query_mutation"] is False
    assert review["production_mutation"] is False
    assert review["automatic_contact"] is False
    assert review["automatic_bid"] is False
    assert review["automatic_reservation"] is False
    assert review["automatic_purchase"] is False
    assert review["automatic_payment"] is False


def test_learning_layer_valid_zero_is_not_fabricated_learning() -> None:
    review = build_learning_layer_review(
        search_success_memory={},
        root_cause_feedback={},
        daily_learning={},
    )

    assert review["status"] == "VALID_ZERO_NO_REVIEW_ITEMS"
    assert review["review_item_count"] == 0
    assert review["what_worked"] == []
    assert review["what_failed"] == []
    assert review["review_queue"] == []
    assert review["automatic_query_activation"] is False
    assert review["production_mutation"] is False


def test_learning_layer_writer_reads_existing_artifacts_and_attaches_summary(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "inputs"
    learning = input_root / "learning"
    output = tmp_path / "checkpoint"
    learning.mkdir(parents=True)
    output.mkdir(parents=True)

    (learning / "search-success-memory.json").write_text(
        json.dumps(_search_success_memory()), encoding="utf-8"
    )
    (output / "root-cause-feedback-router.json").write_text(
        json.dumps(_root_cause_feedback()), encoding="utf-8"
    )
    (output / "daily-learning-cycle.json").write_text(
        json.dumps(_daily_learning()), encoding="utf-8"
    )
    (output / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"schema_version": "test", "current_direct_opportunities": ["keep"]}),
        encoding="utf-8",
    )
    (output / "multi-market-phone-summary.txt").write_text(
        "existing summary\n", encoding="utf-8"
    )

    review = write_learning_layer_review(output, input_root=input_root)

    assert review["status"] == "REVIEW_REQUIRED"
    assert (output / "learning-layer-review.json").exists()
    assert (output / "learning-layer-review.txt").exists()

    brief = json.loads(
        (output / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    assert brief["current_direct_opportunities"] == ["keep"]
    assert brief["learning_layer"]["status"] == "REVIEW_REQUIRED"
    assert brief["learning_layer"]["review_item_count"] == 3

    phone = (output / "multi-market-phone-summary.txt").read_text(encoding="utf-8")
    assert "LEARNING LAYER:" in phone
    assert "REVIEW_REQUIRED" in phone
    assert phone.count("LEARNING LAYER:") == 1


def test_learning_layer_hook_runs_after_daily_learning_by_atexit_order() -> None:
    init = INIT.read_text(encoding="utf-8")
    layer_install = init.index("install_learning_layer_review_cli_hook()")
    daily_install = init.index("install_daily_auto_miss_learning_cli_hook()")
    river_install = init.index("install_unified_market_intelligence_river_cli_hook()")

    # atexit is LIFO. Registration order must be:
    # Learning Layer -> daily learner -> river, so runtime order becomes:
    # river/capture -> daily learner -> Learning Layer aggregation.
    assert layer_install < daily_install < river_install

    hook = HOOK.read_text(encoding="utf-8")
    assert 'Path(sys.argv[0]).name != "build_domain_market_intelligence_feed.py"' in hook
    assert "write_learning_layer_review(" in hook
    assert "run_learning_layer_review_fail_closed(" in hook
