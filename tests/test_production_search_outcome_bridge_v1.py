from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.auksjonen_route_learning import (
    write_unified_learning_spine_with_native_routes,
)
from opportunity_engine.production_search_outcome_bridge_v1 import (
    EVIDENCE_KIND,
    OUTPUT_FILENAME,
    augment_unified_learning_spine,
    build_production_search_outcome_bridge,
    install_unified_memory_query_outcome_metrics,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY
from opportunity_engine.unified_learning_spine import build_unified_learning_spine
from opportunity_engine.unified_memory_v2 import build_unified_memory_v2


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolution(*, generated_at: str, q1: str, q2: str) -> dict:
    return {
        "schema_version": "exa-exact-lot-checkpoint-resolution-1.8",
        "generated_at": generated_at,
        "market": "NO",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "queries": [
            {
                "query": q1,
                "query_stage": "PRIMARY",
                "hits": [
                    {"title": "one", "url": "https://search.test/1", "description": ""},
                    {"title": "two", "url": "https://search.test/2", "description": ""},
                ],
            },
            {
                "query": q2,
                "query_stage": "FRESH_RECALL",
                "hits": [
                    {"title": "three", "url": "https://search.test/3", "description": ""}
                ],
            },
        ],
        "production_mutation": False,
    }


def _candidate(url: str, *, query: str = "", provenance: str = "MULTI_HOP") -> dict:
    return {
        "canonical_urls": [url],
        "source_urls": [url],
        "opportunity_identity": url,
        "found_by_queries": [query] if query else [],
        "retrieval_provenance": provenance,
        "exact_lot_origin": provenance,
        "route_memory_reverified": provenance == "PROVEN_ROUTE_RECOVERY",
    }


def _write_market_artifacts(
    root: Path,
    *,
    generated_at: str,
    fresh_q1: int = 1,
    fresh_q2: int = 0,
    unattributed_fresh: int = 0,
    recovery: int = 0,
) -> tuple[str, str]:
    q1 = "Norge klær vareparti nettauksjon konkursbo lager pris antall stk"
    q2 = "Norge klær restparti grossist lager pris antall stk"
    source = root / "no-exa-exact-lot"
    resolution = _resolution(generated_at=generated_at, q1=q1, q2=q2)
    candidates: list[dict] = []
    for index in range(fresh_q1):
        candidates.append(_candidate(f"https://fresh.test/q1/{index}", query=q1))
    for index in range(fresh_q2):
        candidates.append(_candidate(f"https://fresh.test/q2/{index}", query=q2))
    for index in range(unattributed_fresh):
        candidates.append(_candidate(f"https://fresh.test/unattributed/{index}"))
    for index in range(recovery):
        candidates.append(
            _candidate(
                f"https://recovery.test/{index}",
                query=q2,
                provenance="PROVEN_ROUTE_RECOVERY",
            )
        )

    fresh_total = fresh_q1 + fresh_q2 + unattributed_fresh
    _write_json(source / "exa-exact-lot-resolution.json", resolution)
    _write_json(source / "all-discovered-candidates.json", candidates)
    _write_json(
        source / "search-run-report.json",
        {
            "market_code": "NO",
            "queries_submitted": 2,
            "strict_exact_lot_count": len(candidates),
            "current_exa_discovery_strict_exact_lot_count": fresh_total,
            "freshly_reverified_recovery_exact_lot_count": recovery,
        },
    )
    return q1, q2


def _empty_spine(*, generated_at: str) -> dict:
    spine = build_unified_learning_spine(
        unified_intelligence_items=None,
        search_success_memory=None,
        missed_opportunity_memory=None,
        daily_learning=None,
    )
    spine["generated_at"] = generated_at
    return spine


def test_bridge_counts_only_fresh_exact_lots_as_query_yield(tmp_path: Path) -> None:
    q1, q2 = _write_market_artifacts(
        tmp_path,
        generated_at="2026-09-01T08:00:00+00:00",
        fresh_q1=1,
        unattributed_fresh=1,
        recovery=1,
    )

    bridge = build_production_search_outcome_bridge(input_root=tmp_path)

    assert bridge["status"] == "SUCCESS"
    assert bridge["query_outcome_count"] == 2
    assert bridge["search_request_count"] == 2
    assert bridge["fresh_strict_exact_lot_count"] == 2
    assert bridge["recovery_strict_exact_lot_count"] == 1
    assert bridge["unattributed_fresh_exact_lot_count"] == 1
    assert bridge["market_status"]["NO"]["fresh_attribution_complete"] is False

    by_query = {row["query"]: row for row in bridge["records"]}
    assert by_query[q1]["fresh_strict_exact_lot_count"] == 1
    assert by_query[q1]["fresh_yield_per_request"] == 1.0
    assert by_query[q2]["fresh_strict_exact_lot_count"] == 0
    assert by_query[q2]["recovery_exact_lot_count"] == 0
    assert by_query[q2]["recovery_query_credit_blocked"] is True


def test_bridge_augments_spine_with_production_query_evidence(tmp_path: Path) -> None:
    _write_market_artifacts(
        tmp_path,
        generated_at="2026-09-01T08:00:00+00:00",
        fresh_q1=1,
        fresh_q2=1,
    )
    bridge = build_production_search_outcome_bridge(input_root=tmp_path)
    spine = augment_unified_learning_spine(
        _empty_spine(generated_at="2026-09-01T08:00:00+00:00"),
        bridge,
    )

    assert spine["status"] == "SUCCESS"
    assert spine["evidence_record_count"] == 2
    assert spine["evidence_kind_counts"] == {EVIDENCE_KIND: 2}
    assert spine["market_counts"] == {"NO": 2}
    assert spine["production_search_outcome_bridge"]["search_request_count"] == 2
    assert all(row["evidence_kind"] == EVIDENCE_KIND for row in spine["records"])


def test_memory_accumulates_fresh_yield_across_runs() -> None:
    install_unified_memory_query_outcome_metrics()
    query = "Norge klær vareparti nettauksjon konkursbo lager pris antall stk"

    def bridge(*, generated_at: str, fresh: int) -> dict:
        urls = [f"https://fresh.test/{generated_at[:10]}/{index}" for index in range(fresh)]
        return {
            "schema_version": "production-search-outcome-bridge-1.0",
            "status": "SUCCESS",
            "records": [
                {
                    "outcome_id": "production-search-outcome:stable-query",
                    "market_code": "NO",
                    "project_domain": CLOTHING_INVENTORY,
                    "provider": "exa",
                    "query": query,
                    "query_stage": "PRIMARY",
                    "search_request_count": 1,
                    "hits_received": 5,
                    "fresh_strict_exact_lot_count": fresh,
                    "fresh_strict_exact_lot_urls": urls,
                    "recovery_exact_lot_count": 0,
                    "fresh_yield_per_request": float(fresh),
                    "outcome": "FRESH_SUCCESS" if fresh else "FRESH_ZERO",
                    "generated_at": generated_at,
                    "source_path": "no-exa-exact-lot/exa-exact-lot-resolution.json",
                    "recovery_query_credit_blocked": True,
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
            ],
            "query_outcome_count": 1,
            "search_request_count": 1,
            "fresh_strict_exact_lot_count": fresh,
            "recovery_strict_exact_lot_count": 0,
            "unattributed_fresh_exact_lot_count": 0,
            "recovery_query_credit_blocked": True,
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

    first_spine = augment_unified_learning_spine(
        _empty_spine(generated_at="2026-09-01T08:00:00+00:00"),
        bridge(generated_at="2026-09-01T08:00:00+00:00", fresh=1),
    )
    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=first_spine,
        run_id="run-1",
        rule_registry={},
    )

    second_spine = augment_unified_learning_spine(
        _empty_spine(generated_at="2026-09-02T08:00:00+00:00"),
        bridge(generated_at="2026-09-02T08:00:00+00:00", fresh=0),
    )
    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=second_spine,
        run_id="run-2",
        rule_registry={},
    )

    assert second["query_memory_count"] == 1
    memory = second["query_memory"][0]
    assert memory["production_search_request_count"] == 2
    assert memory["production_hits_received"] == 10
    assert memory["fresh_strict_exact_lot_count"] == 1
    assert memory["fresh_yield_per_request"] == 0.5
    assert memory["fresh_success_run_count"] == 1
    assert memory["fresh_zero_run_count"] == 1
    assert memory["recovery_exact_lot_query_credit"] == 0
    assert memory["query_stage_counts"] == {"PRIMARY": 2}


def test_daily_spine_writer_emits_bridge_artifact_and_evidence(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output = tmp_path / "output"
    _write_market_artifacts(
        input_root,
        generated_at="2026-09-01T08:00:00+00:00",
        fresh_q1=1,
    )

    spine = write_unified_learning_spine_with_native_routes(
        output,
        input_root=input_root,
    )

    assert (output / OUTPUT_FILENAME).exists()
    assert (output / "unified-learning-spine.json").exists()
    assert spine["production_search_outcome_bridge"]["status"] == "SUCCESS"
    assert spine["evidence_kind_counts"][EVIDENCE_KIND] == 2
