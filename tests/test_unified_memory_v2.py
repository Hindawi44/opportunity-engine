from __future__ import annotations

import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.checkpoint_state_restore import LEARNING_STATE_FILENAMES
from opportunity_engine.unified_memory_v2 import (
    MEMORY_FILENAME,
    RULE_REGISTRY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_unified_memory_v2,
    write_unified_memory_v2,
)


ROOT = Path(__file__).resolve().parents[1]
SPINE_HOOK = ROOT / "src/opportunity_engine/discovery/unified_learning_spine_cli_hook.py"
DISCOVERY_INIT = ROOT / "src/opportunity_engine/discovery/__init__.py"


def _record(
    evidence_id: str,
    kind: str,
    *,
    market: str,
    source: str | None = None,
    provider: str | None = None,
    query: str | None = None,
    url: str | None = None,
    result_type: str | None = None,
    outcome: str | None = None,
    miss_reason: str | None = None,
    route: str | None = None,
    source_identity: str | None = None,
    supporting_run_ids: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "learning_evidence_id": evidence_id,
        "evidence_kind": kind,
        "market_code": market,
        "project_domain": "CLOTHING_INVENTORY",
        "source_name": source,
        "provider": provider,
        "query": query,
        "url": url,
        "result_type": result_type,
        "outcome": outcome,
        "miss_reason": miss_reason,
        "route": route,
        "source_identity": source_identity,
        "observed_at": "2026-08-23T20:00:00Z",
        "supporting_run_ids": supporting_run_ids or [],
        "metadata": metadata or {},
    }


def _spine(*, generated_at: str, records: list[dict]) -> dict:
    market_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for row in records:
        market_counts[row["market_code"]] = market_counts.get(row["market_code"], 0) + 1
        kind_counts[row["evidence_kind"]] = kind_counts.get(row["evidence_kind"], 0) + 1
    return {
        "schema_version": "unified-learning-spine-1.0",
        "status": "SUCCESS" if records else "VALID_ZERO",
        "generated_at": generated_at,
        "evidence_record_count": len(records),
        "market_counts": market_counts,
        "domain_counts": {"CLOTHING_INVENTORY": len(records)} if records else {},
        "evidence_kind_counts": kind_counts,
        "records": records,
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


def _run_one() -> dict:
    return _spine(
        generated_at="2026-08-23T20:00:00Z",
        records=[
            _record(
                "e-route-friptadium",
                "SEARCH_ROUTE_SUCCESS",
                market="FR",
                source="friptadium.com",
                provider="exa",
                query="France lot vêtements prix quantité stock",
                url="https://friptadium.com/products/hauts-femme-au-kilo",
                result_type="SEARCH_ROUTE",
                outcome="CANDIDATE",
                route="AGGREGATE_CHILD",
                source_identity="friptadium.com",
                supporting_run_ids=["32663784799"],
                metadata={
                    "independent_run_count": 1,
                    "verified_exact_lot_url_count": 1,
                    "verified_exact_lot_urls": [
                        "https://friptadium.com/products/hauts-femme-au-kilo"
                    ],
                },
            ),
            _record(
                "e-auksjonen-jakke-1",
                "MARKET_OBSERVATION",
                market="NO",
                source="Auksjonen.no",
                url="https://ny.auksjonen.no/auksjon/torget/611144",
                result_type="CANONICAL_OPPORTUNITY",
                outcome="ACTIVE_OPPORTUNITY",
                source_identity="intelligence-item:auksjonen-jakke-1",
            ),
            _record(
                "e-miss-de-1",
                "MISSED_OPPORTUNITY",
                market="DE",
                source="automatic-query-gap-scout",
                result_type="CLOTHING_INVENTORY",
                outcome="MISSED",
                miss_reason="QUERY_GAP",
                source_identity="miss-case-de-1",
            ),
        ],
    )


def _run_two() -> dict:
    return _spine(
        generated_at="2026-08-24T20:00:00Z",
        records=[
            _record(
                "e-route-friptadium",
                "SEARCH_ROUTE_SUCCESS",
                market="FR",
                source="friptadium.com",
                provider="exa",
                query="France lot vêtements prix quantité stock",
                url="https://friptadium.com/products/hauts-femme-au-kilo",
                result_type="SEARCH_ROUTE",
                outcome="REPLICATED_FOR_REVIEW",
                route="AGGREGATE_CHILD",
                source_identity="friptadium.com",
                supporting_run_ids=["32663784799", "32670000000"],
                metadata={
                    "independent_run_count": 2,
                    "verified_exact_lot_url_count": 2,
                    "verified_exact_lot_urls": [
                        "https://friptadium.com/products/hauts-femme-au-kilo",
                        "https://friptadium.com/products/robes-femme-au-kilo",
                    ],
                },
            ),
            _record(
                "e-auksjonen-jakke-1",
                "MARKET_OBSERVATION",
                market="NO",
                source="Auksjonen.no",
                url="https://ny.auksjonen.no/auksjon/torget/611144",
                result_type="CANONICAL_OPPORTUNITY",
                outcome="ACTIVE_OPPORTUNITY",
                source_identity="intelligence-item:auksjonen-jakke-1",
            ),
            _record(
                "e-auksjonen-jakke-2",
                "MARKET_OBSERVATION",
                market="NO",
                source="Auksjonen.no",
                url="https://ny.auksjonen.no/auksjon/torget/611145",
                result_type="CANONICAL_OPPORTUNITY",
                outcome="ACTIVE_OPPORTUNITY",
                source_identity="intelligence-item:auksjonen-jakke-2",
            ),
            _record(
                "e-miss-de-1",
                "MISSED_OPPORTUNITY",
                market="DE",
                source="automatic-query-gap-scout",
                result_type="CLOTHING_INVENTORY",
                outcome="MISSED",
                miss_reason="QUERY_GAP",
                source_identity="miss-case-de-1",
            ),
            _record(
                "e-miss-de-2",
                "MISSED_OPPORTUNITY",
                market="DE",
                source="automatic-query-gap-scout",
                result_type="CLOTHING_INVENTORY",
                outcome="MISSED",
                miss_reason="QUERY_GAP",
                source_identity="miss-case-de-2",
            ),
        ],
    )


def test_memory_v2_remembers_across_runs_and_proves_repeated_patterns() -> None:
    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=_run_one(),
        run_id="32663784799",
    )

    assert first["schema_version"] == SCHEMA_VERSION
    assert first["memory_run_count"] == 1
    assert first["evidence_memory_count"] == 3
    assert first["new_evidence_count"] == 3
    assert first["repeated_success_route_count"] == 0
    assert first["why_failed_counts"] == {"QUERY_GAP": 1}

    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=_run_two(),
        run_id="32670000000",
    )

    assert second["memory_run_count"] == 2
    assert second["evidence_memory_count"] == 5
    assert second["new_evidence_count"] == 2
    assert second["reobserved_evidence_count"] == 3
    assert second["query_memory_count"] == 1
    assert second["why_failed_counts"] == {"QUERY_GAP": 2}
    assert second["repeated_success_route_count"] == 1
    assert second["repeated_success_routes"][0]["pattern_status"] == "PROVEN"
    assert second["repeated_success_routes"][0]["source_identity"] == "friptadium.com"
    assert second["repeated_success_routes"][0]["independent_run_count"] >= 2

    patterns = {(row["pattern_type"], row["pattern_status"]) for row in second["patterns"]}
    assert ("ROUTE_SUCCESS", "PROVEN") in patterns
    assert ("MISS_REASON", "PROVEN") in patterns
    assert ("SOURCE_OUTCOME", "PROVEN") in patterns
    assert second["proven_pattern_count"] == 3
    assert second["rule_review_candidate_count"] == 3
    assert second["fixed_rule_pattern_count"] == 0
    assert second["ai_still_needed_pattern_count"] == second["pattern_count"]
    assert second["automatic_code_change"] is False
    assert second["production_mutation"] is False


def test_memory_v2_is_idempotent_for_same_checkpoint_run() -> None:
    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=_run_one(),
        run_id="32663784799",
    )
    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=_run_two(),
        run_id="32670000000",
    )
    replay = build_unified_memory_v2(
        existing_memory=second,
        unified_learning_spine=_run_two(),
        run_id="32670000000",
    )

    assert replay["memory_run_count"] == 2
    assert replay["new_evidence_count"] == 2
    assert replay["reobserved_evidence_count"] == 3
    route = next(
        row for row in replay["evidence_memory"]
        if row["learning_evidence_id"] == "e-route-friptadium"
    )
    assert route["seen_checkpoint_run_count"] == 2
    assert [row["run_id"] for row in replay["run_history"]] == [
        "32663784799",
        "32670000000",
    ]


def test_fixed_rule_registry_marks_pattern_converted_and_removes_ai_need() -> None:
    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=_run_one(),
        run_id="32663784799",
    )
    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=_run_two(),
        run_id="32670000000",
    )
    route_pattern = next(
        row for row in second["patterns"] if row["pattern_type"] == "ROUTE_SUCCESS"
    )
    registry = {
        "schema_version": RULE_REGISTRY_SCHEMA_VERSION,
        "rules": [
            {
                "rule_id": "rule:fr-exa-friptadium-aggregate-child-v1",
                "pattern_key": route_pattern["pattern_key"],
                "status": "ACTIVE",
                "implemented_in": "future-explicit-reviewed-rule",
            }
        ],
        "automatic_code_change": False,
        "production_mutation": False,
    }

    with_rule = build_unified_memory_v2(
        existing_memory=second,
        unified_learning_spine=_run_two(),
        run_id="32670000000",
        rule_registry=registry,
    )
    route = next(
        row for row in with_rule["patterns"] if row["pattern_type"] == "ROUTE_SUCCESS"
    )

    assert route["converted_to_rule"] is True
    assert route["rule_review_status"] == "FIXED_RULE_ACTIVE"
    assert route["ai_still_needed"] is False
    assert route["ai_role"] == "FIXED_RULE_HANDLES_PATTERN"
    assert with_rule["fixed_rule_pattern_count"] == 1
    assert route["pattern_id"] not in with_rule["ai_still_needed_pattern_ids"]


def test_memory_v2_refuses_unsafe_or_out_of_domain_spine() -> None:
    unsafe = _run_one()
    unsafe["production_mutation"] = True
    with pytest.raises(ValueError, match="production_mutation"):
        build_unified_memory_v2(
            existing_memory=None,
            unified_learning_spine=unsafe,
            run_id="bad-run",
        )

    escaped = _run_one()
    escaped["records"][0]["project_domain"] = "OUT_OF_DOMAIN"
    with pytest.raises(ValueError, match="out-of-domain"):
        build_unified_memory_v2(
            existing_memory=None,
            unified_learning_spine=escaped,
            run_id="bad-domain",
        )


def test_memory_v2_persists_to_checkpoint_learning_state_and_attaches_summary(tmp_path) -> None:
    output = tmp_path / "checkpoint"
    input_root = tmp_path / "inputs"
    output.mkdir(parents=True)
    (output / "unified-learning-spine.json").write_text(
        json.dumps(_run_one()),
        encoding="utf-8",
    )
    (output / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"status": "SUCCESS"}),
        encoding="utf-8",
    )
    (output / "multi-market-phone-summary.txt").write_text(
        "BASE SUMMARY\n",
        encoding="utf-8",
    )

    memory = write_unified_memory_v2(
        output,
        input_root=input_root,
        run_id="32663784799",
        rule_registry_path=None,
    )

    durable = input_root / "learning" / MEMORY_FILENAME
    assert durable.exists()
    assert json.loads(durable.read_text(encoding="utf-8"))["memory_run_count"] == 1
    assert (output / "unified-memory-v2-summary.json").exists()

    brief = json.loads(
        (output / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    assert brief["unified_memory_v2"]["new_evidence_count"] == 3
    phone = (output / "multi-market-phone-summary.txt").read_text(encoding="utf-8")
    assert "UNIFIED MEMORY V2:" in phone
    assert "new evidence: 3" in phone
    assert memory["automatic_query_activation"] is False
    assert memory["automatic_provider_activation"] is False
    assert memory["production_mutation"] is False


def test_memory_v2_is_restorable_and_runtime_order_is_spine_then_memory_then_review() -> None:
    assert MEMORY_FILENAME in LEARNING_STATE_FILENAMES

    hook = SPINE_HOOK.read_text(encoding="utf-8")
    spine_build = hook.index("report = run_unified_learning_spine_fail_closed")
    memory_build = hook.index("memory_report = run_unified_memory_v2_fail_closed")
    assert spine_build < memory_build

    discovery = DISCOVERY_INIT.read_text(encoding="utf-8")
    learning_registration = discovery.index("install_learning_layer_review_cli_hook()")
    spine_registration = discovery.index("install_unified_learning_spine_cli_hook()")
    # atexit is LIFO: Spine/Memory handler executes before Learning Layer.
    assert learning_registration < spine_registration
