from __future__ import annotations

import json
from pathlib import Path

import pytest

from opportunity_engine.production_search_outcome_bridge_v1 import (
    EVIDENCE_KIND,
    SCHEMA_VERSION as LIVE_BRIDGE_SCHEMA,
    augment_unified_learning_spine,
)
from opportunity_engine.production_search_outcome_history_seed_compact_v1 import (
    load_compact_historical_query_outcome_seed,
)
from opportunity_engine.production_search_outcome_history_seed_v1 import (
    augment_unified_learning_spine_with_history,
    install_historical_query_outcome_memory_metrics,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY
from opportunity_engine.unified_learning_spine import build_unified_learning_spine
from opportunity_engine.unified_memory_v2 import build_unified_memory_v2


MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
SAFETY_FALSE_FIELDS = (
    "automatic_query_activation",
    "automatic_provider_activation",
    "automatic_source_promotion",
    "automatic_code_change",
    "production_query_mutation",
    "production_mutation",
    "automatic_contact",
    "automatic_bid",
    "automatic_reservation",
    "automatic_purchase",
    "automatic_payment",
)


def _empty_spine(*, generated_at: str) -> dict:
    spine = build_unified_learning_spine(
        unified_intelligence_items=None,
        search_success_memory=None,
        missed_opportunity_memory=None,
        daily_learning=None,
    )
    spine["generated_at"] = generated_at
    return spine


def _complete_live_bridge(*, generated_at: str, include_record: bool = False) -> dict:
    records = []
    if include_record:
        records.append(
            {
                "outcome_id": "production-search-outcome:live-se-query",
                "market_code": "SE",
                "project_domain": CLOTHING_INVENTORY,
                "provider": "exa",
                "query": "Sverige restparti kläder grossist lager",
                "query_stage": "PRIMARY",
                "search_request_count": 1,
                "hits_received": 5,
                "fresh_strict_exact_lot_count": 1,
                "fresh_strict_exact_lot_urls": ["https://live.test/se/one"],
                "recovery_exact_lot_count": 0,
                "fresh_yield_per_request": 1.0,
                "outcome": "FRESH_SUCCESS",
                "generated_at": generated_at,
                "source_path": "se-exa-exact-lot/exa-exact-lot-resolution.json",
                "recovery_query_credit_blocked": True,
                **{field: False for field in SAFETY_FALSE_FIELDS},
            }
        )
    return {
        "schema_version": LIVE_BRIDGE_SCHEMA,
        "status": "SUCCESS",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "market_coverage": list(MARKETS),
        "query_outcome_count": len(records),
        "search_request_count": len(records),
        "hits_received": sum(row["hits_received"] for row in records),
        "fresh_strict_exact_lot_count": sum(
            row["fresh_strict_exact_lot_count"] for row in records
        ),
        "recovery_strict_exact_lot_count": 0,
        "unattributed_fresh_exact_lot_count": 0,
        "market_status": {
            market: {
                "status": "SUCCESS",
                "resolution": True,
                "candidates": True,
                "search_report": True,
            }
            for market in MARKETS
        },
        "records": records,
        "recovery_query_credit_blocked": True,
        **{field: False for field in SAFETY_FALSE_FIELDS},
    }


def _history_spine(*, generated_at: str = "2026-09-02T08:00:00+00:00") -> dict:
    seed = load_compact_historical_query_outcome_seed()
    return augment_unified_learning_spine_with_history(
        _empty_spine(generated_at=generated_at),
        seed,
        live_bridge=_complete_live_bridge(generated_at=generated_at),
    )


def _query(memory: dict, *, market: str, query: str) -> dict:
    return next(
        row
        for row in memory["query_memory"]
        if row["market_code"] == market and row["provider"] == "exa" and row["query"] == query
    )


def test_compact_seed_reconciles_five_independent_days() -> None:
    seed = load_compact_historical_query_outcome_seed()

    assert seed["market_coverage"] == list(MARKETS)
    assert seed["independent_checkpoint_day_count"] == 5
    assert seed["source_run_count"] == 5
    assert seed["query_outcome_count"] == 99
    assert seed["search_request_count"] == 99
    assert seed["hits_received"] == 487
    assert seed["fresh_strict_exact_lot_count"] == 196
    assert seed["unique_fresh_strict_exact_lot_count"] == 85
    assert seed["recovery_strict_exact_lot_count"] == 200
    assert seed["unattributed_fresh_exact_lot_count"] == 0
    assert seed["recovery_query_credit_blocked"] is True
    assert [row["sample_date"] for row in seed["source_runs"]] == [
        "2026-08-28",
        "2026-08-29",
        "2026-08-30",
        "2026-08-31",
        "2026-09-01",
    ]
    assert len({row["source_run_id"] for row in seed["source_runs"]}) == 5


def test_history_preserves_query_pack_evolution_instead_of_smearing_success() -> None:
    seed = load_compact_historical_query_outcome_seed()
    runs = {row["source_run_id"]: row["sample_date"] for row in seed["source_runs"]}

    old_no = "Norge klær vareparti nettauksjon auksjon plagg til salgs pris stk"
    new_no = "Norge klær vareparti nettauksjon konkursbo lager pris antall stk"
    old_dates = {
        runs[row["source_run_id"]]
        for row in seed["records"]
        if row["market_code"] == "NO" and row["query"] == old_no
    }
    new_dates = {
        runs[row["source_run_id"]]
        for row in seed["records"]
        if row["market_code"] == "NO" and row["query"] == new_no
    }

    assert old_dates == {"2026-08-28", "2026-08-29", "2026-08-30"}
    assert new_dates == {"2026-08-31", "2026-09-01"}
    assert old_dates.isdisjoint(new_dates)


def test_history_suppresses_same_day_live_observation_but_keeps_next_day() -> None:
    seed = load_compact_historical_query_outcome_seed()

    live_sep1 = _complete_live_bridge(
        generated_at="2026-09-01T10:00:00+00:00",
        include_record=True,
    )
    spine_sep1 = augment_unified_learning_spine(
        _empty_spine(generated_at="2026-09-01T10:00:00+00:00"),
        live_sep1,
    )
    merged_sep1 = augment_unified_learning_spine_with_history(
        spine_sep1,
        seed,
        live_bridge=live_sep1,
    )
    production_sep1 = [
        row for row in merged_sep1["records"] if row["evidence_kind"] == EVIDENCE_KIND
    ]
    assert len(production_sep1) == 99
    assert merged_sep1["production_search_outcome_history_seed"][
        "live_same_day_records_suppressed"
    ] == 1
    assert merged_sep1["production_search_outcome_history_seed"][
        "suppressed_live_same_day_dates"
    ] == ["2026-09-01"]

    live_sep2 = _complete_live_bridge(
        generated_at="2026-09-02T10:00:00+00:00",
        include_record=True,
    )
    spine_sep2 = augment_unified_learning_spine(
        _empty_spine(generated_at="2026-09-02T10:00:00+00:00"),
        live_sep2,
    )
    merged_sep2 = augment_unified_learning_spine_with_history(
        spine_sep2,
        seed,
        live_bridge=live_sep2,
    )
    production_sep2 = [
        row for row in merged_sep2["records"] if row["evidence_kind"] == EVIDENCE_KIND
    ]
    assert len(production_sep2) == 100
    assert merged_sep2["production_search_outcome_history_seed"][
        "live_same_day_records_suppressed"
    ] == 0


def test_memory_history_is_idempotent_and_exposes_unique_yield() -> None:
    install_historical_query_outcome_memory_metrics()
    spine = _history_spine()

    first = build_unified_memory_v2(
        existing_memory=None,
        unified_learning_spine=spine,
        run_id="current-run-1",
        rule_registry={},
    )
    second = build_unified_memory_v2(
        existing_memory=first,
        unified_learning_spine=spine,
        run_id="current-run-2",
        rule_registry={},
    )

    se = _query(
        second,
        market="SE",
        query="Sverige restparti kläder grossist lager",
    )
    assert se["production_search_request_count"] == 5
    assert se["fresh_strict_exact_lot_count"] == 5
    assert se["unique_fresh_strict_exact_lot_count"] == 1
    assert se["fresh_yield_per_request"] == 1.0
    assert se["unique_fresh_yield_per_request"] == pytest.approx(0.2)
    assert se["independent_checkpoint_day_count"] == 5
    assert se["historical_seed_observation_count"] == 5
    assert se["recovery_exact_lot_query_credit"] == 0

    fr = _query(
        second,
        market="FR",
        query=(
            "France vêtements clothing Pronovias déstockage grossiste stock lot à vendre"
        ),
    )
    assert fr["production_search_request_count"] == 4
    assert fr["fresh_strict_exact_lot_count"] == 28
    assert fr["unique_fresh_strict_exact_lot_count"] == 17
    assert fr["fresh_yield_per_request"] == 7.0
    assert fr["unique_fresh_yield_per_request"] == pytest.approx(4.25)
    assert fr["independent_checkpoint_day_count"] == 4


def test_history_does_not_apply_to_incomplete_live_market_set() -> None:
    seed = load_compact_historical_query_outcome_seed()
    incomplete = _complete_live_bridge(generated_at="2026-09-02T08:00:00+00:00")
    incomplete["market_status"]["NL"]["resolution"] = False
    spine = _empty_spine(generated_at="2026-09-02T08:00:00+00:00")

    output = augment_unified_learning_spine_with_history(
        spine,
        seed,
        live_bridge=incomplete,
    )

    assert output["evidence_record_count"] == 0
    assert output["production_search_outcome_history_seed"]["status"] == (
        "SKIPPED_INCOMPLETE_LIVE_MARKET_SET"
    )


def test_corrupted_compact_seed_is_rejected(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "config/learning/production-search-outcome-history-seed-v1.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["market_coverage"].append("DK")
    corrupted = tmp_path / "corrupted-seed.json"
    corrupted.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="six markets"):
        load_compact_historical_query_outcome_seed(corrupted)
