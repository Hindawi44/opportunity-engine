from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.openai_fabric_procurement_advisor import (
    attach_advisory_to_fabric_report,
    run_openai_fabric_procurement_advisor,
    select_procurement_candidates,
)
from opportunity_engine.discovery.openai_fabric_procurement_cli_hook import (
    write_daily_openai_fabric_advisor,
)


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"


def _candidate(
    candidate_id: str,
    source_id: str,
    source_name: str,
    location: str,
    score: int,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_id": source_id,
        "source_name": source_name,
        "source_country": "IT",
        "source_kind": "COMO_SILK_STOCK" if "como" in candidate_id else "BIELLA_WOOL_STOCK",
        "location": location,
        "title": f"Stock silk wool fabric {candidate_id}",
        "description": "Stock fabric ready for supplier review.",
        "source_url": f"https://example.com/{candidate_id}",
        "fabric_terms": ["silk", "lana"],
        "bridal_terms": [],
        "value_terms": ["stock"],
        "price": None,
        "currency": None,
        "quantity": None,
        "quantity_unit": None,
        "procurement_relevance_score": score,
        "verification_status": "UNVERIFIED_SEARCH_RESULT",
    }


def _report() -> dict[str, Any]:
    return {
        "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
        "candidate_count": 4,
        "candidates": [
            _candidate("como-a", "silk-lab-como", "Silk Lab Italy", "Como, IT", 75),
            _candidate("como-b", "silk-lab-como", "Silk Lab Italy", "Como, IT", 70),
            _candidate("biella-a", "texit-biella", "Texit", "Biella, IT", 65),
            _candidate("prato-a", "verian-prato", "Verian", "Prato, IT", 85),
        ],
        "automatic_purchase": False,
    }


def test_selection_keeps_one_best_candidate_per_supplier() -> None:
    selected = select_procurement_candidates(_report(), max_candidates=7)
    assert [item["candidate_id"] for item in selected] == [
        "prato-a",
        "como-a",
        "biella-a",
    ]


class FakeStructuredClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_structured_response(self, **kwargs):
        self.calls.append(kwargs)
        supplied = json.loads(kwargs["input_text"])["fabric_procurement_candidates"]
        return (
            {
                "assessments": [
                    {
                        "candidate_id": item["candidate_id"],
                        "review_priority": "HIGH" if item["candidate_id"] == "prato-a" else "MEDIUM",
                        "material_summary": f"Review {item['title']}",
                        "source_facts": ["Supplier result states stock fabric."],
                        "missing_information": ["exact composition", "shipping to Norway"],
                        "operator_questions": ["What is the exact composition?"],
                        "norway_import_checks": ["Confirm delivered cost to Norway."],
                        "reason": "Useful supplier evidence but commercial terms remain incomplete.",
                        "confidence": 0.7,
                    }
                    for item in supplied
                ],
                "overall_note": "Compare source evidence before any supplier contact or order.",
            },
            {"input_tokens": 300, "output_tokens": 200, "total_tokens": 500},
        )


def test_advisor_uses_one_request_and_preserves_manual_only_boundary() -> None:
    client = FakeStructuredClient()
    advisor = run_openai_fabric_procurement_advisor(
        _report(),
        environment={"OPENAI_FABRIC_ADVISOR_MAX_CANDIDATES": "7"},
        client=client,
    )

    assert advisor["status"] == "SUCCESS"
    assert advisor["api_request_count"] == 1
    assert advisor["selected_candidate_count"] == 3
    assert advisor["assessment_count"] == 3
    assert len(client.calls) == 1
    assert advisor["promotion_to_opportunity_allowed"] is False
    assert advisor["automatic_contact"] is False
    assert advisor["automatic_purchase"] is False
    assert advisor["automatic_payment"] is False

    enriched = attach_advisory_to_fabric_report(_report(), advisor)
    prato = next(item for item in enriched["candidates"] if item["candidate_id"] == "prato-a")
    metadata = prato["metadata"]["openai_procurement_advisory"]
    assert metadata["review_priority"] == "HIGH"
    assert "shipping to Norway" in metadata["missing_information"]


def test_missing_api_key_skips_without_changing_safety() -> None:
    advisor = run_openai_fabric_procurement_advisor(_report(), environment={})
    assert advisor["status"] == "SKIPPED_NO_API_KEY"
    assert advisor["api_request_count"] == 0
    assert advisor["automatic_purchase"] is False


def test_daily_hook_attaches_ai_section_and_metadata(tmp_path: Path) -> None:
    fabric = _report()
    (tmp_path / "fabric-procurement-watch.json").write_text(
        json.dumps(fabric), encoding="utf-8"
    )
    (tmp_path / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"market_coverage": ["NO", "SE", "DE"]}), encoding="utf-8"
    )
    (tmp_path / "domain-market-intelligence-brief.txt").write_text(
        "BASE BULLETIN\n", encoding="utf-8"
    )

    def fake_runner(report: Mapping[str, Any], *, environment: Mapping[str, str]):
        assert report["feed_family"] == "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1"
        assert environment == {"OPENAI_API_KEY": "secret"}
        return {
            "schema_version": "openai-fabric-procurement-advisor-1.0",
            "status": "SUCCESS",
            "model": "fake-model",
            "selected_candidate_count": 1,
            "api_request_count": 1,
            "assessment_count": 1,
            "assessments": [
                {
                    "candidate_id": "como-a",
                    "review_priority": "HIGH",
                    "material_summary": "Silk stock worth operator review.",
                    "source_facts": ["stock"],
                    "missing_information": ["price", "MOQ"],
                    "operator_questions": ["What is the MOQ?"],
                    "norway_import_checks": ["Confirm shipping to Norway."],
                    "reason": "Commercial terms are incomplete.",
                    "confidence": 0.8,
                }
            ],
            "overall_note": "Manual verification required.",
            "usage": {},
            "model_output_is_advisory": True,
            "source_evidence_required_for_verification": True,
            "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    advisor = write_daily_openai_fabric_advisor(
        tmp_path,
        environment={"OPENAI_API_KEY": "secret"},
        runner=fake_runner,
    )
    assert advisor is not None
    assert advisor["status"] == "SUCCESS"

    updated_fabric = json.loads(
        (tmp_path / "fabric-procurement-watch.json").read_text(encoding="utf-8")
    )
    como = next(item for item in updated_fabric["candidates"] if item["candidate_id"] == "como-a")
    assert como["metadata"]["openai_procurement_advisory"]["review_priority"] == "HIGH"

    brief = json.loads(
        (tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    assert brief["market_coverage"] == ["NO", "SE", "DE"]
    assert brief["fabric_ai_advisor"]["api_request_count"] == 1
    assert brief["fabric_ai_advisor"]["decision_owner"] == "HUMAN_OPERATOR"
    assert brief["fabric_ai_advisor"]["automatic_purchase"] is False
    assert (tmp_path / "openai-fabric-procurement-advisor.json").exists()
    rendered = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert "OPENAI FABRIC PROCUREMENT ADVISOR" in rendered
    assert "automatic_purchase: false" in rendered


def test_hook_registration_runs_fabric_then_ai_then_unified_river_at_exit() -> None:
    text = INIT_FILE.read_text(encoding="utf-8")
    river = text.index("install_unified_market_intelligence_river_cli_hook()")
    ai = text.index("install_openai_fabric_procurement_cli_hook()")
    fabric = text.index("install_fabric_procurement_watch_cli_hook()")
    assert river < ai < fabric
