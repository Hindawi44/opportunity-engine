from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.unified_operator_report import (
    build_unified_operator_report,
    render_unified_operator_report,
    write_unified_operator_report,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _inputs(root: Path) -> None:
    _write(
        root / "unified-six-market-pipeline-v1.json",
        {
            "generated_at": "2026-09-01T00:00:00+00:00",
            "pipeline_contract": "UNIFIED_SIX_MARKET_PIPELINE_V1",
            "markets": [{"market_code": code} for code in ("NO", "SE", "DE", "FR", "IT", "NL")],
        },
    )
    _write(
        root / "unified-search-runtime-v1.json",
        {
            "status": "SUCCESS",
            "clothing_inventory": {
                "markets": {
                    code: {
                        "status": "SUCCESS",
                        "hits_received": index + 1,
                        "strict_exact_lot_count": index + 2,
                        "exact_lot_urls": [f"https://example.test/{code.lower()}/leader"],
                    }
                    for index, code in enumerate(("NO", "SE", "DE", "FR", "IT", "NL"))
                }
            },
        },
    )
    _write(
        root / "multi-market-daily-checkpoint.json",
        {
            "source_execution_counts": {"SUCCESS": 4, "VALID_ZERO_RESULT": 2},
            "status_counts": {"ACTIVE": 1, "HISTORICAL": 3, "UNRESOLVED": 0},
            "top5_eligible_count": 1,
            "deduplicated_opportunities": [
                {"opportunity_id": "one", "market_code": "NO", "top5_eligible": True},
                {"opportunity_id": "two", "market_code": "NO", "top5_eligible": False},
            ],
            "next_human_action": {"action": "LEGACY_ACTION"},
        },
    )
    _write(
        root / "domain-market-intelligence-brief.json",
        {"selected_human_action": {"action": "DOMAIN_ACTION"}},
    )
    _write(
        root / "central-intelligence-brief.json",
        {
            "status": "SUCCESS",
            "primary_human_action": {
                "action_type": "REVIEW_TOP_ACTIONABLE_OPPORTUNITY",
                "target": "one",
                "reason": "Strongest verified candidate.",
            },
        },
    )


def test_report_uses_one_central_action_and_six_market_truth(tmp_path: Path) -> None:
    _inputs(tmp_path)

    report = build_unified_operator_report(tmp_path)

    assert report["authority"] == "UNIFIED_OPERATOR_REPORT_V1"
    assert report["market_coverage"] == ["NO", "SE", "DE", "FR", "IT", "NL"]
    assert report["primary_human_action"]["authority"] == "CENTRAL_INTELLIGENCE"
    assert report["primary_human_action"]["action"] == "REVIEW_TOP_ACTIONABLE_OPPORTUNITY"
    assert [row["opportunity_id"] for row in report["top5_opportunities"]] == ["one"]
    assert [row["market_code"] for row in report["six_market_search_truth"]] == [
        "NO",
        "SE",
        "DE",
        "FR",
        "IT",
        "NL",
    ]
    assert [row["market_code"] for row in report["market_search_leaders"]] == [
        "NO",
        "SE",
        "DE",
        "FR",
        "IT",
        "NL",
    ]
    assert report["commercial_checkpoint_gap_markets"] == ["SE", "DE", "FR", "IT", "NL"]
    assert report["unconnected_verified_exact_lot_count"] == 25
    assert report["legacy_reports_are_not_operator_authority"] is True

    text = render_unified_operator_report(report)
    assert text.count("الإجراء البشري الوحيد:") == 1
    assert "NO | SE | DE | FR | IT | NL" in text
    assert "NO: 2 | SE: 3 | DE: 4 | FR: 5 | IT: 6 | NL: 7" in text
    assert "SE | DE | FR | IT | NL" in text
    assert "مرشح البحث FR: https://example.test/fr/leader" in text
    assert "LEGACY_ACTION" not in text
    assert "DOMAIN_ACTION" not in text


def test_top5_gives_each_eligible_market_a_slot_before_duplicates(tmp_path: Path) -> None:
    _inputs(tmp_path)
    checkpoint_path = tmp_path / "multi-market-daily-checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["top5_eligible_count"] = 7
    checkpoint["deduplicated_opportunities"] = [
        {"opportunity_id": "no-1", "market_code": "NO", "top5_eligible": True},
        {"opportunity_id": "no-2", "market_code": "NO", "top5_eligible": True},
        {"opportunity_id": "no-3", "market_code": "NO", "top5_eligible": True},
        {"opportunity_id": "fr-1", "market_code": "FR", "top5_eligible": True},
        {"opportunity_id": "it-1", "market_code": "IT", "top5_eligible": True},
        {"opportunity_id": "nl-1", "market_code": "NL", "top5_eligible": True},
        {"opportunity_id": "de-1", "market_code": "DE", "top5_eligible": True},
    ]
    _write(checkpoint_path, checkpoint)

    report = build_unified_operator_report(tmp_path)

    assert [row["opportunity_id"] for row in report["top5_opportunities"]] == [
        "no-1",
        "fr-1",
        "it-1",
        "nl-1",
        "de-1",
    ]
    assert report["top5_market_coverage"] == ["NO", "FR", "IT", "NL", "DE"]
    assert report["top5_market_diversity_enforced"] is True
    assert report["top5_scope"] == "COMMERCIAL_CHECKPOINT_ELIGIBLE_ONLY"


def test_writer_emits_the_only_operator_authority_files(tmp_path: Path) -> None:
    _inputs(tmp_path)

    paths = write_unified_operator_report(tmp_path)

    assert paths["json"].name == "unified-operator-report-v1.json"
    assert paths["text"].name == "unified-operator-report-v1.txt"
    persisted = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert persisted["single_human_action_enforced"] is True
