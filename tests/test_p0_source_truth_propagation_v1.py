from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    enrich_checkpoint_with_lifecycle,
)
from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    build_multi_market_checkpoint,
)
from opportunity_engine.discovery.one_opportunity_daily_analysis import (
    build_daily_analysis,
)


BAUER_ID = "https://ny.auksjonen.no/auksjon/torget/test/bauer-jakker"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _zero_source(root: Path, name: str, *, market: str, currency: str) -> dict:
    directory = root / name
    _write(directory / "execution-status.json", {"exit_code": 0})
    _write(
        directory / "search-run-report.json",
        {
            "status": "PASS",
            "market_code": market,
            "currency": currency,
            "currency_conversion_performed": False,
        },
    )
    _write(directory / "all-discovered-candidates.json", [])
    _write(directory / "discovery-top5.json", [])
    return {
        "market_code": market,
        "source_name": name,
        "currency": currency,
        "artifact_dir": name,
    }


def _matrix() -> dict:
    return {
        "markets": [
            {"market_code": "NO", "sources": []},
            {"market_code": "SE", "sources": []},
            {"market_code": "DE", "sources": []},
        ]
    }


def test_verified_bauer_truth_survives_checkpoint_lifecycle_and_daily_selection(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "no-auksjonen"
    _write(directory / "execution-status.json", {"exit_code": 0})

    raw_listing = {
        "title": "Halv pall med Bauer jakker",
        "url": BAUER_ID,
        "object_id": 912345,
        "listing_status": "ACTIVE",
        "inventory_lot_signal": True,
        "current_bid_nok": 250,
    }
    _write(
        directory / "auksjonen-live-clothing-listings.json",
        {"scan_complete": True, "errors": [], "listings": [raw_listing]},
    )
    _write(directory / "live-clothing-top5.json", [raw_listing])

    verified_candidate = {
        "title": "Halv pall med Bauer jakker",
        "opportunity_identity": BAUER_ID,
        "listing_status": "ACTIVE",
        "opportunity_state": "ACTIVE_OPPORTUNITY",
        "top5_eligible": True,
        "analysis_eligible": True,
        "verified": True,
        "exact_item_page_verified": True,
        "quantity": 12,
        "condition": "Brukt",
        "location": "Norge",
        "current_bid_nok": 250,
        "price_nok": 250,
        "verification_blockers": [],
        "missing_information": [],
        "analysis_tasks": ["calculate final payable price"],
        "source_urls": [BAUER_ID],
    }
    _write(directory / "all-discovered-candidates.json", [verified_candidate])
    _write(
        directory / "unified-opportunity-report.json",
        {
            "market_code": "NO",
            "currency": "NOK",
            "record_count": 1,
            "conversion_error_count": 0,
            "records": [
                {
                    "opportunity_id": BAUER_ID,
                    "listing_status": "ACTIVE",
                    "evaluation_status": "NOT_EVALUATED",
                    "workflow_status": "ACTIVE_OPPORTUNITY",
                    "metadata": {
                        "lifecycle_reason_code": "ACTIVE_READY_FOR_ANALYSIS"
                    },
                }
            ],
        },
    )

    no_source = {
        "market_code": "NO",
        "source_name": "Auksjonen.no",
        "currency": "NOK",
        "artifact_dir": "no-auksjonen",
        "report_kind": "AUKSJONEN_LIVE",
        "report_file": "auksjonen-live-clothing-listings.json",
        "top5_file": "live-clothing-top5.json",
    }
    se_source = _zero_source(
        tmp_path,
        "se-zero",
        market="SE",
        currency="SEK",
    )
    de_source = _zero_source(
        tmp_path,
        "de-zero",
        market="DE",
        currency="EUR",
    )
    manifest = {"sources": [no_source, se_source, de_source]}

    checkpoint = build_multi_market_checkpoint(
        manifest,
        _matrix(),
        root=tmp_path,
        generated_at="2026-08-16T19:00:00+00:00",
    )

    record = checkpoint["deduplicated_opportunities"][0]
    assert record["opportunity_identity"] == BAUER_ID
    assert record["listing_status"] == "ACTIVE"
    assert record["top5_eligible"] is True
    assert record["analysis_eligible"] is True
    assert record["missing_evidence"] == []
    assert checkpoint["analysis_eligible_count"] == 1
    assert checkpoint["missing_evidence"] == []
    assert checkpoint["next_human_action"]["opportunity_identity"] == BAUER_ID

    enriched = enrich_checkpoint_with_lifecycle(
        checkpoint,
        manifest,
        root=tmp_path,
        restore_status={"status": "NO_PREVIOUS_STATE", "restored_databases": []},
    )
    enriched_record = enriched["deduplicated_opportunities"][0]
    assert enriched_record["analysis_eligible"] is True
    assert enriched_record["missing_evidence"] == []
    assert enriched_record["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert enriched["next_human_action"]["workflow_status"] == "ACTIVE_OPPORTUNITY"

    daily = build_daily_analysis(
        enriched,
        generated_at=datetime(2026, 8, 16, 19, 0, tzinfo=timezone.utc),
    )
    assert daily["selection_status"] == "SELECTED"
    assert daily["eligible_candidate_count"] == 1
    assert daily["selected_opportunity"]["opportunity_identity"] == BAUER_ID
    assert daily["selected_opportunity"]["workflow_status"] == "ACTIVE_OPPORTUNITY"
