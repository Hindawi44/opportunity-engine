from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingCollection,
    normalize_public_api_item,
)
from opportunity_engine.discovery.auksjonen_unified_lifecycle import (
    auksjonen_listing_to_discovery_candidate,
)
from opportunity_engine.discovery.checkpoint_state_restore import LEARNING_STATE_FILENAMES
from opportunity_engine.parser_gap_rescue import apply_auksjonen_parser_rescue


def _active_item(title: str, object_id: int) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "status": "ACTIVE",
        "bidExpired": False,
        "endTime": int((now + timedelta(days=1)).timestamp() * 1000),
        "auctionId": object_id,
        "objectId": object_id,
        "currentBidAmount": 1000,
        "city": "Oslo",
    }


def _collection(*titles: str) -> AuksjonenLiveClothingCollection:
    listings = []
    for index, title in enumerate(titles, start=1):
        listing = normalize_public_api_item(_active_item(title, 420000 + index))
        assert listing is not None
        listings.append(listing)
    return AuksjonenLiveClothingCollection(
        captured_at=datetime.now(timezone.utc).isoformat(),
        endpoint="test",
        reported_size=len(listings),
        items_received=len(listings),
        listings=tuple(listings),
        pages_fetched=1,
        page_size=30,
        errors=(),
    )


def test_rescue_promotes_only_exact_learned_token_after_clothing_gate() -> None:
    collection = _collection(
        "Sluttlager med arbeidsjakker",
        "Sluttlageret med bukser",
        "Arbeidsjakke modell 2026",
    )

    rescued = apply_auksjonen_parser_rescue(collection, ("sluttlager",))

    assert len(rescued.inventory_opportunities) == 1
    assert rescued.inventory_opportunities[0].title == "Sluttlager med arbeidsjakker"
    assert len(rescued.individual_clothing_items) == 2
    assert normalize_public_api_item(_active_item("Sluttlager med gravemaskiner", 999999)) is None


def test_static_inventory_lot_and_unmatched_individuals_keep_normal_semantics() -> None:
    collection = _collection(
        "Varelager med arbeidsjakker",
        "Arbeidsjakke modell 2026",
    )

    rescued = apply_auksjonen_parser_rescue(collection, ("sluttlager",))

    assert len(rescued.inventory_opportunities) == 1
    assert rescued.inventory_opportunities[0].title == "Varelager med arbeidsjakker"
    assert len(rescued.individual_clothing_items) == 1


def test_rescued_listing_still_requires_exact_item_verification() -> None:
    collection = _collection("Sluttlager med arbeidsjakker")
    rescued = apply_auksjonen_parser_rescue(collection, ("sluttlager",))
    listing = rescued.inventory_opportunities[0]

    candidate = auksjonen_listing_to_discovery_candidate(
        listing,
        top5_eligible=True,
        exact_item_evidence=None,
    )

    assert candidate["verified"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["opportunity_state"] == "STRONG_LEAD_REQUIRES_VERIFICATION"
    assert "verified exact item-page evidence" in candidate["verification_blockers"]


def test_daily_auksjonen_runtime_applies_overlay_before_exact_item_verification() -> None:
    source = Path("scripts/run_auksjonen_live_clothing.py").read_text(encoding="utf-8")

    load_at = source.index("load_parser_rescue_terms(")
    rescue_at = source.index("apply_auksjonen_parser_rescue(")
    verify_at = source.index("verify_auksjonen_inventory_lots(")

    assert "INPUT_ROOT" in source
    assert "PARSER_RESCUE_OVERLAY_FILENAME" in source
    assert load_at < rescue_at < verify_at


def test_post_bulletin_learning_order_is_capture_then_route_then_parser_learning() -> None:
    source = Path(
        "src/opportunity_engine/discovery/unified_market_intelligence_river_cli_hook.py"
    ).read_text(encoding="utf-8")

    capture_at = source.index("write_automatic_missed_opportunity_capture(")
    route_at = source.index("write_root_cause_feedback_router(")
    parser_at = source.index("write_parser_gap_rescue_overlay(")

    assert capture_at < route_at < parser_at


def test_parser_overlay_is_durable_checkpoint_learning_state() -> None:
    assert "parser-rescue-overlay.json" in LEARNING_STATE_FILENAMES
