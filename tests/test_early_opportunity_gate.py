from pathlib import Path

from opportunity_engine.discovery.early_opportunity_gate import (
    ACTIVE,
    ARTICLE_OR_INFO,
    CONFIRMED_SALE,
    EVENT_LEAD,
    ITEM_LISTING,
    REJECTED_NOISE,
    SOURCE_CHANNEL,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    UNKNOWN,
    UNRESOLVED_SOURCE,
    apply_early_opportunity_gate,
)


def base_report(*candidates):
    return {
        "search_run_report": {
            "schema_version": "clothing-inventory-discovery-search-1.1",
            "rejected_results": len(candidates),
            "confirmed_sales": 0,
            "strong_leads_requiring_verification": 0,
            "top5_count": 0,
            "top5_eligible_count": 0,
            "generic_pages_excluded": len(candidates),
            "discovery_bands": {"HIGH": 0, "REVIEW": 0, "LOW": len(candidates)},
            "automatic_contact": False,
            "automatic_purchase_decision": False,
            "financial_ranking_used": False,
        },
        "all_discovered_candidates": list(candidates),
        "discovery_top5": [],
    }


def candidate(**overrides):
    value = {
        "title": "AXL Sport og Fritid Kolvereid AS konkurs",
        "scenario": "UNVERIFIED_EVENT",
        "opportunity_state": REJECTED_NOISE,
        "reason": "article_or_info is not one specific inventory opportunity",
        "page_role": ARTICLE_OR_INFO,
        "opportunity_identity": None,
        "identity_stable": False,
        "top5_eligible": False,
        "discovery_score": 15,
        "discovery_band": "LOW",
        "score_breakdown": {"source_traceability": 15},
        "location": None,
        "company_name": None,
        "inventory_type": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "published_at": None,
        "listing_status": UNKNOWN,
        "source_urls": ["https://news.example.no/nyheter/axl-konkurs"],
        "source_providers": ["Search"],
        "found_by_queries": ["lead-01"],
        "duplicate_count": 0,
        "evidence_signals": ["konkurs", "klesbutikk", "sportsklær", "varelager"],
        "why_opportunity": [],
        "confirmed_information": [],
        "missing_information": [],
        "next_verification_step": "",
        "verification": [{
            "url": "https://news.example.no/nyheter/axl-konkurs",
            "title": "AXL Sport og Fritid Kolvereid AS konkurs",
            "text": "Klesbutikk og sportsklær. Selskapet er konkurs i Kolvereid.",
            "bounded_context": None,
            "page_role": ARTICLE_OR_INFO,
            "identity_stable": False,
            "event_scenario": "COMPANY_BANKRUPTCY",
            "verified": True,
        }],
    }
    value.update(overrides)
    return value


def test_traceable_bankruptcy_event_enters_top5_but_not_analysis():
    corrected = apply_early_opportunity_gate(base_report(candidate()))

    top = corrected["discovery_top5"][0]
    assert top["page_role"] == EVENT_LEAD
    assert top["scenario"] == "COMPANY_BANKRUPTCY"
    assert top["opportunity_state"] == STRONG_LEAD_REQUIRES_VERIFICATION
    assert top["top5_eligible"] is True
    assert top["analysis_eligible"] is False
    assert top["price_nok"] is None
    assert top["quantity"] is None
    assert top["location"] == "Kolvereid"
    assert corrected["search_run_report"]["early_event_leads_in_top5"] == 1
    assert corrected["search_run_report"]["opportunity_quality_status"] == "REVIEW_REQUIRED"


def test_specific_event_survives_public_page_timeout():
    timed_out = candidate(
        page_role=UNRESOLVED_SOURCE,
        reason="unresolved source without independently proven item-listing identity",
        verification=[{
            "url": "https://news.example.no/nyheter/axl-konkurs",
            "page_role": UNRESOLVED_SOURCE,
            "verified": False,
            "error": "timed out",
        }],
    )
    corrected = apply_early_opportunity_gate(base_report(timed_out))
    assert corrected["discovery_top5"][0]["page_role"] == EVENT_LEAD
    assert corrected["discovery_top5"][0]["analysis_eligible"] is False


def test_root_source_channel_remains_rejected():
    source = candidate(
        title="Kjøp og salg av varepartier - Miko Trading AS",
        page_role=SOURCE_CHANNEL,
        source_urls=["https://miko-trading.no/"],
        evidence_signals=["klesbutikk", "vareparti", "avvikling"],
        verification=[{
            "url": "https://miko-trading.no/",
            "title": "Kjøp og salg av varepartier - Miko Trading AS",
            "text": "Vi kjøper og selger varepartier fra avvikling.",
            "page_role": SOURCE_CHANNEL,
            "verified": True,
            "event_scenario": "UNVERIFIED_EVENT",
        }],
    )
    corrected = apply_early_opportunity_gate(base_report(source))
    assert corrected["discovery_top5"] == []
    assert corrected["all_discovered_candidates"][0]["opportunity_state"] == REJECTED_NOISE
    assert corrected["all_discovered_candidates"][0]["analysis_eligible"] is False


def test_confirmed_active_listing_is_the_only_analysis_eligible_type():
    listing = candidate(
        title="Komplett varelager fra Sport AS selges",
        scenario="AUCTION",
        opportunity_state=CONFIRMED_SALE,
        reason="specific active sale confirmed",
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:7001",
        identity_stable=True,
        top5_eligible=True,
        listing_status=ACTIVE,
        source_urls=["https://estate.example.no/auksjon/7001"],
        evidence_signals=["varelager", "klær", "selges", "auksjon"],
        discovery_score=90,
        discovery_band="HIGH",
        verification=[],
    )
    corrected = apply_early_opportunity_gate(base_report(candidate(), listing))
    by_title = {item["title"]: item for item in corrected["discovery_top5"]}
    assert by_title[listing["title"]]["analysis_eligible"] is True
    assert by_title["AXL Sport og Fritid Kolvereid AS konkurs"]["analysis_eligible"] is False
    assert corrected["search_run_report"]["analysis_eligible_count"] == 1
    assert corrected["search_run_report"]["opportunity_quality_status"] == "PASS"


def test_generic_editorial_article_is_not_promoted_without_entity_anchor():
    generic = candidate(
        title="Slik går det når en klesbutikk går konkurs",
        source_urls=["https://news.example.no/guider/klesbutikk-konkurs"],
        evidence_signals=["konkurs", "klesbutikk"],
        verification=[{
            "url": "https://news.example.no/guider/klesbutikk-konkurs",
            "title": "Slik går det når en klesbutikk går konkurs",
            "text": "En generell guide om hva som skjer når en klesbutikk går konkurs.",
            "page_role": ARTICLE_OR_INFO,
            "verified": True,
            "event_scenario": "COMPANY_BANKRUPTCY",
        }],
    )
    corrected = apply_early_opportunity_gate(base_report(generic))
    assert corrected["discovery_top5"] == []
    assert corrected["all_discovered_candidates"][0]["analysis_eligible"] is False


def test_live_runner_applies_early_opportunity_gate_before_artifact_writing():
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "run_clothing_inventory_discovery_search.py"
    ).read_text(encoding="utf-8")
    assert "raw_result = run_clothing_inventory_discovery(" in script
    assert "result = apply_early_opportunity_gate(raw_result)" in script
    assert "result = apply_post_verification_top5_hard_gate(result)" in script
    assert (
        script.index("apply_early_opportunity_gate(raw_result)")
        < script.index("apply_post_verification_top5_hard_gate(result)")
        < script.index("paths = write_discovery_artifacts")
    )
