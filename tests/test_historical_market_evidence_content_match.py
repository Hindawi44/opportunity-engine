from opportunity_engine.discovery.early_opportunity_gate import (
    ENDED,
    HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW,
    HISTORICAL_MARKET_EVIDENCE,
    ITEM_LISTING,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    apply_early_opportunity_gate,
)


def _report(candidate):
    return {
        "search_run_report": {
            "schema_version": "clothing-inventory-discovery-search-1.2",
            "automatic_contact": False,
            "automatic_purchase_decision": False,
            "financial_ranking_used": False,
        },
        "all_discovered_candidates": [candidate],
        "discovery_top5": [],
    }


def _ended_candidate(bounded_context: str, **overrides):
    candidate = {
        "title": "Blinto - Restparti - Arbetsbyxor Double W.",
        "scenario": "WAREHOUSE_SURPLUS",
        "opportunity_state": STRONG_LEAD_REQUIRES_VERIFICATION,
        "reason": "specific listing is ended and retained as historical evidence only",
        "page_role": ITEM_LISTING,
        "opportunity_identity": "item-url:https://blinto.se/auction/Arbetsbyxor-Double-W",
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "discovery_score": 61,
        "discovery_band": "REVIEW",
        "score_breakdown": {},
        "location": None,
        "company_name": None,
        "inventory_type": "workwear_inventory",
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": 20,
        "published_at": None,
        "listing_status": ENDED,
        "source_urls": ["https://blinto.se/auction/Arbetsbyxor-Double-W"],
        "source_providers": ["Brave Search"],
        "found_by_queries": ["se-bl-06"],
        "duplicate_count": 0,
        "evidence_signals": ["auksjon", "klær", "vareparti"],
        "why_opportunity": [
            "commercial event detected: WAREHOUSE_SURPLUS",
            "specific clothing-inventory evidence detected",
            "verified ended clothing-inventory listing retained as historical market evidence",
        ],
        "confirmed_information": [
            "traceable public sources: 1",
            f"discovery state: {STRONG_LEAD_REQUIRES_VERIFICATION}",
            "page role: ITEM_LISTING",
        ],
        "missing_information": ["price"],
        "next_verification_step": (
            "Verify publicly that this specific listing remains active and offered for sale."
        ),
        "verification": [{
            "url": "https://blinto.se/auction/Arbetsbyxor-Double-W",
            "title": "Blinto - Restparti - Arbetsbyxor Double W.",
            "text": bounded_context,
            "bounded_context": bounded_context,
            "listing_status": ENDED,
            "page_role": ITEM_LISTING,
            "opportunity_identity": (
                "item-url:https://blinto.se/auction/Arbetsbyxor-Double-W"
            ),
            "identity_stable": True,
            "clothing_inventory_evidence": True,
            "sale_evidence": False,
            "verified": True,
            "error": None,
        }],
    }
    candidate.update(overrides)
    return candidate


def test_bounded_bulk_clothing_description_enters_historical_market_evidence():
    candidate = _ended_candidate(
        "Parti med arbetskläder och arbetsbyxor. Totalt 38 par nya byxor "
        "i blandade storlekar. Auktionen är avslutad."
    )

    result = apply_early_opportunity_gate(_report(candidate))
    historical = result["all_discovered_candidates"][0]

    assert historical["opportunity_state"] == HISTORICAL_MARKET_EVIDENCE
    assert historical["historical_market_evidence_eligible"] is True
    assert historical["verification_content_match"] is True
    assert historical["historical_data_fields_trusted"] is True
    assert historical["verification"][0]["verification_content_match"] is True
    assert result["search_run_report"]["historical_market_evidence"] == 1
    assert result["search_run_report"]["historical_evidence_manual_review"] == 0


def test_title_only_clothing_signal_cannot_promote_generic_blinto_boilerplate():
    candidate = _ended_candidate(
        "Blinto should be contacted before the item is transported. Repair objects "
        "cannot be returned. Passenger cars and trucks under 30000 SEK are repair "
        "objects. Financing final amount, contract period and residual value 10%. "
        "The auction has ended. Highest bid 2000 SEK. Buyer is responsible for "
        "pickup and transportation."
    )

    result = apply_early_opportunity_gate(_report(candidate))
    review = result["all_discovered_candidates"][0]

    assert (
        review["opportunity_state"]
        == HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW
    )
    assert review["historical_market_evidence_eligible"] is False
    assert review["verification_content_match"] is False
    assert review["historical_data_fields_trusted"] is False
    assert review["verification"][0]["verification_content_match"] is False
    assert review["top5_eligible"] is False
    assert review["analysis_eligible"] is False
    assert review["inventory_type"] is None
    assert review["quantity"] is None
    assert review["next_verification_step"] is None
    assert "manually" in review["next_action"]
    assert result["search_run_report"]["historical_market_evidence"] == 0
    assert result["search_run_report"]["historical_evidence_manual_review"] == 1
    assert result["discovery_top5"] == []
