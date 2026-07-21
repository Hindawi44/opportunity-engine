from scripts.build_opportunity_review_queue import classify


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
