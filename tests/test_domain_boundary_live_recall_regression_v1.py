from __future__ import annotations

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    OUT_OF_DOMAIN,
    classify_project_domain,
)
from opportunity_engine.unified_learning_spine import build_unified_learning_spine


def test_live_auksjonen_singular_jakke_is_clothing_inventory() -> None:
    assert (
        classify_project_domain(
            text="280 stk GSA jakke oransje (art GSA11030) str 56/60"
        )
        == CLOTHING_INVENTORY
    )


def test_distinctive_german_fashion_compounds_are_clothing_evidence() -> None:
    for text in (
        "Modekette Adenauer & Co insolvent",
        "Deutsche Mode-Kette meldet Insolvenz an",
        "Modemarke aus NRW rutscht in die Insolvenz",
        "Modehändler mit 13 Filialen ist insolvent",
        "Arbeitskleidung aus Insolvenzbestand",
    ):
        assert classify_project_domain(text=text) == CLOTHING_INVENTORY


def test_structured_clothing_nace_codes_are_authoritative_domain_evidence() -> None:
    for code in ("47.710", "46.420", "14.100", "14.210", "14.240"):
        assert classify_project_domain(industry_codes=[code]) == CLOTHING_INVENTORY


def test_unified_spine_retains_live_auksjonen_and_nace_clothing_signal() -> None:
    river = {
        "generated_at": "2026-08-23T20:00:00Z",
        "items": [
            {
                "intelligence_id": "intelligence-item:live-auksjonen-jakke",
                "source_country": "NO",
                "record_kind": "CANONICAL_OPPORTUNITY",
                "title": "280 stk GSA jakke oransje (art GSA11030) str 56/60",
                "source_name": "Auksjonen.no",
                "source_url": "https://ny.auksjonen.no/auksjon/torget/611144",
                "commercial_state": "ACTIVE_OPPORTUNITY",
                "details": {
                    "quantity": 280,
                    "exact_item_page_verified": True,
                },
                "evidence": [],
            },
            {
                "intelligence_id": "intelligence-item:live-nace-clothing",
                "source_country": "NO",
                "record_kind": "BUSINESS_EVENT_SIGNAL",
                "title": "Avvikling: AS RITA KORSETTSALONG",
                "source_name": "Brønnøysundregistrene Enhetsregisteret API",
                "company_name": "AS RITA KORSETTSALONG",
                "details": {
                    "description": "AS RITA KORSETTSALONG — Avvikling",
                    "metadata": {
                        "nace_codes": ["47.710"],
                        "signal_only": True,
                    },
                },
                "evidence": [],
            },
        ],
    }

    report = build_unified_learning_spine(
        unified_intelligence_items=river,
        search_success_memory={},
        missed_opportunity_memory={},
        daily_learning={},
    )

    assert report["evidence_record_count"] == 2
    assert report["market_counts"] == {"NO": 2}
    assert report["out_of_domain_excluded_count"] == 0
    assert {row["source_identity"] for row in report["records"]} == {
        "intelligence-item:live-auksjonen-jakke",
        "intelligence-item:live-nace-clothing",
    }


def test_mixed_general_merchandise_page_still_fails_closed() -> None:
    text = (
        "Restposten aus nahezu allen Branchen: Textilien, Elektronik, IT-Hardware, "
        "Werkzeug, Maschinen, Autoteile, Büromöbel und Gastronomie-Inventar."
    )
    assert classify_project_domain(text=text) == OUT_OF_DOMAIN
