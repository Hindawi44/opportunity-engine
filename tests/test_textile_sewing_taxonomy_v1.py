from __future__ import annotations

import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.textile_taxonomy import (
    OpportunityCategory,
    PRIMARY_CATEGORIES,
    SCHEMA_VERSION,
    SECONDARY_CATEGORIES,
    build_textile_taxonomy_audit,
    classify_textile_opportunity,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "textile_taxonomy_v1_cases.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_taxonomy_has_stable_machine_readable_category_values() -> None:
    assert [category.value for category in OpportunityCategory] == [
        "SMALL_CLOTHING_STORE_LIQUIDATION",
        "CLOTHING_CHAIN_OR_BRANCH_CLOSURE",
        "BRAND_INVENTORY_LIQUIDATION",
        "CLOTHING_INVENTORY",
        "SHOES_BAGS_ACCESSORIES_INVENTORY",
        "FABRIC_TEXTILE_STOCK",
        "TAILOR_WORKSHOP_LIQUIDATION",
        "SEWING_ATELIER_LIQUIDATION",
        "SEWING_FACTORY_LIQUIDATION",
        "SEWING_MACHINERY",
        "HABERDASHERY_AND_NOTIONS",
        "CLOTHING_STORE_FIXTURES",
    ]
    assert len(PRIMARY_CATEGORIES) == 11
    assert SECONDARY_CATEGORIES == {
        OpportunityCategory.CLOTHING_STORE_FIXTURES
    }


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_norway_v1_fixtures_are_classified_conservatively(case: dict) -> None:
    decision = classify_textile_opportunity(
        case["title"],
        case.get("description", ""),
    )

    assert decision.schema_version == SCHEMA_VERSION
    assert decision.status == case["expected_status"]
    assert decision.primary_category == case["expected_primary_category"]
    assert decision.primary_tier == case["expected_primary_tier"]


def test_audit_separates_event_sector_inventory_and_rejection_signals() -> None:
    decision = classify_textile_opportunity(
        "Klesbutikk konkurs - hele varelageret klær og lagerreoler selges"
    )

    assert decision.status == "IN_SCOPE"
    assert decision.primary_category == "SMALL_CLOTHING_STORE_LIQUIDATION"
    assert "BANKRUPTCY:konkurs" in decision.event_signals
    assert "klesbutikk" in decision.sector_signals
    assert "hele varelageret" in decision.inventory_signals
    assert "klær" in decision.inventory_signals
    assert "lagerreol" in decision.inventory_signals
    assert any(signal.startswith("GENERIC_STORAGE:") for signal in decision.rejection_signals)
    assert "human review" in decision.reason


def test_generic_inventory_term_never_qualifies_an_unrelated_sector() -> None:
    decision = classify_textile_opportunity(
        "Varelager og auksjon for kjøkken- og møbelproduksjon"
    )

    assert decision.status == "OUT_OF_SCOPE"
    assert decision.primary_category is None
    assert decision.matched_categories == ()
    assert any(
        signal.startswith("KITCHEN_OR_FURNITURE:")
        for signal in decision.rejection_signals
    )
    assert decision.reason == (
        "unrelated-sector signal without qualifying textile evidence"
    )


def test_ordinary_clothing_retail_page_is_not_a_liquidation_opportunity() -> None:
    decision = classify_textile_opportunity(
        "Ny kolleksjon klær og kjoler med rabatt og fri frakt"
    )

    assert decision.status == "OUT_OF_SCOPE"
    assert decision.primary_category is None
    assert decision.reason == "no liquidation event or commercial inventory signal"


def test_fixture_category_requires_explicit_textile_business_context() -> None:
    generic = classify_textile_opportunity("Lagerreoler til salgs")
    clothing = classify_textile_opportunity(
        "Klesstativer og lagerreoler fra klesbutikk til salgs"
    )

    assert generic.status == "OUT_OF_SCOPE"
    assert clothing.status == "IN_SCOPE"
    assert clothing.primary_category == "CLOTHING_STORE_FIXTURES"
    assert clothing.primary_tier == "SECONDARY"


def test_zero_candidates_produce_a_valid_zero_audit() -> None:
    audit = build_textile_taxonomy_audit([])

    assert audit["schema_version"] == SCHEMA_VERSION
    assert audit["candidate_count"] == 0
    assert audit["included_count"] == 0
    assert audit["rejected_count"] == 0
    assert audit["decisions"] == []
    assert set(audit["category_counts"]) == {
        category.value for category in OpportunityCategory
    }
    assert all(count == 0 for count in audit["category_counts"].values())


def test_audit_explains_each_candidate_and_keeps_other_engines_unchanged() -> None:
    audit = build_textile_taxonomy_audit(
        [
            {
                "candidate_id": "fabric-1",
                "title": "Restlager stoffruller og metervare selges",
                "source": "fixture",
                "url": "https://example.test/fabric-1",
            },
            {
                "candidate_id": "workshop-1",
                "title": "Skredderverksted legges ned med industrisymaskiner",
                "source": "fixture",
                "url": "https://example.test/workshop-1",
            },
            {
                "candidate_id": "noise-1",
                "title": "Skoleinventar og garderobeskap på auksjon",
                "source": "fixture",
                "url": "https://example.test/noise-1",
            },
        ]
    )

    assert audit["candidate_count"] == 3
    assert audit["included_count"] == 2
    assert audit["rejected_count"] == 1
    assert audit["category_counts"]["FABRIC_TEXTILE_STOCK"] == 1
    assert audit["category_counts"]["TAILOR_WORKSHOP_LIQUIDATION"] == 1
    assert audit["category_counts"]["SEWING_MACHINERY"] == 1
    assert [row["candidate_id"] for row in audit["decisions"]] == [
        "fabric-1",
        "workshop-1",
        "noise-1",
    ]
    assert audit["scope"] == {
        "changes_lifecycle": False,
        "changes_scoring": False,
        "changes_ranking": False,
        "changes_top5": False,
        "changes_alerts": False,
        "changes_persistence": False,
        "automatic_contact": False,
        "automatic_purchase": False,
    }


def test_empty_public_text_fails_closed_with_a_reason() -> None:
    decision = classify_textile_opportunity("", "")

    assert decision.status == "OUT_OF_SCOPE"
    assert decision.primary_category is None
    assert decision.reason == "missing title and description"
    assert decision.to_dict()["matched_categories"] == []
