import json
from dataclasses import replace

import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ITEM_LISTING,
    PageVerification,
)
from opportunity_engine.discovery.finn_playwright_pilot import (
    DEFAULT_FINN_SEARCH_URL,
    FinnPilotListing,
    FinnPlaywrightCollection,
    FinnPlaywrightPilotConfig,
    normalize_search_cards,
    run_finn_playwright_pilot,
    write_finn_playwright_pilot_artifacts,
)

NOW = "2026-07-28T10:00:00+00:00"
ITEM_URL = "https://www.finn.no/recommerce/forsale/item/468124077"
IMAGE_URL = "https://images.finncdn.no/dynamic/default/468124077.jpg"


def verified_listing(**overrides):
    verification = PageVerification(
        url=ITEM_URL,
        title="Restlager fra norsk klesmerke – ca. 1000 plagg selges samlet",
        text=(
            "Restlager fra norsk klesmerke med 1000 plagg selges samlet. "
            "Til salgs i Oslo. Pris 50 000 kr."
        ),
        location="Oslo",
        inventory_type="klær",
        price_nok=50000,
        quantity=1000,
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity="url-id:468124077",
        identity_stable=True,
        clothing_inventory_evidence=True,
        sale_evidence=True,
        event_scenario="LARGE_LOT_SALE",
        bounded_context=(
            "Restlager fra norsk klesmerke med 1000 plagg selges samlet. "
            "Til salgs i Oslo. Pris 50 000 kr."
        ),
        verified=True,
    )
    values = {
        "listing_id": "468124077",
        "title": verification.title,
        "url": ITEM_URL,
        "description": verification.text,
        "price_nok": 50000,
        "location": "Oslo",
        "image_urls": (IMAGE_URL,),
        "listing_status": ACTIVE,
        "captured_at": NOW,
        "search_url": DEFAULT_FINN_SEARCH_URL,
        "verification": verification,
    }
    values.update(overrides)
    return FinnPilotListing(**values)


def collection(*listings):
    return FinnPlaywrightCollection(
        captured_at=NOW,
        listings=tuple(listings),
        search_urls=(DEFAULT_FINN_SEARCH_URL,),
        network_pages_visited=len(listings) + 1,
        delay_seconds=3.0,
        max_listings=20,
    )


def test_config_requires_written_permission_and_enforces_bounded_volume():
    with pytest.raises(ValueError, match="written automation permission"):
        FinnPlaywrightPilotConfig(written_permission_reference="")
    with pytest.raises(ValueError, match="between 20 and 50"):
        FinnPlaywrightPilotConfig(
            written_permission_reference="FINN-EMAIL-REF",
            max_listings=19,
        )
    with pytest.raises(ValueError, match="between 20 and 50"):
        FinnPlaywrightPilotConfig(
            written_permission_reference="FINN-EMAIL-REF",
            max_listings=51,
        )
    with pytest.raises(ValueError, match="at least 2"):
        FinnPlaywrightPilotConfig(
            written_permission_reference="FINN-EMAIL-REF",
            delay_seconds=1,
        )


def test_config_accepts_only_public_finn_search_urls():
    with pytest.raises(ValueError, match="FINN Torget search page"):
        FinnPlaywrightPilotConfig(
            written_permission_reference="FINN-EMAIL-REF",
            search_urls=("https://example.no/search",),
        )
    with pytest.raises(ValueError, match="FINN Torget search page"):
        FinnPlaywrightPilotConfig(
            written_permission_reference="FINN-EMAIL-REF",
            search_urls=(ITEM_URL,),
        )


def test_search_card_normalization_deduplicates_stable_item_ids():
    rows = [
        {
            "url": ITEM_URL,
            "title": "  Restlager fra norsk klesmerke  ",
            "description": "  1000 plagg selges samlet  ",
            "image_urls": [IMAGE_URL, IMAGE_URL, "http://unsafe.example/image.jpg"],
        },
        {
            "url": f"{ITEM_URL}?utm_source=test",
            "title": "Duplicate",
            "description": "",
            "image_urls": [],
        },
        {
            "url": "https://example.no/recommerce/forsale/item/99",
            "title": "Wrong host",
            "description": "",
            "image_urls": [],
        },
    ]

    cards = normalize_search_cards(rows, search_url=DEFAULT_FINN_SEARCH_URL)

    assert len(cards) == 1
    assert cards[0]["listing_id"] == "468124077"
    assert cards[0]["title"] == "Restlager fra norsk klesmerke"
    assert cards[0]["image_urls"] == (IMAGE_URL,)


def test_authorized_collection_runs_existing_discovery_and_keeps_images():
    result = run_finn_playwright_pilot(collection(verified_listing()))

    report = result["search_run_report"]
    assert report["collection_mode"] == "AUTHORIZED_FINN_PLAYWRIGHT_PILOT"
    assert report["network_listings_collected"] == 1
    assert report["permission_reference_present"] is True
    assert report["automatic_contact"] is False
    assert report["automatic_purchase_decision"] is False

    candidate = result["discovery_top5"][0]
    assert candidate["opportunity_state"] == "CONFIRMED_SALE"
    assert candidate["analysis_eligible"] is True
    assert candidate["price_nok"] == 50000
    assert candidate["location"] == "Oslo"
    assert candidate["image_urls"] == [IMAGE_URL]
    assert candidate["source_capture"][0]["listing_id"] == "468124077"


def test_collection_above_twenty_is_batched_without_changing_query_matrix():
    listings = []
    for offset in range(21):
        listing_id = str(468124077 + offset)
        url = f"https://www.finn.no/recommerce/forsale/item/{listing_id}"
        base = verified_listing()
        listings.append(verified_listing(
            listing_id=listing_id,
            title=f"{base.title} parti {offset + 1}",
            url=url,
            verification=replace(
                base.verification,
                url=url,
                title=f"{base.title} parti {offset + 1}",
                opportunity_identity=f"url-id:{listing_id}",
            ),
        ))

    result = run_finn_playwright_pilot(collection(*listings))

    assert result["search_run_report"]["queries_submitted"] == 2
    assert result["search_run_report"]["network_listings_collected"] == 21
    assert result["search_run_report"]["merged_candidates"] == 21
    assert len(result["discovery_top5"]) == 5


def test_unverified_detail_never_becomes_confirmed_sale():
    unresolved = verified_listing(
        price_nok=None,
        location=None,
        listing_status="UNKNOWN",
        verification=PageVerification(
            url=ITEM_URL,
            verified=False,
            error="timed out",
        ),
    )

    result = run_finn_playwright_pilot(collection(unresolved))

    candidate = result["all_discovered_candidates"][0]
    assert candidate["opportunity_state"] == "STRONG_LEAD_REQUIRES_VERIFICATION"
    assert candidate["analysis_eligible"] is False
    assert candidate["price_nok"] is None


def test_writes_raw_collection_without_permission_reference_value(tmp_path):
    pilot_collection = collection(verified_listing())
    result = run_finn_playwright_pilot(pilot_collection)

    paths = write_finn_playwright_pilot_artifacts(
        result,
        pilot_collection,
        tmp_path,
    )

    raw = json.loads(paths["finn_playwright_collection"].read_text())
    assert raw["permission_reference_present"] is True
    assert "FINN-EMAIL-REF" not in paths["finn_playwright_collection"].read_text()
    assert raw["listings"][0]["image_urls"] == [IMAGE_URL]
    assert paths["discovery_top5"].exists()
