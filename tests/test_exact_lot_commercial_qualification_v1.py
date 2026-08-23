from __future__ import annotations

from opportunity_engine.discovery.exact_lot_commercial_qualification import (
    qualify_exact_lot_commercial_page,
)
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult


BLOCKET_URL = "https://www.blocket.se/recommerce/forsale/item/24362849"


def _verified_page(*, classification: str = "EXACT_LOT_CANDIDATE") -> dict:
    return {
        "market_code": "SE",
        "url": BLOCKET_URL,
        "final_url": BLOCKET_URL,
        "classification": classification,
        "fetch_ok": True,
        "status_code": 200,
        "evidence": {
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
            "item_specific_url_evidence": True,
        },
    }


def _page(text: str) -> PageFetchResult:
    return PageFetchResult(
        requested_url=BLOCKET_URL,
        final_url=BLOCKET_URL,
        ok=True,
        status_code=200,
        title=(
            "Restparti med Poolkantsten/Poolsarg i grå granit - komplett paket "
            "för 3x6meter | Blocket"
        ),
        text=text,
    )


def test_blocket_exact_lot_extracts_source_price_quantity_location_and_condition() -> None:
    text = " ".join(
        [
            "Restparti med Poolkantsten/Poolsarg i grå granit - komplett paket för 3x6meter",
            "Säljes 9 281 kr",
            "Skick : Nytt skick - helt ny",
            "Här säljer vi nu restpartier med kantsten för poolen i lyxig grå granit.",
            "Samtliga stenar är helt nya men har legat på pallförvaring.",
            "Just detta paket är komplett för en 3x6m pool.",
            "Mängd: 30st raka stenar + 4st hörn",
            "Vikavägen 3 14860 Stora Vika",
            "Ytterligare tjänster Frakt och leverans Se alla tjänster",
            "Zurface Sweden Vikavägen 3 14860 Stora Vika Se butik Verifierat företag",
            # Related-listing prices must not replace the main listing price.
            "Mer från Zurface Sweden 8 746 kr Restparti - 6st Blocksteg 6 650 kr Restparti - 14m kantsten",
        ]
    )

    report = qualify_exact_lot_commercial_page(_verified_page(), _page(text))

    assert report["status"] == "QUALIFIED_SOURCE_FACTS"
    assert report["exact_lot_status"] == "CONFIRMED"
    assert report["source_facts"]["price"] == {
        "amount": 9281.0,
        "currency": "SEK",
        "kind": "SOURCE_PRICE",
        "is_final_payable_price": False,
    }
    assert report["source_facts"]["quantity"]["total_units"] == 34
    assert report["source_facts"]["quantity"]["components"] == [
        {"count": 30, "label": "raka stenar"},
        {"count": 4, "label": "hörn"},
    ]
    assert report["source_facts"]["quantity"]["package_scope"] == "3x6m pool"
    assert report["source_facts"]["condition"] == "NEW"
    assert report["source_facts"]["location"] == {
        "street_address": "Vikavägen 3",
        "postal_code": "14860",
        "locality": "Stora Vika",
        "country_code": "SE",
    }
    assert report["source_facts"]["seller"] == {
        "name": "Zurface Sweden",
        "verified_company": True,
    }


def test_shipping_presence_without_price_never_fabricates_logistics_cost_or_buy_decision() -> None:
    text = " ".join(
        [
            "Säljes 9 281 kr",
            "Skick : Nytt skick - helt ny",
            "Just detta paket är komplett för en 3x6m pool.",
            "Mängd: 30st raka stenar + 4st hörn",
            "Vikavägen 3 14860 Stora Vika",
            "Ytterligare tjänster Frakt och leverans Se alla tjänster",
            "Zurface Sweden Verifierat företag",
        ]
    )

    report = qualify_exact_lot_commercial_page(_verified_page(), _page(text))

    assert report["source_facts"]["logistics"] == {
        "shipping_available": True,
        "shipping_price_known": False,
        "shipping_cost": None,
        "shipping_currency": None,
        "status": "AVAILABLE_UNPRICED",
    }
    assert report["analysis_state"] == "REQUIRES_COMMERCIAL_INPUTS"
    assert report["financial_readiness"]["ready_for_financial_engine"] is False
    assert report["financial_decision"] is None
    assert "obtain pickup or delivery cost in NOK" in report["required_analysis_tasks"]
    assert "document conservative resale value and comparables" in report["required_analysis_tasks"]
    assert report["next_human_action"]["action"] == "COMPLETE_LOGISTICS_AND_MARKET_VALUE"
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def test_non_exact_lot_input_fails_closed_before_commercial_promotion() -> None:
    page = _page("Säljes 9 281 kr Mängd: 30st raka stenar + 4st hörn")
    report = qualify_exact_lot_commercial_page(
        _verified_page(classification="ACTIVE_STOCK_SIGNAL"),
        page,
    )

    assert report["status"] == "BLOCKED_NOT_EXACT_LOT"
    assert report["exact_lot_status"] == "NOT_CONFIRMED"
    assert report["source_facts"] is None
    assert report["analysis_state"] == "REQUIRES_VERIFICATION"
    assert report["financial_decision"] is None
    assert report["next_human_action"]["action"] == "VERIFY_EXACT_LOT"
    assert report["automatic_contact"] is False
    assert report["automatic_purchase"] is False
