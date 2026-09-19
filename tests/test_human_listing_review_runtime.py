"""Contract tests for the auction-only read-only inbox in the real daily CLI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys

from scripts import run_unified_daily_runtime as cli

AUK = "https://www.auksjonen.no/auksjon/overskuddsvarer/arbeidsklaer-parti/574797"
FINN = "https://www.finn.no/recommerce/forsale/item/471259920"


def test_daily_runtime_exports_only_auction_lots_and_preserves_review_memory(monkeypatch, tmp_path):
    output = tmp_path / "output"
    input_root = tmp_path / "inputs"
    output.mkdir()
    input_root.mkdir()
    now = datetime.now(timezone.utc)
    checkpoint = {
        "generated_at": (now + timedelta(minutes=1)).isoformat(), "commercially_qualified_count": 0,
        "next_human_action": {"action": "NO_IMMEDIATE_ACTION"},
        "deduplicated_opportunities": [
            {"opportunity_identity": "listing-471259920", "title": "Classified advert",
             "market_code": "NO", "listing_status": "ACTIVE", "canonical_url": None,
             "source_urls": [FINN]},
            {"opportunity_identity": AUK, "title": "Clothing auction lot",
             "market_code": "NO", "listing_status": "ACTIVE", "canonical_url": None,
             "source_urls": [AUK]},
        ],
    }
    (output / "multi-market-daily-checkpoint.json").write_text(json.dumps(checkpoint))
    (output / "multi-market-phone-summary.txt").write_text("الإجراء البشري الوحيد: انتظر\n")
    snapshot = input_root / "no-auksjonen" / "auksjonen-live-clothing-listings.json"
    snapshot.parent.mkdir()
    snapshot.write_text(json.dumps({
        "schema_version": "auksjonen-live-clothing-test-v1", "captured_at": now.isoformat(),
        "listings": [{"source": "Auksjonen Public API", "url": AUK, "status": "INPROGRESS",
                      "listing_status": "ACTIVE", "ends_at": (now + timedelta(days=2)).isoformat()}],
    }))
    needed = ("pipeline", "runtime", "summary", "reconciliation", "operator_report_json", "operator_report_text")
    monkeypatch.setattr(cli, "build_unified_daily_runtime", lambda directory: {name: directory / name for name in needed})
    monkeypatch.setattr(cli, "ingest_explicit_events", lambda directory: {"status": "NO_EVENTS", "events_seen": 0})
    monkeypatch.setattr(cli, "export_memory", lambda directory: {"deleted_ids": [], "study": [], "later": []})
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("OPPORTUNITY_ENGINE_SOURCE_PAGE_AUDIT", raising=False)
    monkeypatch.delenv("OPPORTUNITY_ENGINE_PSAUCTION_CHILD_EXTRACTION", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_unified_daily_runtime.py", "--output-dir", str(output), "--input-root", str(input_root)])
    assert cli.main() == 0
    result = json.loads((output / "human-listing-review-queue-v1.json").read_text())
    assert result["counts"]["review_policy"] == "AUCTION_ONLY_SOURCE_NATIVE_STATUS_REQUIRED_V1"
    assert result["counts"]["direct_waiting_for_review"] == 1
    assert result["counts"]["advertisements_and_nonauction_pages_hidden_from_review"] == 1
    assert result["counts"]["commercially_qualified"] == 0
    assert result["daily_batch"][0]["source_url"] == AUK
    assert result["daily_batch"][0]["opportunity_confirmed"] is False
    text = (output / "human-listing-review-queue-v1.txt").read_text()
    summary = (output / "multi-market-phone-summary.txt").read_text()
    assert "مزادات فقط" in text and AUK in text and FINN not in text
    assert AUK in summary and FINN not in summary
    assert summary.count("الإجراء البشري الوحيد:") == 1
    assert result["automatic_contact"] is False
    assert result["automatic_purchase"] is False
