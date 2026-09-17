"""Balanced discovery is supplemental; the strict verification queue is untouched."""
from opportunity_engine.balanced_link_review import (
    _source_item_pattern, build_balanced_review, readable_balanced_review,
)


def record(identity, url, *, title="Clothing lot", score=80, status="ACTIVE",
           workflow="REQUIRES_VERIFICATION", final=None):
    row = {"opportunity_identity": identity, "title": title, "source_urls": [url],
           "market_code": "NL", "discovery_score": score,
           "listing_status": status, "workflow_status": workflow}
    if final:
        row["pending_investigation"] = {"final_url": final, "source_url": url}
    return row


def held(row, reason):
    return {"identity": row["opportunity_identity"], "reason": reason,
            "title": row["title"], "source_urls": row["source_urls"]}


def test_restore_source_specific_lots_without_claiming_a_verified_offer():
    cube = record("cube-600", "https://cubecompany.nl/product/partij-600-stuks/",
                  title="Partij dameskleding 600 stuks")
    dutch = record("nl-6383", "https://www.partijhandelaren.nl/partijhandel/kleding/lot-25-stuks/6383")
    de = record("de-10628342", "https://www.restposten24.de/restposten-textilien/10628342")
    market = record("cdon", "https://cdon.se/produkt/parti-klader-579b4f423d5f43e1/")
    report = {"deduplicated_opportunities": [cube, dutch, de, market]}
    queue = {"review_queue": [], "held_separately": [held(row, "REDIRECT_TO_UNKNOWN" if row is market else "UNKNOWN")
                                                  for row in report["deduplicated_opportunities"]]}
    result = build_balanced_review(report, queue)
    assert result["counts"]["recovered_unverified_item_leads"] == 4
    assert not result["automatic_contact"] and not result["automatic_purchase"]
    assert all(not row["page_identity_verified"] and not row["stock_verified"]
               and not row["site_identity_verified"] for row in result["recovered_unverified_item_leads"])
    assert queue["review_queue"] == []  # No automatic promotion into proven pages.
    assert "600" in readable_balanced_review(result)


def test_parent_pages_remain_navigation_only_and_excluded_domain_never_resurfaces():
    campaign = record("ps", "https://psauction.se/auction/69199/avyttring-butiksinredning",
                      title="Avyttring butiksinredning", score=56)
    excluded = record("bad", "https://vinqa-grossiste.com/products/box-jeans")
    generic = record("home", "https://example.com/category/clothes")
    report = {"deduplicated_opportunities": [campaign, excluded, generic]}
    queue = {"review_queue": [], "held_separately": [held(campaign, "CAMPAIGN"),
            held(excluded, "EXCLUDED_SOURCE"), held(generic, "CAMPAIGN")]}
    result = build_balanced_review(report, queue)
    assert result["counts"] == {"recovered_unverified_item_leads": 0,
                                "campaign_parents_for_child_extraction": 1}
    parent = result["campaign_parents_for_child_extraction"][0]
    assert parent["role"] == "PARENT_PAGE_FIND_CHILD_LISTINGS"
    assert parent["child_listings_extracted"] is False
    assert parent["offer_or_stock_verified"] is False
    assert "vinqa-grossiste" not in readable_balanced_review(result)


def test_redirect_site_spoofing_history_and_human_memory_block_recovery():
    url = "https://cubecompany.nl/product/partij-600-stuks/"
    xsite = record("redirect", url, final="https://different.example/product/lot")
    ended = record("ended", "https://cubecompany.nl/product/old/", status="ENDED")
    deleted = record("deleted", "https://cubecompany.nl/product/deleted/")
    known = record("already-visible", "https://cubecompany.nl/product/visible/")
    report = {"deduplicated_opportunities": [xsite, ended, deleted, known]}
    queue = {"review_queue": [{"identity": "already-visible"}],
             "held_separately": [held(row, "UNKNOWN") for row in report["deduplicated_opportunities"]]}
    result = build_balanced_review(report, queue, {"deleted_ids": ["deleted"]})
    assert result["recovered_unverified_item_leads"] == []
    assert not _source_item_pattern("https://evilcubecompany.nl/product/lot")
    assert not _source_item_pattern("https://vinqa-grossiste.com/products/box-jeans")
    assert not _source_item_pattern("https://cubecompany.nl/collections/all")


def test_low_score_and_non_product_directory_are_not_recovered():
    low = record("low", "https://cubecompany.nl/product/lot/", score=20)
    directory = record("directory", "https://www.europages.fr/fr/company/seller/products/lot")
    report = {"deduplicated_opportunities": [low, directory]}
    queue = {"review_queue": [], "held_separately": [held(low, "UNKNOWN"), held(directory, "UNKNOWN")]}
    assert build_balanced_review(report, queue)["recovered_unverified_item_leads"] == []
