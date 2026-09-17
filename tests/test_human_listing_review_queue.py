from opportunity_engine.human_listing_review_queue import build_queue, classify_url, readable_text


def row(url, identity="item-1", status="ACTIVE", market="NO"):
    return {"opportunity_identity": identity, "title": identity, "canonical_url": None,
            "source_urls": [url], "market_code": market, "listing_status": status,
            "source_names": ["test"], "missing_evidence": ["shipping"]}


def test_direct_recovery_and_no_commercial_or_novelty_gate():
    report = {"generated_at": "2026-09-17T00:00:00Z", "commercially_qualified_count": 0,
              "next_human_action": {"action": "NO_IMMEDIATE_ACTION"},
              "deduplicated_opportunities": [row("https://www.finn.no/recommerce/forsale/item/471259920")]}
    queue = build_queue(report)
    assert queue["counts"]["direct_waiting_for_review"] == 1
    assert queue["daily_batch"][0]["stock_confidence"] == "UNVERIFIED"
    assert queue["daily_batch"][0]["site_identity_status"] == "UNVERIFIED"
    assert queue["daily_batch"][0]["page_type"] == "DIRECT_URL_SHAPE_ONLY_UNVERIFIED"
    assert queue["daily_batch"][0]["source_detail_status"] == "POSSIBLE_DIRECT_LISTING_UNVERIFIED"
    assert queue["daily_batch"][0]["seller_phone"] is None
    assert "https://www.finn.no/" in readable_text(queue)


def test_campaign_and_ended_are_separated_and_direct_url_deduped():
    rows = [row("https://psauction.se/auction/69086/parti", "campaign", market="SE"),
            row("https://ny.auksjonen.no/auksjon/torget/lot/123", "ended", "ENDED"),
            row("https://www.finn.no/recommerce/forsale/item/123", "a"),
            row("https://www.finn.no/recommerce/forsale/item/123/", "b")]
    queue = build_queue({"deduplicated_opportunities": rows})
    assert queue["counts"]["direct_waiting_for_review"] == 1
    assert queue["counts"]["duplicate_urls"] == 1
    assert queue["counts"]["historical_or_ended"] == 1
    assert queue["counts"]["non_direct_or_uncertain"] == 1
    assert classify_url("https://psauction.se/auction/69086/parti") == "CAMPAIGN"


def test_study_delete_later_respected_without_fabricated_decisions():
    rows = [row(f"https://www.finn.no/recommerce/forsale/item/{n}", f"item-{n}") for n in range(4)]
    memory = {"deleted_ids": ["item-0"], "study": [{"opportunity_id": "item-1"}],
              "later": [{"opportunity_id": "item-2"}]}
    queue = build_queue({"deduplicated_opportunities": rows}, memory)
    assert [r["identity"] for r in queue["review_queue"]] == ["item-3"]
    assert queue["counts"]["operator_deleted"] == 1
    assert queue["counts"]["in_study_memory"] == 1
    assert queue["counts"]["deferred"] == 1
    assert not queue["choices_persisted_by_this_export"]


def test_host_spoofing_and_variant_query_not_deduped():
    assert classify_url("https://evilfinn.no/recommerce/forsale/item/10") == "UNKNOWN"
    rows = [row("https://stockitaly24.com/products/clothing-lot?variant=1", "variant-1", market="IT"),
            row("https://stockitaly24.com/products/clothing-lot?variant=2", "variant-2", market="IT")]
    queue = build_queue({"deduplicated_opportunities": rows})
    assert queue["counts"]["direct_waiting_for_review"] == 2
    assert all(r["stock_confidence"] == "UNVERIFIED" for r in queue["review_queue"])


def test_generic_routes_and_configurable_boxes_are_not_specific_offers():
    assert classify_url("https://stockitaly24.com/collections/shoes") == "CAMPAIGN"
    assert classify_url("https://stockitaly24.com/products/box") == "CAMPAIGN"
    assert classify_url("https://www.finn.no/450273961") == "DIRECT"
    assert classify_url("https://www.finn.no/recommerce/forsale/item/123") == "DIRECT"
    rows = [row("https://stockitaly24.com/products/box", "generic"),
            row("https://www.finn.no/450273961", "legacy")]
    queue = build_queue({"deduplicated_opportunities": rows})
    assert [r["identity"] for r in queue["review_queue"]] == ["legacy"]
    assert queue["held_separately"][0]["reason"] == "CAMPAIGN"


def test_redirect_to_landing_page_blocks_original_direct_url():
    listing = row("https://stockitaly24.com/products/lot-100")
    listing["pending_investigation"] = {
        "source_url": listing["source_urls"][0],
        "final_url": "https://stockitaly24.com/collections/all",
        "status": "VERIFIED_EXACT_LOT_CANDIDATE",
    }
    queue = build_queue({"deduplicated_opportunities": [listing]})
    assert queue["counts"]["direct_waiting_for_review"] == 0
    assert queue["held_separately"][0]["reason"] == "REDIRECT_TO_CAMPAIGN"


def test_dated_source_item_evidence_does_not_verify_site_or_stock():
    listing = row("https://stockitaly24.com/products/lot-100")
    listing["pending_investigation"] = {
        "source_url": listing["source_urls"][0],
        "final_url": listing["source_urls"][0],
        "status": "VERIFIED_EXACT_LOT_CANDIDATE",
        "last_investigated_at": "2026-09-17T09:00:00Z",
        "evidence": {
            "item_specific_url_evidence": True, "domain_evidence": True,
            "inventory_evidence": True, "direct_sale_evidence": True,
            "price_evidence": True, "quantity_evidence": True,
        },
    }
    queue = build_queue({"deduplicated_opportunities": [listing]})
    item = queue["review_queue"][0]
    assert item["page_type"] == "SOURCE_ITEM_PAGE_EVIDENCE"
    assert item["source_detail_status"] == "EXACT_ITEM_VERIFIED"
    assert item["site_identity_status"] == "UNVERIFIED"
    assert item["stock_confidence"] == "UNVERIFIED"
    listing["pending_investigation"]["evidence"]["price_evidence"] = False
    assert build_queue({"deduplicated_opportunities": [listing]})["review_queue"][0]["source_detail_status"] == "POSSIBLE_DIRECT_LISTING_UNVERIFIED"


def test_excluded_supplier_keeps_historical_record_but_no_new_review_listing():
    assert classify_url("https://vinqa-grossiste.com/products/clothing-box") == "EXCLUDED"
    queue = build_queue({"deduplicated_opportunities": [row("https://vinqa-grossiste.com/products/clothing-box")]})
    assert queue["counts"]["direct_waiting_for_review"] == 0
    assert queue["counts"]["excluded_source"] == 1
    assert queue["held_separately"][0]["reason"] == "EXCLUDED_SOURCE"
