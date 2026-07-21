import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_top5_opportunity_report.py"
spec = importlib.util.spec_from_file_location("top5_report", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_score_never_invents_economics():
    score, reasons = module._score({
        "relevance_score": 25,
        "priority": 1,
        "asking_price_nok": 1000,
        "city": "Namsos",
        "ends_at": "2026-07-22T12:00:00+00:00",
        "missing_evidence": ["three_verified_market_comparables"],
        "expected_profit_nok": None,
        "roi_percent": None,
    })

    assert 0 <= score <= 100
    assert "verified_economics:0/15" in reasons


def test_verified_positive_economics_improve_score():
    base = {
        "relevance_score": 20,
        "priority": 1,
        "asking_price_nok": 1000,
        "city": "Namsos",
        "ends_at": None,
        "missing_evidence": [],
    }
    without, _ = module._score({**base, "expected_profit_nok": None, "roi_percent": None})
    with_verified, reasons = module._score({**base, "expected_profit_nok": 500, "roi_percent": 35})

    assert with_verified > without
    assert "verified_economics:15/15" in reasons


def test_merge_preserves_missing_values_and_sets_evidence_action():
    merged = module._merge(
        {"opportunity_id": "x", "title": "Lagerreol", "priority": 1, "relevance_score": 24},
        {"decision": "EVIDENCE_REQUIRED", "expected_profit_nok": None, "roi_percent": None, "missing_evidence": ["auction_fee_nok"]},
    )

    assert merged["expected_profit_nok"] is None
    assert merged["recommendation"] == "COLLECT_EVIDENCE"
