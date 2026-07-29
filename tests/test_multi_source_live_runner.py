import json
from pathlib import Path

from opportunity_engine.discovery.auksjonen_multi_category_adapter import (
    AuksjonenMultiCategoryResult,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingListing,
)
from opportunity_engine.discovery.cross_source_clothing_sale_verifier import (
    AuksjonenItemIdentityEvidence,
    CrossSourceVerificationRecord,
    CrossSourceVerificationResult,
)
from opportunity_engine.discovery.vareauksjonen_public_adapter import (
    VareauksjonenCollection,
    VareauksjonenLiveClothingListing,
)
from scripts.run_cross_source_clothing_verification import (
    build_combined_top5,
    write_combined_outputs,
)


def cross_result(*, verified=True):
    listing = AuksjonenLiveClothingListing(
        title="Konkursbo med 300 jakker",
        url="https://ny.auksjonen.no/auksjon/torget/Konkursbo_med_300_jakker/700001",
        auction_id=900001,
        object_id=700001,
        status="INPROGRESS",
        listing_status="ACTIVE",
        current_bid_nok=20_000.0,
        buy_now_price_nok=None,
        start_price_nok=0.0,
        bid_count=3,
        bidder_count=2,
        city="Oslo",
        zip_code="0001",
        address=None,
        ends_at="2026-08-10T10:00:00+00:00",
        main_image="image.jpg",
        inventory_lot_signal=True,
    )
    evidence = AuksjonenItemIdentityEvidence(
        item_url=listing.url,
        object_id=listing.object_id,
        seller_label="MENSWEAR NORGE AS",
        project_auction_text="Selges på vegne av MENSWEAR NORGE AS. Org.nr 930111222.",
        meta_description="Konkursbo med 300 jakker",
        entity_names=("MENSWEAR NORGE AS",),
        organisation_numbers=("930111222",),
        source_status="PARSED",
    )
    record = CrossSourceVerificationRecord(
        listing=listing,
        evidence=evidence,
        matched_lead=None,
        match_method="EXACT_ORGANISATION_NUMBER" if verified else "NONE",
        verification_state=(
            "VERIFIED_ACTIVE_INVENTORY_SALE"
            if verified
            else "NO_BANKRUPTCY_IDENTITY_MATCH"
        ),
        inventory_sale_verified=verified,
        requires_human_verification=False,
    )
    return CrossSourceVerificationResult(
        captured_at="2026-07-30T00:00:00+00:00",
        bankruptcy_from_date="2025-07-30",
        bankruptcy_requests=2,
        bankruptcy_items_received=61,
        bankruptcy_leads=(),
        auksjonen_result=AuksjonenMultiCategoryResult(
            captured_at="2026-07-30T00:00:00+00:00",
            scans=(),
            max_listings=300,
        ),
        records=(record,),
        detail_pages_requested=1,
        scan_complete=True,
        errors=(),
    )


def vare_collection(*, with_opportunity=True, duplicate_url=None):
    listings = ()
    if with_opportunity:
        listings = (
            VareauksjonenLiveClothingListing(
                listing_id=200001,
                title="Restlager med 120 herreklær",
                url=(
                    duplicate_url
                    or "https://www.vareauksjonen.no/Listing/Details/200001/Restlager-med-herreklaer"
                ),
                listing_status="ACTIVE",
                listing_type="Auction",
                price_nok=12_500.0,
                quantity=120,
                location="Trondheim",
                description="Restlager med jakker og bukser selges samlet.",
                image_url="https://images.example/item.jpg",
                clothing_signal=True,
                inventory_lot_signal=True,
                source_pages=("https://www.vareauksjonen.no/Browse",),
            ),
        )
    return VareauksjonenCollection(
        captured_at="2026-07-30T00:00:00+00:00",
        crawl_delay_seconds=10.0,
        page_diagnostics=(
            {"url": "https://www.vareauksjonen.no/Browse", "status": "READ"},
        ),
        candidates=(),
        listings=listings,
        scan_complete=True,
        errors=(),
    )


def test_combined_top5_contains_only_verified_opportunities_in_evidence_order():
    combined = build_combined_top5(cross_result(), vare_collection())

    assert len(combined) == 2
    assert combined[0]["source_channel"] == "KONKURS_APP_AUKSJONEN_EXACT_ORGNR"
    assert combined[0]["price_nok"] == 20_000.0
    assert combined[1]["source_channel"] == "VAREAUKSJONEN_DIRECT_ACTIVE_LOT"
    assert combined[1]["quantity"] == 120
    assert all(item["top5_eligible"] for item in combined)
    assert all(item["automatic_purchase_decision"] is False for item in combined)


def test_unverified_cross_source_record_is_not_promoted():
    combined = build_combined_top5(
        cross_result(verified=False),
        vare_collection(with_opportunity=False),
    )

    assert combined == []


def test_combined_top5_deduplicates_by_exact_url():
    cross = cross_result()
    cross_url = cross.records[0].listing.url
    combined = build_combined_top5(
        cross,
        vare_collection(duplicate_url=cross_url),
    )

    assert len(combined) == 1
    assert combined[0]["source_channel"] == "KONKURS_APP_AUKSJONEN_EXACT_ORGNR"


def test_combined_outputs_keep_one_canonical_commercial_file(tmp_path: Path):
    paths = write_combined_outputs(
        cross_source=cross_result(),
        vareauksjonen=vare_collection(),
        output_dir=tmp_path,
    )

    top5 = json.loads(paths["commercial_top5"].read_text(encoding="utf-8"))
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert len(top5) == 2
    assert report["commercial_top5_count"] == 2
    assert report["scan_complete"] is True
    assert report["paid_search_used"] is False
    assert "Unified commercial Top 5 count: 2" in summary
    assert "Paid Brave/OpenAI calls: 0" in summary
