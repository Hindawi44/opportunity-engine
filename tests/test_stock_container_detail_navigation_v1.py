from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
    _looks_item_specific_url,
)
from opportunity_engine.discovery.exact_lot_multihop_resolution import _extract_navigation_links


ROOT = "https://example.test/"
DETAIL = "https://example.test/stock/donna/stock-motivi/"
CATEGORY = "https://example.test/stock/donna/"
GENERIC_CATEGORY = "https://example.test/stock/donna/abbigliamento/"


def test_stock_container_requires_category_and_meaningful_detail_slug() -> None:
    assert _looks_item_specific_url("https://example.test/stock/") is False
    assert _looks_item_specific_url(CATEGORY) is False
    assert _looks_item_specific_url(GENERIC_CATEGORY) is False
    assert _looks_item_specific_url(DETAIL) is True


def test_stock_detail_route_is_navigation_eligible_from_existing_root() -> None:
    html = (
        '<a href="/stock/donna/">Donna</a>'
        '<a href="/stock/donna/abbigliamento/">Abbigliamento</a>'
        '<a href="/stock/donna/stock-motivi/">Stock Motivi</a>'
        '<a href="/stock/uomo/stock-piumini-500-pezzi/">Stock Piumini</a>'
    )

    links = _extract_navigation_links(
        page_url=ROOT,
        root_host="example.test",
        html_text=html,
        max_links=12,
    )

    assert DETAIL in links
    assert "https://example.test/stock/uomo/stock-piumini-500-pezzi/" in links
    assert CATEGORY not in links
    assert GENERIC_CATEGORY not in links


def test_stock_detail_url_is_only_specificity_evidence_not_qualification() -> None:
    classification, evidence = _classify_page(
        title="Stock lotti Motivi abbigliamento donna",
        text="Stock abbigliamento donna in vendita. Lotto da 100 pezzi. Prezzo 9,50 euro al pezzo.",
        url=DETAIL,
    )
    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["project_domain"] == "CLOTHING_INVENTORY"

    weak_classification, weak_evidence = _classify_page(
        title="Stock Motivi",
        text="Informazioni generali sul catalogo.",
        url=DETAIL,
    )
    assert weak_classification != EXACT_LOT_CANDIDATE
    assert weak_evidence["item_specific_url_evidence"] is True
