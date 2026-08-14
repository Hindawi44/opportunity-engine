from __future__ import annotations

from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    parse_auksjonen_item_page,
    verify_auksjonen_inventory_lots,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingListing,
)
from opportunity_engine.discovery.auksjonen_unified_lifecycle import (
    auksjonen_listing_to_discovery_candidate,
)


def _listing(title: str = "Halv pall med Bauer jakker") -> AuksjonenLiveClothingListing:
    return AuksjonenLiveClothingListing(
        title=title,
        url="https://ny.auksjonen.no/auksjon/torget/Halv_pall_med_Bauer_jakker/619341",
        auction_id=7001,
        object_id=619341,
        status="ACTIVE",
        listing_status="ACTIVE",
        current_bid_nok=4200.0,
        buy_now_price_nok=None,
        start_price_nok=1000.0,
        bid_count=5,
        bidder_count=3,
        city="Oslo",
        zip_code="1177",
        address="Kongsveien 94",
        ends_at="2026-08-15T10:00:00+00:00",
        main_image="https://example.test/bauer.jpg",
        inventory_lot_signal=True,
    )


def test_half_pallet_does_not_invent_piece_quantity() -> None:
    html = """
    <html><body>
      <h1>Halv pall med Bauer jakker – assorterte modeller, farger og størrelser</h1>
      <div>Tilstand: Ny</div>
      <div>Hentested: 1177 Oslo</div>
      <img src="https://images.example.test/bauer-1.jpg">
    </body></html>
    """
    result = parse_auksjonen_item_page(html)
    assert result["quantity"] is None
    assert result["condition"] == "NEW_OR_UNUSED"
    assert result["source_postal_code"] == "1177"
    assert result["source_city"] == "Oslo"
    assert result["weight_kg"] is None
    assert result["pallet_count"] is None
    assert result["image_count"] == 1
    assert result["visual_quantity_inference_performed"] is False
    assert result["estimated_values_added"] is False


def test_extracts_only_explicit_shipping_and_commercial_fields() -> None:
    html = """
    <html><body>
      <h1>24 stk arbeidsjakker</h1>
      <div>Antall: 24</div>
      <div>Tilstand: Ubrukt</div>
      <div>Hentested: 7800 Namsos</div>
      <div>Vekt: 84 kg</div>
      <div>Dimensjoner: 120 x 80 x 95 cm</div>
      <div>Antall paller: 1</div>
      <div>Kjøpersalær: 20 %</div>
      <div>MVA: 25 %</div>
    </body></html>
    """
    result = parse_auksjonen_item_page(html)
    assert result["quantity"] == 24
    assert result["condition"] == "NEW_OR_UNUSED"
    assert result["weight_kg"] == 84.0
    assert result["length_cm"] == 120.0
    assert result["width_cm"] == 80.0
    assert result["height_cm"] == 95.0
    assert result["pallet_count"] == 1
    assert result["buyer_premium_percent"] == 20.0
    assert result["vat_percent"] == 25.0


def test_verified_exact_page_hydrates_candidate_and_clears_verification_gate() -> None:
    listing = _listing("24 stk Bauer jakker")
    html = """
    <html><body>
      <h1>24 stk Bauer jakker</h1>
      <div>Antall: 24</div>
      <div>Tilstand: Ny</div>
      <div>Hentested: 1177 Oslo</div>
      <div>Vekt: 60 kg</div>
      <div>Dimensjoner: 120 x 80 x 70 cm</div>
    </body></html>
    """

    def fetcher(url: str) -> tuple[str, str, int, str]:
        assert url == listing.url
        return html, url, len(html.encode("utf-8")), "abc123"

    evidence = verify_auksjonen_inventory_lots([listing], limit=1, fetcher=fetcher)
    candidate = auksjonen_listing_to_discovery_candidate(
        listing,
        top5_eligible=True,
        exact_item_evidence=evidence[listing.url],
    )

    assert candidate["verified"] is True
    assert candidate["analysis_eligible"] is True
    assert candidate["opportunity_state"] == "ACTIVE_OPPORTUNITY"
    assert candidate["verification_blockers"] == []
    assert candidate["quantity"] == 24
    assert candidate["condition"] == "NEW_OR_UNUSED"
    assert candidate["source_postal_code"] == "1177"
    assert candidate["source_city"] == "Oslo"
    assert candidate["weight_kg"] == 60.0
    assert candidate["length_cm"] == 120.0
    assert candidate["width_cm"] == 80.0
    assert candidate["height_cm"] == 70.0
    assert candidate["exact_item_page_verified"] is True
    assert candidate["automatic_contact"] is False
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_purchase"] is False
    assert candidate["automatic_payment"] is False


def test_failed_page_verification_does_not_promote_or_guess() -> None:
    listing = _listing()

    def fetcher(url: str) -> tuple[str, str, int, str]:
        raise TimeoutError("synthetic timeout")

    evidence = verify_auksjonen_inventory_lots([listing], limit=1, fetcher=fetcher)
    candidate = auksjonen_listing_to_discovery_candidate(
        listing,
        top5_eligible=True,
        exact_item_evidence=evidence[listing.url],
    )

    assert candidate["verified"] is False
    assert candidate["analysis_eligible"] is False
    assert candidate["opportunity_state"] == "STRONG_LEAD_REQUIRES_VERIFICATION"
    assert candidate["quantity"] is None
    assert "verified exact item-page evidence" in candidate["verification_blockers"]
