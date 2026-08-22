from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    has_inventory_lot_signal,
    normalize_public_api_item,
)
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    save_missed_opportunity_memory,
)
from opportunity_engine.parser_gap_rescue import (
    apply_auksjonen_parser_rescue,
    build_parser_rescue_overlay,
    load_parser_rescue_terms,
    write_parser_gap_rescue_overlay,
)

URL = "https://ny.auksjonen.no/auksjon/torget/Sluttlager_med_arbeidsjakker/424242"


def _case(
    case_id: str = "parser-gap-1",
    *,
    cause: str = "PARSER_GAP",
    learning_status: str = "DIAGNOSED",
    repeat: bool = False,
) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="AUTOMATIC_SOURCE_VERIFIED_GAP_DETECTOR",
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_BULK_CLOTHING_STOCK",
        stock_proven=True,
        ground_truth_company="Eksempel Arbeidsklær AS",
        ground_truth_url=URL,
        trace=DiscoveryTrace(
            query_generated=True,
            search_hit=True,
            retrieved=True,
            parsed=False,
            timely_discovery=True,
        ),
        root_cause=cause,
        learning_status=learning_status,
        repeat_miss=repeat,
    )


def _raw_report(*titles: str) -> dict:
    rows = []
    for index, title in enumerate(titles):
        rows.append(
            {
                "title": title,
                "url": URL if index == 0 else f"https://ny.auksjonen.no/auksjon/torget/x/{500000 + index}",
                "listing_status": "ACTIVE",
                "inventory_lot_signal": False,
            }
        )
    return {"listings": rows}


def _active_item(title: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "status": "ACTIVE",
        "bidExpired": False,
        "endTime": int((now + timedelta(days=1)).timestamp() * 1000),
        "auctionId": 123,
        "objectId": 424242,
        "currentBidAmount": 1000,
        "city": "Oslo",
    }


def _collection_for(title: str) -> AuksjonenLiveClothingCollection:
    listing = normalize_public_api_item(_active_item(title))
    assert listing is not None
    return AuksjonenLiveClothingCollection(
        captured_at=datetime.now(timezone.utc).isoformat(),
        endpoint="test",
        reported_size=1,
        items_received=1,
        listings=(listing,),
        pages_fetched=1,
        page_size=30,
        errors=(),
    )


def test_verified_parser_gap_can_prove_strong_new_lot_term() -> None:
    overlay = build_parser_rescue_overlay(
        [_case()],
        _raw_report("Sluttlager med arbeidsjakker"),
    )

    assert overlay["active_term_count"] == 1
    [row] = overlay["sources"]["Auksjonen.no"]
    assert row["term"] == "sluttlager"
    assert row["status"] == "PROVEN_BY_VERIFIED_PARSER_GAP"
    assert row["raw_match_count"] == 1
    assert row["verified_case_ids"] == ["parser-gap-1"]


def test_source_gap_and_other_causes_never_train_parser_overlay() -> None:
    overlay = build_parser_rescue_overlay(
        [_case(cause="SOURCE_GAP")],
        _raw_report("Sluttlager med arbeidsjakker"),
    )

    assert overlay["active_term_count"] == 0
    assert overlay["sources"] == {}


def test_generic_or_company_words_are_not_learned() -> None:
    report = _raw_report("Salg Eksempel Arbeidsklær AS arbeidsjakker")
    overlay = build_parser_rescue_overlay([_case()], report)

    assert overlay["active_term_count"] == 0


def test_noisy_term_is_rejected_when_it_matches_too_many_raw_titles() -> None:
    titles = ["Sluttlager med arbeidsjakker"] + [
        f"Sluttlager med jakker modell {index}" for index in range(1, 8)
    ]
    overlay = build_parser_rescue_overlay(
        [_case()],
        _raw_report(*titles),
        max_raw_matches_per_term=5,
    )

    assert overlay["active_term_count"] == 0
    assert overlay["rejected_noisy_terms"] == ["sluttlager"]


def test_learned_term_only_rescues_already_normalized_clothing_listing() -> None:
    assert has_inventory_lot_signal("Sluttlager med arbeidsjakker") is False
    collection = _collection_for("Sluttlager med arbeidsjakker")
    assert collection.listings[0].inventory_lot_signal is False

    rescued = apply_auksjonen_parser_rescue(collection, ("sluttlager",))

    assert rescued.listings[0].inventory_lot_signal is True
    assert len(rescued.inventory_opportunities) == 1

    # The static clothing gate remains authoritative: this title never enters
    # the collection, so the rescue layer cannot promote it.
    assert normalize_public_api_item(_active_item("Sluttlager med gravemaskiner")) is None


def test_empty_overlay_changes_nothing() -> None:
    collection = _collection_for("Sluttlager med arbeidsjakker")
    rescued = apply_auksjonen_parser_rescue(collection, ())

    assert rescued == collection
    assert rescued.listings[0].inventory_lot_signal is False


def test_existing_static_lot_pattern_does_not_need_rescue_term() -> None:
    overlay = build_parser_rescue_overlay(
        [_case()],
        _raw_report("Varelager med arbeidsjakker"),
    )

    assert has_inventory_lot_signal("Varelager med arbeidsjakker") is True
    assert overlay["active_term_count"] == 0


def test_existing_proven_overlay_terms_are_retained_and_bounded() -> None:
    existing = {
        "schema_version": "parser-gap-rescue-overlay-1.0",
        "sources": {
            "Auksjonen.no": [
                {
                    "term": "restparti",
                    "status": "PROVEN_BY_VERIFIED_PARSER_GAP",
                    "raw_match_count": 1,
                    "verified_case_ids": ["older"],
                }
            ]
        },
    }
    overlay = build_parser_rescue_overlay(
        [_case()],
        _raw_report("Sluttlager med arbeidsjakker"),
        existing_overlay=existing,
        max_terms_per_source=2,
    )

    terms = [row["term"] for row in overlay["sources"]["Auksjonen.no"]]
    assert terms == ["restparti", "sluttlager"]
    assert overlay["active_term_count"] == 2


def test_writer_reads_durable_parser_cases_and_writes_next_run_overlay(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "checkpoint"
    source_dir = tmp_path / "artifacts" / "no-auksjonen"
    output_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)

    save_missed_opportunity_memory(
        input_root / "learning" / "missed-opportunities.json",
        [_case()],
    )
    (output_dir / "input-manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "market_code": "NO",
                        "source_name": "Auksjonen.no",
                        "artifact_dir": "artifacts/no-auksjonen",
                        "report_file": "auksjonen-live-clothing-listings.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (source_dir / "auksjonen-live-clothing-listings.json").write_text(
        json.dumps(_raw_report("Sluttlager med arbeidsjakker")),
        encoding="utf-8",
    )

    report = write_parser_gap_rescue_overlay(
        output_dir,
        input_root=input_root,
        root=tmp_path,
    )

    overlay_path = input_root / "learning" / "parser-rescue-overlay.json"
    assert overlay_path.exists()
    assert load_parser_rescue_terms(overlay_path, "Auksjonen.no") == ("sluttlager",)
    assert report["new_term_count"] == 1
    assert report["network_requests"] == 0
    assert report["automatic_purchase"] is False


def test_recovered_non_repeat_parser_case_can_leave_retained_skill_active() -> None:
    existing = {
        "schema_version": "parser-gap-rescue-overlay-1.0",
        "sources": {
            "Auksjonen.no": [
                {
                    "term": "sluttlager",
                    "status": "PROVEN_BY_VERIFIED_PARSER_GAP",
                    "raw_match_count": 1,
                    "verified_case_ids": ["parser-gap-1"],
                }
            ]
        },
    }
    overlay = build_parser_rescue_overlay(
        [_case(learning_status="RECOVERED")],
        _raw_report("Sluttlager med arbeidsjakker"),
        existing_overlay=existing,
    )

    assert [row["term"] for row in overlay["sources"]["Auksjonen.no"]] == [
        "sluttlager"
    ]


def test_restore_allowlist_contains_parser_rescue_overlay() -> None:
    source = Path(
        "src/opportunity_engine/discovery/checkpoint_state_restore.py"
    ).read_text(encoding="utf-8")

    assert '"parser-rescue-overlay.json"' in source
