"""Contract tests for integrating the read-only inbox in the real daily CLI."""
from __future__ import annotations

import json
import sys

from scripts import run_unified_daily_runtime as cli


def test_daily_runtime_exports_source_direct_links_and_study_memory(monkeypatch, tmp_path):
    output = tmp_path / "output"
    input_root = tmp_path / "inputs"
    output.mkdir()
    input_root.mkdir()
    checkpoint = {
        "generated_at": "2026-09-17T01:06:37Z", "commercially_qualified_count": 0,
        "next_human_action": {"action": "NO_IMMEDIATE_ACTION"},
        "deduplicated_opportunities": [{
            "opportunity_identity": "listing-471259920", "title": "Clothes lot",
            "market_code": "NO", "listing_status": "ACTIVE", "canonical_url": None,
            "source_urls": ["https://www.finn.no/recommerce/forsale/item/471259920"],
        }],
    }
    (output / "multi-market-daily-checkpoint.json").write_text(json.dumps(checkpoint))
    (output / "multi-market-phone-summary.txt").write_text("الإجراء البشري الوحيد: انتظر\n")
    needed = ("pipeline", "runtime", "summary", "reconciliation", "operator_report_json", "operator_report_text")
    monkeypatch.setattr(cli, "build_unified_daily_runtime", lambda directory: {name: directory / name for name in needed})
    monkeypatch.setattr(cli, "export_memory", lambda directory: {"deleted_ids": [], "study": [], "later": []})
    monkeypatch.setattr(sys, "argv", ["run_unified_daily_runtime.py", "--output-dir", str(output), "--input-root", str(input_root)])
    assert cli.main() == 0
    result = json.loads((output / "human-listing-review-queue-v1.json").read_text())
    assert result["counts"]["direct_waiting_for_review"] == 1
    assert result["counts"]["commercially_qualified"] == 0
    assert "471259920" in (output / "human-listing-review-queue-v1.txt").read_text()
    summary = (output / "multi-market-phone-summary.txt").read_text()
    assert "471259920" in summary
    assert summary.count("الإجراء البشري الوحيد:") == 1
    assert result["automatic_contact"] is False
    assert result["automatic_purchase"] is False