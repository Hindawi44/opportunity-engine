from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_opportunity_review_queue.py"
SPEC = importlib.util.spec_from_file_location("build_opportunity_review_queue", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
classify = MODULE.classify
fallback_items = MODULE._fallback_items


def test_used_car_url_is_excluded_even_without_vehicle_word_in_title() -> None:
    item = classify(
        {
            "opportunity_id": "car-1",
            "title": "2021 Audi e-tron 55 Sportback quattro",
            "url": "https://www.auksjonen.no/auksjon/bruktbil/2021_Audi_e_tron/607137",
            "asking_price_nok": 133000,
            "city": "Oslo",
        }
    )

    assert item["status"] == "excluded"
    assert "vehicle" in item["exclusion_reasons"]


def test_target_reol_listing_remains_reviewable() -> None:
    item = classify(
        {
            "opportunity_id": "reol-1",
            "title": "4 stk komplette lagerreoler",
            "url": "https://www.auksjonen.no/auksjon/torget/lagerreoler/613336",
            "asking_price_nok": 4600,
            "city": "Tønsberg",
        }
    )

    assert item["status"] in {"review_first", "review_if_capacity"}
    assert item["exclusion_reasons"] == []


def test_unrelated_low_relevance_items_never_enter_fallback() -> None:
    unrelated = [
        classify({"title": "Original litografi av Espolin Johnson", "asking_price_nok": 100}),
        classify({"title": "2023 LMC Tandero 500K campingvogn", "asking_price_nok": 31000}),
        classify({"title": "Kebony Radiata terrassebord", "asking_price_nok": 31000}),
    ]

    assert all(item["status"] == "low_relevance" for item in unrelated)
    assert fallback_items(unrelated, 3) == []


def test_weak_explicit_target_may_enter_labelled_fallback() -> None:
    target = classify(
        {
            "title": "Lite skap",
            "asking_price_nok": None,
            "city": None,
            "ends_at": None,
        }
    )

    assert target["status"] == "low_relevance"
    selected = fallback_items([target], 3)
    assert len(selected) == 1
    assert selected[0]["status"] == "discovery_fallback"
    assert selected[0]["matched_target_terms"] == ["skap"]
