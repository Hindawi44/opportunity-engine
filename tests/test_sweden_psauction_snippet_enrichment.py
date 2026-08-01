from opportunity_engine.discovery.sweden_psauction_snippet_enrichment import (
    enrich_psauction_discovery_result,
    extract_psauction_snippet_facts,
)


def _candidate(url: str, *, queries: list[str] | None = None) -> dict:
    return {
        "title": "Candidate",
        "scenario": "COMPANY_BANKRUPTCY",
        "source_urls": [url],
        "found_by_queries": queries or ["se-ps-08"],
        "duplicate_count": 0,
        "inventory_type": None,
        "quantity": None,
        "price_nok": None,
        "listing_status": "UNKNOWN",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "top5_eligible": False,
        "analysis_eligible": False,
        "evidence_signals": [
            "konkursbo",
            "konkurs",
            "klær",
            "auksjon",
            "nettauksjon",
        ],
        "why_opportunity": [
            "commercial event detected: COMPANY_BANKRUPTCY",
            "specific clothing-inventory evidence detected",
        ],
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


def test_extracts_mixed_pallet_inventory_before_workwear_subtype() -> None:
    facts = extract_psauction_snippet_facts(
        "Stort parti med kläder och skor, ca 10 pall med kartonger. "
        "Jeans, arbetsskor, tröjor och pikéer."
    )

    assert facts.inventory_type == "mixed_clothing_and_footwear"
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
        "all_discovered_candidates": [_candidate(url, queries=["se-ps-05"])],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Parti med damkläder från Masai (ca 1300 stycken plagg) - Auktioner online",
            "description": (
                "Uppskattningsvis 1300 plagg med ett uppskattat "
                "butikspris på 790 000:-. OBS! Detta är en tvångsförsäljning "
                "då objektet tillhör ett konkursbo."
            ),
        }
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["scenario"] == "COMPANY_BANKRUPTCY"
    assert candidate["inventory_type"] == "womens_clothing"
    assert candidate["quantity"] == 1300
    assert candidate["quantity_unit"] == "garments"
    assert candidate["reference_value_sek"] == 790000
    assert candidate["reference_value_is_current_sale_price"] is False
    assert candidate["price_nok"] is None
    assert "quantity" not in candidate["missing_information"]
    assert "price" in candidate["missing_information"]
    assert candidate["score_breakdown"]["commercial_event_strength"] == 25
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
            _candidate(url, queries=["se-ps-05", "se-ps-06", "se-ps-08"])
        ],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Kläder, jeans, tröjor, piké, skor, mm, ca 10 pall - Auktioner online",
            "description": (
                "Stort parti med kläder och skor, ca 10 pall. Jeans, "
                "arbetsskor, tröjor och pikéer."
                + (
                    " OBS! Detta är en tvångsförsäljning då objektet tillhör ett konkursbo."
                    if query_id == "se-ps-06"
                    else ""
                )
            ),
            "query_id": query_id,
        }
        for query_id in ("se-ps-05", "se-ps-06", "se-ps-08")
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["scenario"] == "COMPANY_BANKRUPTCY"
    assert candidate["inventory_type"] == "mixed_clothing_and_footwear"
    assert candidate["duplicate_count"] == 2
    assert candidate["quantity"] == 10
    assert candidate["quantity_unit"] == "pallets"
    diagnostics = enriched["search_run_report"]["source_snippet_enrichment"]
    assert diagnostics["accepted_samples_used"] == 3
    assert diagnostics["candidates_enriched"] == 1
    assert diagnostics["quantities_extracted"] == 1
    assert diagnostics["duplicate_counts_corrected"] == 1
    assert diagnostics["inventory_types_corrected"] == 1
    assert diagnostics["source_boilerplate_used_for_event_classification"] is False


def test_sport_store_remainder_is_not_bankruptcy_from_site_boilerplate() -> None:
    url = "https://psauction.se/item/view/826330/restparti-med-klader-fran-sportbutik"
    result = {
        "all_discovered_candidates": [_candidate(url)],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Restparti med kläder från sportbutik - Auktioner online - Nätauktioner & Konkursauktioner | PS Auction",
            "description": (
                "Restparti med kläder från sportbutik. Träningskläder, shorts, "
                "T-shirt och ytterkläder. | Auktionsexperter med fokus på "
                "konkurser, avyttringar, avvecklingar och överskott. "
                "Nätauktioner varje dag."
            ),
        }
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["scenario"] == "WAREHOUSE_SURPLUS"
    assert candidate["score_breakdown"]["commercial_event_strength"] == 18
    assert candidate["discovery_score"] == 61
    assert "konkurs" not in candidate["evidence_signals"]
    assert "konkursbo" not in candidate["evidence_signals"]
    assert "auksjon" not in candidate["evidence_signals"]
    assert "nettauksjon" not in candidate["evidence_signals"]
    assert "restlager" in candidate["evidence_signals"]
    assert candidate["why_opportunity"][0] == (
        "source-scoped commercial event detected: WAREHOUSE_SURPLUS"
    )


def test_secondhand_cartons_are_large_lot_not_bankruptcy_from_site_name() -> None:
    url = "https://psauction.se/item/view/824258/approx-sek-35-second-hand-clothes-washed-and-sorted"
    result = {
        "all_discovered_candidates": [_candidate(url)],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Ca 35 krt secondhand kläder tvättat och sorterat - Auktioner online - Nätauktioner & Konkursauktioner | PS Auction",
            "description": (
                "Ca 35 krt secondhand kläder, mest damkläder tvättat och "
                "sorterat ca 15-20 plagg /kartong. | Auktionsexperter med "
                "fokus på konkurser. Nätauktioner varje dag."
            ),
        }
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["scenario"] == "LARGE_LOT_SALE"
    assert candidate["score_breakdown"]["commercial_event_strength"] == 16
    assert candidate["discovery_score"] == 64
    assert candidate["quantity"] == 35
    assert candidate["estimated_piece_count_min"] == 525
    assert candidate["estimated_piece_count_max"] == 700
    assert "konkurs" not in candidate["evidence_signals"]
    assert "konkursbo" not in candidate["evidence_signals"]
    assert "vareparti" in candidate["evidence_signals"]


def test_explicit_bankruptcy_phrase_survives_boilerplate_cleanup() -> None:
    url = "https://psauction.se/item/view/756168/parti-med-mc-klader"
    result = {
        "all_discovered_candidates": [_candidate(url, queries=["se-ps-05"])],
        "discovery_top5": [],
        "search_run_report": {},
    }
    samples = [
        {
            "canonical_url": url,
            "title": "Parti med MC kläder - Auktioner online",
            "description": (
                "Parti med diverse MC kläder. Detta är en tvångsförsäljning "
                "då objektet tillhör ett konkursbo. Totalt ca 100 artiklar. | "
                "Auktionsexperter med fokus på konkurser."
            ),
        }
    ]

    enriched = enrich_psauction_discovery_result(result, samples)
    candidate = enriched["all_discovered_candidates"][0]

    assert candidate["scenario"] == "COMPANY_BANKRUPTCY"
    assert "konkursbo" in candidate["evidence_signals"]
    assert "konkurs" in candidate["evidence_signals"]
    assert "auksjon" not in candidate["evidence_signals"]
