from __future__ import annotations

import json
from pathlib import Path

from scripts.build_scored_opportunities import score_opportunity
from scripts.run_p2_pipeline import build_p2_stages, enrich_daily_report


def _item(**overrides):
    item = {
        "opportunity_id": "opp-1",
        "title": "Kontorstol og butikkinnredning",
        "description": "Lett og demontert",
        "relevance_score": 90,
        "priority": 1,
        "asking_price_nok": 5_000,
        "city": "Namsos",
        "ends_at": "2026-07-30T10:00:00+00:00",
        "source": "Auksjonen.no",
    }
    item.update(overrides)
    return item


def _complete_evaluation(**overrides):
    evaluation = {
        "decision": "REVIEW_NUMBERS",
        "expected_profit_nok": 12_000,
        "roi_percent": 60,
        "total_cost_nok": 20_000,
        "conservative_resale_value_nok": 32_000,
        "maximum_safe_bid_nok": None,
        "missing_evidence": [],
        "evidence": {"market_comparables_nok": [32_000, 34_000, 36_000]},
    }
    evaluation.update(overrides)
    return evaluation


def test_buy_review_requires_complete_verified_economics() -> None:
    result = score_opportunity(_item(), _complete_evaluation())

    assert result["recommendation"] == "BUY_REVIEW"
    assert result["requires_human_approval"] is True
    assert result["opportunity_score"] >= 75


def test_missing_evidence_hard_caps_score_and_blocks_buy() -> None:
    result = score_opportunity(
        _item(),
        {
            "decision": "EVIDENCE_REQUIRED",
            "expected_profit_nok": None,
            "roi_percent": None,
            "missing_evidence": ["transport_cost_nok"],
            "evidence": {"market_comparables_nok": []},
        },
    )

    assert result["opportunity_score"] <= 59
    assert result["recommendation"] != "BUY_REVIEW"
    assert result["requires_human_approval"] is False


def test_negative_verified_profit_is_rejected() -> None:
    result = score_opportunity(
        _item(),
        _complete_evaluation(expected_profit_nok=-1_000, roi_percent=-5),
    )

    assert result["opportunity_score"] <= 29
    assert result["recommendation"] == "REJECT"


def test_p2_stages_replace_legacy_top5_with_scoring_sequence() -> None:
    names = [name for name, _ in build_p2_stages()]

    scoring_index = names.index("unified_scoring")
    assert names[scoring_index : scoring_index + 3] == [
        "unified_scoring",
        "top5_report",
        "scoring_alerts",
    ]
    assert names.count("top5_report") == 1


def test_daily_report_is_enriched_with_scoring(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "daily_report.json").write_text(
        json.dumps({"schema_version": 1, "status": "SUCCESS"}), encoding="utf-8"
    )
    scoring = {"candidate_count": 2, "opportunities": []}
    (data / "scored_opportunities.json").write_text(json.dumps(scoring), encoding="utf-8")

    enrich_daily_report(tmp_path)

    report = json.loads((data / "daily_report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == 2
    assert report["scoring"] == scoring
    assert report["scoring_history_path"] == "data/scoring_history.json"
