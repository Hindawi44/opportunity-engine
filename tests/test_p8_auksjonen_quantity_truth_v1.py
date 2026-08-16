from __future__ import annotations

import json

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


BAUER_DESCRIPTION = (
    "Selges samlet parti med Bauer jakker, ca. en halv pall. "
    "Partiet består av flere jakker i hovedsakelig blå og mørke farger. "
    "Jakkene fremstår som sports-/fritidsjakker med glidelås, lommer og Bauer-logo. "
    "Passer godt for idrettslag, klubb, forhandler, videresalg eller firmabruk. "
    "Innhold: - Ca. en halv pall med Bauer jakker - Assorterte modeller - "
    "Assorterte størrelser - Hovedsakelig blå og mørke farger - "
    "Selges samlet slik de står og er avbildet - "
    "Eksakt antall og størrelsesfordeling er ikke kontrollert"
)


def _bauer_listing() -> AuksjonenLiveClothingListing:
    return AuksjonenLiveClothingListing(
        title="Halv pall med Bauer jakker – assorterte modeller, farger og størrelser",
        url="https://ny.auksjonen.no/auksjon/torget/Halv_pall_med_Bauer_jakker/619341",
        auction_id=7001,
        object_id=619341,
        status="ACTIVE",
        listing_status="ACTIVE",
        current_bid_nok=250.0,
        buy_now_price_nok=None,
        start_price_nok=None,
        bid_count=1,
        bidder_count=1,
        city="Oslo",
        zip_code="1177",
        address=None,
        ends_at="2026-08-20T10:00:00+00:00",
        main_image="https://example.test/bauer.jpg",
        inventory_lot_signal=True,
    )


def _run_186_like_html() -> str:
    payload = {
        "name": "Halv pall med Bauer jakker – assorterte modeller, farger og størrelser",
        "description": BAUER_DESCRIPTION,
        # This reproduces the dangerous shape from Run #186: a numeric field is
        # present even though the seller explicitly says the exact count is not checked.
        "itemCount": 16,
        "itemCondition": "https://schema.org/UsedCondition",
    }
    return f"""
    <html><body>
      <h1>Halv pall med Bauer jakker – assorterte modeller, farger og størrelser</h1>
      <script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>
      <div class="page-chrome">16 varer i visningen</div>
      <div>Hentested: 1177 Oslo</div>
    </body></html>
    """


def test_run_186_bauer_uncertainty_vetoes_numeric_quantity() -> None:
    result = parse_auksjonen_item_page(_run_186_like_html())

    assert result["quantity"] is None
    assert result["quantity_explicitly_unknown"] is True
    assert result["condition"] == "USED"
    assert result["visual_quantity_inference_performed"] is False


def test_unrelated_visible_item_counter_cannot_become_lot_quantity() -> None:
    html = """
    <html><body>
      <h1>Halv pall med Bauer jakker</h1>
      <meta name="description" content="Assortert parti med jakker. Selges samlet.">
      <div class="navigation">16 varer</div>
      <div>Tilstand: Brukt</div>
    </body></html>
    """

    result = parse_auksjonen_item_page(html)

    assert result["quantity"] is None
    assert result["quantity_explicitly_unknown"] is False


def test_explicit_labeled_quantity_in_visible_page_still_passes() -> None:
    html = """
    <html><body>
      <h1>Parti med arbeidsjakker</h1>
      <meta name="description" content="Samlet parti med arbeidsjakker.">
      <div>Antall: 24</div>
      <div>Tilstand: Ubrukt</div>
    </body></html>
    """

    result = parse_auksjonen_item_page(html)

    assert result["quantity"] == 24
    assert result["quantity_explicitly_unknown"] is False


def test_run_186_bauer_stays_verified_but_not_analysis_ready_without_quantity() -> None:
    listing = _bauer_listing()
    html = _run_186_like_html()

    def fetcher(url: str) -> tuple[str, str, int, str]:
        assert url == listing.url
        return html, url, len(html.encode("utf-8")), "run186"

    evidence = verify_auksjonen_inventory_lots([listing], limit=1, fetcher=fetcher)
    row = evidence[listing.url]
    candidate = auksjonen_listing_to_discovery_candidate(
        listing,
        top5_eligible=True,
        exact_item_evidence=row,
    )

    assert row["exact_item_page_verified"] is True
    assert row["quantity"] is None
    assert row["quantity_explicitly_unknown"] is True
    assert candidate["verified"] is True
    assert candidate["quantity"] is None
    assert candidate["condition"] == "USED"
    assert candidate["analysis_eligible"] is False
    assert candidate["opportunity_state"] == "STRONG_LEAD_REQUIRES_VERIFICATION"
    assert "exact lot quantity" in candidate["verification_blockers"]
    assert candidate["automatic_contact"] is False
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_purchase"] is False
    assert candidate["automatic_payment"] is False
