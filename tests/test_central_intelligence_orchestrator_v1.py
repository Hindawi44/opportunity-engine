from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.central_intelligence_orchestrator import (
    JSON_FILENAME,
    SCHEMA_VERSION,
    TEXT_FILENAME,
    build_central_intelligence_brief,
    write_central_intelligence_orchestrator,
)

ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"


def _domain() -> dict:
    return {
        "generated_at": "2026-08-12T20:00:00+00:00",
        "market_coverage": ["NO", "SE", "DE"],
        "daily_market_visibility": {
            "countries": ["NO", "SE", "DE", "IT"],
            "primary_opportunity_markets": ["NO", "SE", "DE"],
            "advisory_markets": ["IT"],
        },
    }


def _unified() -> dict:
    direct = {
        "case_id": "case:direct",
        "headline": "Current Norwegian clothing stock",
        "case_type": "DIRECT_OPPORTUNITY",
        "case_status": "ACTIVE_REQUIRES_VERIFICATION",
        "decision_lane": "ACTIONABLE_NOW",
        "actionability_tier": 2,
        "actionability_score": 95.0,
        "source_strength": 72.0,
        "recommended_next_action": "REVIEW_CURRENT_OPPORTUNITY_AND_MISSING_EVIDENCE",
        "missing_information": ["PRICE"],
        "risk_flags": ["PRICE_NOT_CONFIRMED"],
        "source_urls": ["https://example.test/opportunity"],
    }
    fabric_card = {
        "case_id": "case:fabric",
        "headline": "Fabric House — fabric procurement",
        "case_type": "FABRIC_PROCUREMENT",
        "case_status": "WATCH",
        "decision_lane": "ACTIONABLE_NOW",
        "actionability_tier": 7,
        "actionability_score": 70.0,
        "source_strength": 90.0,
        "recommended_next_action": "REVIEW_SAMPLE_PRICE_MOQ_AND_SHIPPING",
        "missing_information": ["PRICE", "MINIMUM_ORDER"],
        "risk_flags": ["PRICE_NOT_CONFIRMED"],
        "source_urls": ["https://fabric.example"],
    }
    watch = {
        "case_id": "case:watch",
        "headline": "German retailer liquidation signal",
        "case_type": "COMPANY_LIQUIDATION",
        "case_status": "WATCH",
        "decision_lane": "MARKET_WATCH",
        "actionability_tier": 21,
        "actionability_score": 42.0,
        "source_strength": 99.0,
        "recommended_next_action": "MONITOR_INVENTORY_RELEASE_AND_LINK_NEW_OFFERS",
        "missing_information": [],
        "risk_flags": [],
        "source_urls": ["https://register.example/company"],
    }
    return {
        "schema_version": "unified-daily-decision-brief-1.0",
        "generated_at": "2026-08-12T20:00:00+00:00",
        "status": "SUCCESS",
        "truthful_zero_result": False,
        "priority_counts": {
            "ACTIONABLE_NOW": 2,
            "MARKET_WATCH": 1,
            "HISTORICAL_EVIDENCE": 0,
        },
        "actionable_now": [direct, fabric_card],
        "market_watch": [watch],
        "historical_evidence": [],
        "top_actionable_card": direct,
        "top_market_watch_card": watch,
        "top_decision_card": direct,
    }


def _fabric() -> dict:
    return {
        "candidate_count": 2,
        "candidates": [
            {
                "candidate_id": "fabric:house",
                "source_name": "Fabric House",
                "source_country": "IT",
                "location": "Prato, IT",
                "title": "Italian deadstock fabrics",
                "source_url": "https://fabric-house.example/item",
                "procurement_relevance_score": 88,
                "price": None,
                "currency": None,
                "quantity": None,
                "quantity_unit": None,
            },
            {
                "candidate_id": "fabric:bridal",
                "source_name": "Bridal Fabrics",
                "source_country": "GB",
                "location": "UK",
                "title": "Bridal lace and tulle",
                "source_url": "https://bridal.example/item",
                "procurement_relevance_score": 95,
                "price": None,
                "currency": None,
                "quantity": None,
                "quantity_unit": None,
            },
        ],
    }


def _advisor() -> dict:
    return {
        "status": "SUCCESS",
        "assessments": [
            {
                "candidate_id": "fabric:house",
                "review_priority": "HIGH",
                "material_summary": "Italian deadstock supplier.",
                "missing_information": ["price", "MOQ", "composition", "shipping"],
                "operator_questions": ["What is the exact MOQ?"],
                "norway_import_checks": ["Verify shipping to Norway."],
                "reason": "Strong supplier fit from supplied evidence.",
            },
            {
                "candidate_id": "fabric:bridal",
                "review_priority": "MEDIUM",
                "material_summary": "Bridal fabric specialist.",
                "missing_information": ["price"],
                "operator_questions": [],
                "norway_import_checks": [],
                "reason": "Relevant but lower current review priority.",
            },
        ],
    }


def test_central_brief_keeps_opportunity_watch_and_fabric_as_separate_views() -> None:
    brief = build_central_intelligence_brief(
        _domain(),
        _unified(),
        fabric_report=_fabric(),
        fabric_advisor=_advisor(),
        market_comparables={"status": "SUCCESS"},
    )

    assert brief["schema_version"] == SCHEMA_VERSION
    assert brief["market_visibility"] == ["NO", "SE", "DE", "IT"]
    assert brief["top_actionable_opportunity"]["headline"] == "Current Norwegian clothing stock"
    assert brief["top_market_signal"]["headline"] == "German retailer liquidation signal"
    assert brief["top_fabric_supplier"]["source_name"] == "Fabric House"
    assert brief["top_fabric_supplier"]["ai_review_priority"] == "HIGH"
    assert brief["primary_human_action"]["action_type"] == "REVIEW_TOP_ACTIONABLE_OPPORTUNITY"
    assert brief["primary_human_action"]["target_id"] == "case:direct"
    assert brief["single_human_action_enforced"] is True
    assert brief["automatic_purchase"] is False


def test_fabric_becomes_primary_action_only_when_no_commercial_opportunity_exists() -> None:
    unified = _unified()
    unified["actionable_now"] = [
        card for card in unified["actionable_now"] if card["case_type"] == "FABRIC_PROCUREMENT"
    ]
    unified["top_actionable_card"] = unified["actionable_now"][0]
    unified["priority_counts"]["ACTIONABLE_NOW"] = 1

    brief = build_central_intelligence_brief(
        _domain(),
        unified,
        fabric_report=_fabric(),
        fabric_advisor=_advisor(),
    )

    action = brief["primary_human_action"]
    assert brief["top_actionable_opportunity"] is None
    assert action["action_type"] == "VERIFY_TOP_FABRIC_SUPPLIER"
    assert action["target"] == "Fabric House"
    assert "MOQ" in action["verification_focus"]


def test_valid_zero_produces_no_synthetic_opportunity_or_action() -> None:
    brief = build_central_intelligence_brief(
        {"market_coverage": ["NO", "SE", "DE"]},
        {
            "status": "VALID_ZERO",
            "truthful_zero_result": True,
            "priority_counts": {
                "ACTIONABLE_NOW": 0,
                "MARKET_WATCH": 0,
                "HISTORICAL_EVIDENCE": 0,
            },
            "actionable_now": [],
            "market_watch": [],
        },
        fabric_report={"candidate_count": 0, "candidates": []},
    )

    assert brief["status"] == "VALID_ZERO"
    assert brief["top_actionable_opportunity"] is None
    assert brief["top_market_signal"] is None
    assert brief["top_fabric_supplier"] is None
    assert (
        brief["primary_human_action"]["action_type"]
        == "NO_IMMEDIATE_ACTION_CONTINUE_MONITORING"
    )
    assert brief["promotion_to_opportunity_allowed"] is False


def test_writer_creates_central_artifacts_and_attaches_compact_summary(tmp_path: Path) -> None:
    (tmp_path / "domain-market-intelligence-brief.json").write_text(
        json.dumps(_domain()), encoding="utf-8"
    )
    (tmp_path / "domain-market-intelligence-brief.txt").write_text(
        "BASE BULLETIN\n", encoding="utf-8"
    )
    (tmp_path / "unified-daily-decision-brief.json").write_text(
        json.dumps(_unified()), encoding="utf-8"
    )
    (tmp_path / "fabric-procurement-watch.json").write_text(
        json.dumps(_fabric()), encoding="utf-8"
    )
    (tmp_path / "openai-fabric-procurement-advisor.json").write_text(
        json.dumps(_advisor()), encoding="utf-8"
    )
    (tmp_path / "market-comparables-benchmark.json").write_text(
        json.dumps({"status": "SUCCESS"}), encoding="utf-8"
    )

    brief = write_central_intelligence_orchestrator(tmp_path)

    assert (tmp_path / JSON_FILENAME).exists()
    assert (tmp_path / TEXT_FILENAME).exists()
    persisted = json.loads((tmp_path / JSON_FILENAME).read_text(encoding="utf-8"))
    assert persisted["primary_human_action"]["action_type"] == "REVIEW_TOP_ACTIONABLE_OPPORTUNITY"

    domain = json.loads(
        (tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    attached = domain["central_intelligence_orchestrator"]
    assert attached["top_fabric_supplier"]["source_name"] == "Fabric House"
    assert attached["single_human_action_enforced"] is True
    assert attached["automatic_purchase"] is False

    text = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert text.count("CENTRAL INTELLIGENCE ORCHESTRATOR") == 1
    assert "الإجراء البشري الوحيد:" in text
    assert brief["decision_owner"] == "HUMAN_OPERATOR"


def test_central_hook_is_registered_before_benchmark_and_river_hooks() -> None:
    text = INIT_FILE.read_text(encoding="utf-8")
    central = text.index("install_central_intelligence_orchestrator_cli_hook()")
    benchmark = text.index("install_market_comparables_benchmark_cli_hook()")
    river = text.index("install_unified_market_intelligence_river_cli_hook()")
    assert central < benchmark < river
