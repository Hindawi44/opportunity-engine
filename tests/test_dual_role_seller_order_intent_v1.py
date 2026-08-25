from opportunity_engine.discovery.exa_shadow_page_verification import (
    ACTIVE_STOCK_SIGNAL,
    SOURCE_INTELLIGENCE_ONLY,
    UNPROVEN_PAGE,
    _classify_page,
)


HOMEPAGE = "https://example.test/"


def test_explicit_seller_order_intent_allows_dual_role_b2b_homepage_navigation_signal() -> None:
    classification, evidence = _classify_page(
        title="Restposten Großhandel Bekleidung für Wiederverkäufer",
        text=(
            "Wir kaufen Restposten aus Insolvenzen. Bekleidung auf Lager. "
            "Verfügbar 1000 Stk. ab 1,20 EUR. "
            "Zügige Bearbeitung von Bestellungen in 1-3 Werktagen."
        ),
        url=HOMEPAGE,
    )

    assert classification == ACTIVE_STOCK_SIGNAL
    assert evidence["buyer_or_source_evidence"] is True
    assert evidence["seller_order_intent_evidence"] is True
    assert evidence["direct_sale_evidence"] is True
    assert evidence["item_specific_url_evidence"] is False
    assert evidence["project_domain"] == "CLOTHING_INVENTORY"


def test_dual_role_inventory_without_explicit_seller_order_intent_stays_source_intelligence() -> None:
    classification, evidence = _classify_page(
        title="Restposten Großhandel Bekleidung für Wiederverkäufer",
        text="Wir kaufen Restposten aus Insolvenzen. Bekleidung auf Lager. Verfügbar 1000 Stk. ab 1,20 EUR.",
        url=HOMEPAGE,
    )

    assert classification == SOURCE_INTELLIGENCE_ONLY
    assert evidence["buyer_or_source_evidence"] is True
    assert evidence["seller_order_intent_evidence"] is False
    assert evidence["direct_sale_evidence"] is False


def test_seller_order_intent_alone_does_not_create_stock_signal() -> None:
    classification, evidence = _classify_page(
        title="Bestellservice",
        text="Zügige Bearbeitung von Bestellungen in 1-3 Werktagen.",
        url=HOMEPAGE,
    )

    assert classification == UNPROVEN_PAGE
    assert evidence["seller_order_intent_evidence"] is True
    assert evidence["inventory_evidence"] is False
