from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    render_daily_central_report,
)
from opportunity_engine.discovery.central_market_decision_quality import (
    apply_market_benchmark_to_brief,
    apply_market_decision_quality,
)


def _card(case_id: str, title: str, case_type: str = "DIRECT_OPPORTUNITY") -> dict:
    return {
        "case_id": case_id,
        "headline": title,
        "case_type": case_type,
        "case_status": "ACTIVE_REQUIRES_VERIFICATION",
        "decision_lane": "ACTIONABLE_NOW",
        "actionability_tier": 2,
        "actionability_score": 94.0,
        "source_strength": 80.0,
        "recommended_next_action": "REVIEW_CURRENT_OPPORTUNITY_AND_MISSING_EVIDENCE",
        "missing_information": ["SHIPPING"],
        "risk_flags": [],
        "source_urls": [f"https://example.test/{case_id}"],
    }


def _brief(top: dict) -> dict:
    return {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE", "IT"],
        "today_snapshot": {
            "actionable_now_count": 2,
            "market_watch_count": 0,
            "fabric_candidate_count": 0,
            "fabric_ai_status": "NOT_AVAILABLE",
        },
        "top_actionable_opportunity": {
            "case_id": top["case_id"],
            "headline": top["headline"],
            "case_type": top["case_type"],
            "source_urls": top["source_urls"],
            "recommended_next_action": top["recommended_next_action"],
        },
        "top_market_signal": None,
        "top_fabric_supplier": None,
        "primary_human_action": {
            "action_type": "REVIEW_TOP_ACTIONABLE_OPPORTUNITY",
            "target_id": top["case_id"],
            "target": top["headline"],
        },
        "decision_owner": "HUMAN_OPERATOR",
        "automatic_purchase": False,
        "output_files": ["central-intelligence-brief.json", "central-intelligence-brief.txt"],
    }


def _benchmark(case_id: str, classification: str, *, count: int = 5) -> dict:
    return {
        "case_id": case_id,
        "intelligence_id": f"item:{case_id}",
        "title": case_id,
        "source_url": f"https://example.test/{case_id}",
        "comparable_count": count,
        "benchmark_classification": classification,
        "confidence": "MEDIUM",
        "target_price": {"amount": 100, "currency": "EUR", "basis": "PER_ITEM"},
        "wholesale_range": {"count": count, "currency": "EUR", "basis": "PER_ITEM", "median": 150},
        "retail_range": None,
        "reference_lane": "WHOLESALE",
        "target_to_reference_median_ratio": 0.67,
        "recommended_next_action": "CHECK_SHIPPING_FEES_CONDITION_AND_FINAL_PRICE",
    }


def test_below_market_candidate_outranks_first_above_market_candidate() -> None:
    first = _card("case:first", "First but expensive")
    second = _card("case:second", "Second and below market", "B2B_INVENTORY")
    unified = {"actionable_now": [first, second]}
    comparables = {
        "status": "SUCCESS",
        "target_benchmarks": [
            _benchmark("case:first", "ABOVE_MARKET"),
            _benchmark("case:second", "BELOW_MARKET_REQUIRES_VERIFICATION"),
        ],
    }

    result = apply_market_benchmark_to_brief(_brief(first), unified, comparables)

    selected = result["top_actionable_opportunity"]
    action = result["primary_human_action"]
    assert selected["case_id"] == "case:second"
    assert selected["market_benchmark"]["benchmark_classification"] == "BELOW_MARKET_REQUIRES_VERIFICATION"
    assert selected["selection_basis"] == "MARKET_COMPARABLES_THEN_EXISTING_ACTIONABILITY_ORDER"
    assert action["action_type"] == "VERIFY_LANDED_COST_FOR_BELOW_MARKET_OPPORTUNITY"
    assert action["target_id"] == "case:second"
    assert result["today_snapshot"]["market_decision_quality"] == "BENCHMARK_APPLIED"


def test_existing_actionability_order_is_preserved_without_benchmark_evidence() -> None:
    first = _card("case:first", "First by existing priority")
    second = _card("case:second", "Second by existing priority", "B2B_INVENTORY")
    unified = {"actionable_now": [first, second]}

    result = apply_market_benchmark_to_brief(_brief(first), unified, {"status": "VALID_ZERO", "target_benchmarks": []})

    selected = result["top_actionable_opportunity"]
    assert selected["case_id"] == "case:first"
    assert selected["market_benchmark"] is None
    assert selected["selection_basis"] == "EXISTING_ACTIONABILITY_ORDER"
    assert result["primary_human_action"]["action_type"] == "REVIEW_TOP_ACTIONABLE_OPPORTUNITY"
    assert result["today_snapshot"]["market_decision_quality"] == "UNIFIED_PRIORITY_ONLY"


def test_above_market_single_candidate_is_deprioritized_not_presented_as_buy_signal() -> None:
    first = _card("case:first", "Expensive current offer")
    unified = {"actionable_now": [first]}
    comparables = {"status": "SUCCESS", "target_benchmarks": [_benchmark("case:first", "ABOVE_MARKET")]}

    result = apply_market_benchmark_to_brief(_brief(first), unified, comparables)

    action = result["primary_human_action"]
    assert action["action_type"] == "DEPRIORITIZE_OR_NEGOTIATE_ABOVE_MARKET_OPPORTUNITY"
    assert action["recommended_next_action"] == "DO_NOT_ADVANCE_WITHOUT_BETTER_PRICE_OR_STRONGER_EVIDENCE"
    assert result["automatic_purchase"] is False


def test_report_shows_market_classification_next_to_title_and_link() -> None:
    first = _card("case:first", "Below-market Norwegian stock")
    result = apply_market_benchmark_to_brief(
        _brief(first),
        {"actionable_now": [first]},
        {"status": "SUCCESS", "target_benchmarks": [_benchmark("case:first", "CLEARLY_BELOW_MARKET", count=7)]},
    )

    text = render_daily_central_report(result)

    assert "العنوان: Below-market Norwegian stock" in text
    assert "الرابط: https://example.test/case:first" in text
    assert "مقارنة السوق: CLEARLY_BELOW_MARKET | comparables=7" in text
    assert "market_decision_quality: BENCHMARK_APPLIED" in text


def test_file_application_updates_central_and_existing_domain_attachment(tmp_path: Path) -> None:
    first = _card("case:first", "First but expensive")
    second = _card("case:second", "Second and better", "AUCTION_INVENTORY")
    brief = _brief(first)

    (tmp_path / "unified-daily-decision-brief.json").write_text(
        json.dumps({"actionable_now": [first, second]}), encoding="utf-8"
    )
    (tmp_path / "market-comparables-benchmark.json").write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "target_benchmarks": [
                    _benchmark("case:first", "ABOVE_MARKET"),
                    _benchmark("case:second", "NEAR_MARKET"),
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"central_intelligence_orchestrator": {"status": "SUCCESS"}}),
        encoding="utf-8",
    )

    result = apply_market_decision_quality(tmp_path, brief)

    assert result["top_actionable_opportunity"]["case_id"] == "case:second"
    persisted = json.loads((tmp_path / "central-intelligence-brief.json").read_text(encoding="utf-8"))
    assert persisted["primary_human_action"]["action_type"] == "REVIEW_MARGIN_FOR_NEAR_MARKET_OPPORTUNITY"
    domain = json.loads((tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8"))
    attached = domain["central_intelligence_orchestrator"]
    assert attached["top_actionable_opportunity"]["case_id"] == "case:second"
    assert attached["today_snapshot"]["market_decision_quality"] == "BENCHMARK_APPLIED"
