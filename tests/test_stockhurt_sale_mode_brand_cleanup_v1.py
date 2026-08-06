from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery import stockhurt_official_catalog_enrichment as target
from opportunity_engine.discovery.stockhurt_sale_mode_brand_cleanup import (
    PATCH_SCHEMA_VERSION,
    extract_official_product_brands,
    stockhurt_candidate_with_sale_mode_brand_cleanup,
)

NOW = datetime(2026, 8, 6, 11, 25, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"


def _html(
    *,
    title: str,
    brand: str,
    strong_auction_fields: bool = False,
) -> str:
    transaction = (
        "Current bid: 100 PLN. Auction ends: 30 August 2026 18:00."
        if strong_auction_fields
        else "Prices are net. Contact us for available wholesale packages."
    )
    return f"""
    <html><head>
      <meta property="og:title" content="{title}" />
      <meta name="description" content="Wholesale clothing stock grade A" />
    </head><body>
      <nav>
        <a href="/en/auctions/">Auctions</a>
        <a href="/en/product/calvin-klein-stock/">Calvin Klein clothing auction</a>
      </nav>
      <h1>{title}</h1>
      <div>{transaction}</div>
      <div>Brand: {brand} Category: Clothes Unit: kg Grade A</div>
      <div>Available quantity: 2500 kg. Minimum weight of 20 kg.</div>
      <div>Condition: new products packaged in foil with paper tags.</div>
      <div>International shipping information available.</div>
      <div>Product code: CLEAN-1</div>
    </body></html>
    """


def _link(*, scope: str, title: str) -> target.CatalogLink:
    return target.CatalogLink(
        url="https://stockhurt.com/en/product/clean-product/",
        catalog_url=(target.AUCTION_URL if scope == "PALLET_AUCTIONS" else target.SHOP_URL),
        catalog_scope=scope,
        context=title,
        clothing_terms=("clothing",),
        commercial_terms=("wholesale",),
        discovery_rank=100,
    )


def test_wholesale_catalog_scope_overrides_global_navigation_auction_text() -> None:
    title = "MIX TO premium jackets grade A (pcs)"
    candidate = stockhurt_candidate_with_sale_mode_brand_cleanup(
        source_url="https://stockhurt.com/en/product/mix-to-jackets/",
        html_text=_html(title=title, brand="MIX TO"),
        observed_at=NOW,
        catalog_link=_link(scope="WHOLESALE_SHOP", title=title),
    )
    assert candidate is not None
    assert candidate["catalog_scope"] == "WHOLESALE_SHOP"
    assert candidate["sale_mode"] == "FIXED_PRICE_OR_ENQUIRY"
    assert candidate["page_role"] == "SPECIFIC_STOCK_OFFER"
    assert candidate["sale_mode_classification_basis"] == "OFFICIAL_CATALOG_SCOPE"
    assert candidate["auction_terms"] == []
    assert candidate["ignored_navigation_auction_terms"] == ["auction", "auctions"]
    assert "AUCTION_END_TIME" not in candidate["missing_information"]
    assert candidate["brands"] == ["MIX TO"]
    assert candidate["brand_navigation_text_ignored"] is True
    assert candidate["automatic_bid"] is False
    assert candidate["automatic_purchase"] is False


def test_auction_catalog_scope_remains_auction() -> None:
    title = "Nike clothing pallet grade A"
    candidate = stockhurt_candidate_with_sale_mode_brand_cleanup(
        source_url="https://stockhurt.com/en/product/nike-auction-lot/",
        html_text=_html(title=title, brand="Nike", strong_auction_fields=True),
        observed_at=NOW,
        catalog_link=_link(scope="PALLET_AUCTIONS", title=title),
    )
    assert candidate is not None
    assert candidate["sale_mode"] == "AUCTION"
    assert candidate["page_role"] == "PALLET_AUCTION_OFFER"
    assert candidate["sale_mode_classification_basis"] == "OFFICIAL_CATALOG_SCOPE"
    assert candidate["current_bid"] == 100
    assert candidate["brands"] == ["Nike"]


def test_page_evidence_is_used_only_when_catalog_scope_is_missing() -> None:
    fixed = stockhurt_candidate_with_sale_mode_brand_cleanup(
        source_url="https://stockhurt.com/en/product/studio-select/",
        html_text=_html(
            title="Studio Select Grade A Clothing (kg)",
            brand="Studio Select",
        ),
        observed_at=NOW,
        catalog_link=None,
    )
    auction = stockhurt_candidate_with_sale_mode_brand_cleanup(
        source_url="https://stockhurt.com/en/product/studio-select-auction/",
        html_text=_html(
            title="Studio Select Grade A Clothing (kg)",
            brand="Studio Select",
            strong_auction_fields=True,
        ),
        observed_at=NOW,
        catalog_link=None,
    )
    assert fixed is not None and auction is not None
    assert fixed["sale_mode"] == "FIXED_PRICE_OR_ENQUIRY"
    assert fixed["sale_mode_classification_basis"] == "PRODUCT_PAGE_TRANSACTION_FIELDS"
    assert auction["sale_mode"] == "AUCTION"
    assert auction["sale_mode_classification_basis"] == "PRODUCT_PAGE_TRANSACTION_FIELDS"


def test_brand_cleanup_matches_live_titles_and_discards_noise() -> None:
    cases = (
        ("MIX TO premium jackets grade A (pcs)", "MIX TO", ["MIX TO"]),
        ("Giorgio Di Mare Grade A Clothing (kg)", "Giorgio Di Mare", ["Giorgio Di Mare"]),
        ("Studio Select Grade A Clothing (kg)", "Studio Select", ["Studio Select"]),
    )
    for title, brand, expected in cases:
        html = _html(title=title, brand=brand)
        assert extract_official_product_brands(title=title, html_text=html) == expected


def test_installation_contract_updates_schema_and_keeps_human_authority() -> None:
    assert target.SCHEMA_VERSION == PATCH_SCHEMA_VERSION
    text = INIT_FILE.read_text(encoding="utf-8")
    assert "install_stockhurt_sale_mode_brand_cleanup" in text
    candidate = target.stockhurt_candidate_from_product_html(
        source_url="https://stockhurt.com/en/product/giorgio-di-mare/",
        html_text=_html(
            title="Giorgio Di Mare Grade A Clothing (kg)",
            brand="Giorgio Di Mare",
        ),
        observed_at=NOW,
        catalog_link=_link(
            scope="WHOLESALE_SHOP",
            title="Giorgio Di Mare Grade A Clothing (kg)",
        ),
    )
    assert candidate is not None
    assert candidate["sale_mode"] == "FIXED_PRICE_OR_ENQUIRY"
    assert candidate["brands"] == ["Giorgio Di Mare"]
    assert candidate["decision_owner"] == "HUMAN_OPERATOR"
    assert candidate["quantity_size_rejection_applied"] is False
