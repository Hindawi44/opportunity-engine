from __future__ import annotations

from opportunity_engine.source_shadow_live_validation import extract_shadow_candidates


def test_worldwise_only_accepts_offer_heading_links_not_navigation() -> None:
    html = '''
    <header>
      <a href="/ambassador/">Join Our Ambassador Program and Get Paid For Referrals</a>
      <a href="/delhi-stocklots/">Delhi Stocklots</a>
      <a href="/import-export-distribution-export-distributors/">Import Export Distribution</a>
    </header>
    <h3><a href="/bulk-clothing-garments-shoes/">Bulk Clothing, Garments, & Shoes</a></h3>
    <h4><a href="/luxury-vinyl-leather-upholstery-rolls-summer-sale/">Luxury Vinyl Leather Upholstery Rolls Summer Sale</a></h4>
    <h4><a href="/new-bicycles-load-your-40ft-now/">New Bicycles – Load your 40ft now!</a></h4>
    '''

    rows = extract_shadow_candidates(
        source_domain="www.worldwiseusa.com",
        source_name="WorldWiseUSA",
        page_url="https://www.worldwiseusa.com/latest-stock-lot-offers/",
        html=html,
        teaching_urls=set(),
    )

    assert [row["source_url"] for row in rows] == [
        "https://www.worldwiseusa.com/luxury-vinyl-leather-upholstery-rolls-summer-sale/",
        "https://www.worldwiseusa.com/new-bicycles-load-your-40ft-now/",
    ]


def test_worldwise_teaching_offer_inside_h4_is_still_excluded() -> None:
    teaching = "https://www.worldwiseusa.com/ready-to-profit-athleisure-load-ready-we-have-your-inventory-report-29000-units/"
    html = f'''<h4><a href="{teaching}">Athleisure 29,000 units</a></h4>'''

    rows = extract_shadow_candidates(
        source_domain="www.worldwiseusa.com",
        source_name="WorldWiseUSA",
        page_url="https://www.worldwiseusa.com/latest-stock-lot-offers/",
        html=html,
        teaching_urls={teaching},
    )

    assert rows == []
