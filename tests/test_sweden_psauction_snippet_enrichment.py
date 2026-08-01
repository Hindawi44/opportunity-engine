from opportunity_engine.discovery.sweden_psauction_snippet_enrichment import (
    enrich_psauction_discovery_result,
    extract_psauction_snippet_facts,
)


def test_extracts_mc_clothing_minimum_article_count() -> None:
    facts = extract_psauction_snippet_facts(
        "Parti med diverse MC kläder och skoteroverall. "
        "Totalt uppskattat till ca 100 + artiklar i objektet."
    )

    assert facts.inventory_type == "motorcycle_and_snowmobile_clothing"
    assert facts.quantity == 100
    assert facts.quantity_unit == "articles"
    assert facts.quantity_qualifier == "minimum"


def test_extracts_masai_garments_and_retail_reference_value() -> None:
    facts = extract_psauction_snippet_facts(
        "Parti med damkläder från Masai. Enligt en schablonberäkning så bör "
        "objektet innehålla uppskattningsvis 1300 plagg med ett uppskattat "
        "butikspris på 790 000:-"
    )

    assert facts.inventory_type == "womens_clothing"
    assert facts.quantity == 1300
    assert facts.quantity_unit == "garments"
    assert facts.quantity_qualifier == "approximate"
    assert facts.reference_value_sek == 790000
    assert facts.reference_value_kind == "estimated_retail_value"


def test_extracts_pallet_quantity_without_treating_it_as_piece_count() -> None:
    facts = extract_psauction_snippet_facts(
        "Stort parti med kläder och skor, ca 10 pall med kartonger. "
        "Jeans, arbetsskor, tröjor och pikéer."
    )

    assert facts.inventory_type == "workwear_and_work_shoes"
    assert facts.quantity == 10
    assert facts.quantity_unit == "pallets"
    assert facts.estimated_piece_count_min is None


def test_extracts_hundreds_and_original_purchase_value() -> None:
    facts = extract_psauction_snippet_facts(
        "Större sortiment av träningskläder och träningsutrustning. "
        "100tals artiklar. Inköpsvärde 249000kr."
    )

    assert facts.inventory_type == "training_clothing_and_accessories"
    assert facts.quantity == 100
    assert facts.quantity_unit == "articles"
    assert facts.quantity_qualifier == "minimum"
    assert facts.reference_value_sek == 249000
    assert facts.reference_value_kind == "original_purchase_value"


def test_extracts_cartons_and_estimated_garment_range() -> None:
    facts = extract_psauction_snippet_facts(
        "Ca 35 krt secondhand kläder, mest damkläder tvättat och sorterat "
        "ca 15-20 plagg /kartong."
    )

    assert facts.inventory_type == "sorted_second_hand_womens_clothing"
    assert facts.quantity == 35
    assert facts.quantity_unit == "cartons"
    assert facts.estimated_piece_count_min == 525
    assert facts.estimated_piece_count_max == 700


def test_enrichment_preserves_unknown_status_and_top5_hard_gate() -> None:
    url = "https://psauction.se/item/view/670524/lot-of-womens-clothing-from-masai-about-1300-pieces-of-clothing"
    result = {
        "all_discovered_candidates": [
            {
                "title": "Parti med damkläder från Masai",
                "source_urls": [url],
                "found_by_queries": ["se-ps-05"],
                "duplicate_count": 0,
                "inventory_type": None,
                "quantity": None,
                "price_nok": None,
                "listing_status": "UNKNOWN",
                "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
                "top5_eligible": False,
                "analysis_eligible": False,
                "missing_information": [
                    "location",
                    "price",
                    "quantity",
                    "active/ended status",
                ],
                "confirmed_information": ["traceable public sources: 1"],
                "score_breakdown": {
                    "commercial_event_strength": 25,
                    "clothing_inventory_clarity": 12,
                    "sale_signal": 8,
                    "source_traceability": 15,
                    "freshness": 0,
                    "location_logistics": 0,
                    "price_or_quantity": 0,
                },
                "discovery_score": 60,
            }
        ],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Parti med damkläder från Masai (ca 1300 stycken plagg)",
            "description": (
                "Uppskattningsvis 1300 plagg med ett uppskattat "
                "butikspris på 790 000:-"
            ),
        }
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["inventory_type"] == "womens_clothing"
    assert candidate["quantity"] == 1300
    assert candidate["quantity_unit"] == "garments"
    assert candidate["reference_value_sek"] == 790000
    assert candidate["reference_value_is_current_sale_price"] is False
    assert candidate["price_nok"] is None
    assert "quantity" not in candidate["missing_information"]
    assert "price" in candidate["missing_information"]
    assert candidate["score_breakdown"]["clothing_inventory_clarity"] == 20
    assert candidate["score_breakdown"]["price_or_quantity"] == 5
    assert candidate["discovery_score"] == 73
    assert candidate["listing_status"] == "UNKNOWN"
    assert candidate["top5_eligible"] is False
    assert candidate["analysis_eligible"] is False
    assert enriched["discovery_top5"] == []


def test_enrichment_corrects_cross_query_duplicate_count() -> None:
    url = "https://psauction.se/item/view/497916/klader-jeans-trojor-pike-skor-mm-ca-10-pall"
    result = {
        "all_discovered_candidates": [
            {
                "source_urls": [url],
                "found_by_queries": ["se-ps-05", "se-ps-06", "se-ps-08"],
                "duplicate_count": 0,
                "missing_information": ["quantity"],
                "confirmed_information": [],
                "score_breakdown": {
                    "commercial_event_strength": 25,
                    "clothing_inventory_clarity": 12,
                    "sale_signal": 8,
                    "source_traceability": 15,
                    "freshness": 0,
                    "location_logistics": 0,
                    "price_or_quantity": 0,
                },
            }
        ],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Kläder, jeans, tröjor, piké, skor, mm, ca 10 pall",
            "description": "Stort parti med kläder och skor, ca 10 pall.",
            "query_id": query_id,
        }
        for query_id in ("se-ps-05", "se-ps-06", "se-ps-08")
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["duplicate_count"] == 2
    assert candidate["quantity"] == 10
    assert candidate["quantity_unit"] == "pallets"
    assert enriched["search_run_report"]["source_snippet_enrichment"] == {
        "source": "PS_AUCTION",
        "accepted_samples_used": 3,
        "candidates_enriched": 1,
        "quantities_extracted": 1,
        "reference_values_extracted": 0,
        "duplicate_counts_corrected": 1,
        "listing_status_changed": False,
        "top5_eligibility_changed": False,
        "reference_values_used_as_sale_prices": False,
    }
