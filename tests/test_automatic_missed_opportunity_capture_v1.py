from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from opportunity_engine.automatic_missed_opportunity_capture import (
    detect_verified_core_misses,
    write_automatic_missed_opportunity_capture,
)
from opportunity_engine.missed_opportunity_learning import (
    load_missed_opportunity_memory,
    save_missed_opportunity_memory,
)


URL = "https://ny.auksjonen.no/auksjon/arbeidsjakker/424242"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest() -> dict:
    return {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "artifacts/no-auksjonen",
                "report_file": "raw.json",
                "candidates_file": "candidates.json",
                "unified_report_file": "unified.json",
            }
        ]
    }


def _checkpoint(*, urls: tuple[str, ...] = ()) -> dict:
    return {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": f"known-{index}",
                "canonical_url": url,
                "source_urls": [],
            }
            for index, url in enumerate(urls)
        ]
    }


def _verification(*, quantity: int | None = 280, verified: bool = True) -> dict:
    return {
        "generated_at": "2026-08-22T07:30:00+00:00",
        "verifications": [
            {
                "source_kind": "AUKSJONEN_EXACT_ITEM",
                "country": "NO",
                "target_label": "Eksempel Arbeidsklær AS",
                "search_result_title": "Parti med 280 arbeidsjakker fra Eksempel Arbeidsklær AS",
                "title": "280 arbeidsjakker - varelager",
                "canonical_source_url": URL,
                "source_url": URL,
                "source_page_verified": verified,
                "entity_link_verified": verified,
                "commercial_facts_confirmed": verified,
                "quantity": quantity,
                "pallet_count": None,
                "source_start_or_minimum_price": 12000,
            }
        ],
    }


def _artifact_dir(tmp_path: Path) -> Path:
    return tmp_path / "artifacts" / "no-auksjonen"


def test_verified_bulk_item_absent_from_raw_source_is_source_gap(tmp_path: Path) -> None:
    _write(_artifact_dir(tmp_path) / "raw.json", {"listings": []})

    cases = detect_verified_core_misses(
        _checkpoint(),
        _manifest(),
        _verification(),
        root=tmp_path,
    )

    assert len(cases) == 1
    case = cases[0]
    assert case.market_code == "NO"
    assert case.stock_proven is True
    assert case.ground_truth_company == "Eksempel Arbeidsklær AS"
    assert case.ground_truth_url == URL
    assert case.root_cause == "SOURCE_GAP"
    assert case.trace.query_generated is True
    assert case.trace.search_hit is False


def test_raw_seen_but_not_candidate_is_parser_gap(tmp_path: Path) -> None:
    _write(_artifact_dir(tmp_path) / "raw.json", {"listings": [{"url": URL}]})
    _write(_artifact_dir(tmp_path) / "candidates.json", [])

    [case] = detect_verified_core_misses(
        _checkpoint(), _manifest(), _verification(), root=tmp_path
    )

    assert case.root_cause == "PARSER_GAP"
    assert case.trace.search_hit is True
    assert case.trace.parsed is False


def test_candidate_without_canonical_record_is_verification_gap(tmp_path: Path) -> None:
    _write(_artifact_dir(tmp_path) / "raw.json", {"listings": [{"url": URL}]})
    _write(_artifact_dir(tmp_path) / "candidates.json", [{"canonical_url": URL}])
    _write(_artifact_dir(tmp_path) / "unified.json", {"records": []})

    [case] = detect_verified_core_misses(
        _checkpoint(), _manifest(), _verification(), root=tmp_path
    )

    assert case.root_cause == "VERIFICATION_GAP"
    assert case.trace.parsed is True
    assert case.trace.verified is False


def test_canonical_record_missing_from_checkpoint_is_reporting_gap(tmp_path: Path) -> None:
    _write(_artifact_dir(tmp_path) / "raw.json", {"listings": [{"url": URL}]})
    _write(_artifact_dir(tmp_path) / "candidates.json", [{"canonical_url": URL}])
    _write(
        _artifact_dir(tmp_path) / "unified.json",
        {"records": [{"canonical_url": URL}]},
    )

    [case] = detect_verified_core_misses(
        _checkpoint(), _manifest(), _verification(), root=tmp_path
    )

    assert case.root_cause == "REPORTING_GAP"
    assert case.trace.verified is True
    assert case.trace.reported is False


def test_item_already_present_in_checkpoint_is_not_a_miss(tmp_path: Path) -> None:
    _write(_artifact_dir(tmp_path) / "raw.json", {"listings": [{"url": URL}]})

    cases = detect_verified_core_misses(
        _checkpoint(urls=(URL,)),
        _manifest(),
        _verification(),
        root=tmp_path,
    )

    assert cases == []


def test_search_hit_or_single_item_is_never_promoted_to_ground_truth(tmp_path: Path) -> None:
    _write(_artifact_dir(tmp_path) / "raw.json", {"listings": []})

    unverified = detect_verified_core_misses(
        _checkpoint(),
        _manifest(),
        _verification(verified=False),
        root=tmp_path,
    )
    single_item = detect_verified_core_misses(
        _checkpoint(),
        _manifest(),
        _verification(quantity=1),
        root=tmp_path,
    )

    assert unverified == []
    assert single_item == []


def test_writer_persists_new_case_and_marks_repeat_after_recovery(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts" / "checkpoint"
    input_root = tmp_path / "artifacts" / "multi-market-inputs"
    source_dir = _artifact_dir(tmp_path)
    _write(source_dir / "raw.json", {"listings": []})
    _write(output_dir / "multi-market-daily-checkpoint.json", _checkpoint())
    _write(output_dir / "input-manifest.json", _manifest())
    _write(output_dir / "signal-follow-up-source-verification.json", _verification())

    first = write_automatic_missed_opportunity_capture(
        output_dir,
        input_root=input_root,
        root=tmp_path,
    )
    assert first["new_case_count"] == 1
    memory_path = input_root / "learning" / "missed-opportunities.json"
    [stored] = load_missed_opportunity_memory(memory_path)

    recovered = replace(
        stored,
        learning_status="RECOVERED",
        learned_patterns=("avviklingssalg",),
    )
    save_missed_opportunity_memory(memory_path, [recovered])

    second = write_automatic_missed_opportunity_capture(
        output_dir,
        input_root=input_root,
        root=tmp_path,
    )
    [repeated] = load_missed_opportunity_memory(memory_path)

    assert second["new_case_count"] == 0
    assert second["repeat_miss_count_this_run"] == 1
    assert repeated.repeat_miss is True
    assert repeated.learning_status == "RECOVERED"
    assert repeated.learned_patterns == ("avviklingssalg",)
    assert second["automatic_query_activation"] is False
    assert second["automatic_purchase"] is False


def test_daily_hook_runs_capture_after_source_verification() -> None:
    hook = Path(
        "src/opportunity_engine/discovery/unified_market_intelligence_river_cli_hook.py"
    ).read_text(encoding="utf-8")

    assert "write_automatic_missed_opportunity_capture" in hook
    assert hook.index("write_signal_follow_up_source_verification(") < hook.index(
        "write_automatic_missed_opportunity_capture("
    )
