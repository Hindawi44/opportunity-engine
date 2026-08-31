from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    classify_project_domain,
)
from opportunity_engine.discovery.exact_lot_multihop_resolution import (
    _commercial_url_role,
    _extract_navigation_links,
)


def test_verified_swedish_compound_clothing_subject_survives_domain_gate() -> None:
    subject = "Parti fritidskläder för MC-intresserade, 170 plagg"
    assert classify_project_domain(text=subject) == CLOTHING_INVENTORY


def test_partijhandel_route_family_distinguishes_category_and_detail() -> None:
    category = "https://example.test/partijhandel/kleding"
    pagination = "https://example.test/partijhandel/kleding/2"
    detail = "https://example.test/partijhandel/kleding/teenslippers-4575-stuks-diverse-kleuren/37514"
    unrelated = "https://example.test/archive/kleding/teenslippers/37514"

    assert _commercial_url_role(category) == "CATEGORY"
    assert _commercial_url_role(pagination) == "CATEGORY"
    assert _commercial_url_role(detail) == "PRODUCT_DETAIL"
    assert _commercial_url_role(unrelated) is None


def test_partijhandel_category_exposes_exact_lot_detail_links_to_multihop() -> None:
    category = "https://example.test/partijhandel/kleding"
    badkleding = "https://example.test/partijhandel/kleding/baby-en-kinder-badkleding/37526"
    teenslippers = "https://example.test/partijhandel/kleding/teenslippers-4575-stuks-diverse-kleuren/37514"
    html = (
        '<a href="/partijhandel/kleding/baby-en-kinder-badkleding/37526">Baby en kinder badkleding</a>'
        '<a href="/partijhandel/kleding/teenslippers-4575-stuks-diverse-kleuren/37514">Teenslippers</a>'
        '<a href="/partijhandel/kleding/2">Volgende pagina</a>'
        '<a href="/contact">Contact</a>'
    )

    links = _extract_navigation_links(
        page_url=category,
        root_host="example.test",
        html_text=html,
        max_links=12,
    )

    assert badkleding in links
    assert teenslippers in links
    assert "https://example.test/contact" not in links
