from __future__ import annotations

from opportunity_engine.source_shadow_live_validation import (
    extract_shadow_candidates,
    run_shadow_source_validation,
    validate_shadow_sources,
    verify_shadow_candidates,
)


VALIDATED_SOURCES = {
    "schema_version": "source-discovery-shadow-candidates-1.0",
    "source_candidates": [
        {
            "source_domain": "www.worldwiseusa.com",
            "source_name": "WorldWiseUSA",
            "status": "VALIDATED_SOURCE",
            "shadow_eligible": True,
            "production_active": False,
            "evidence_urls": [
                "https://www.worldwiseusa.com/ready-to-profit-athleisure-load-ready-we-have-your-inventory-report-29000-units/",
                "https://www.worldwiseusa.com/ready-to-profit-mens-dress-shirts-0-49-each/",
                "https://www.worldwiseusa.com/flooring-liquidation-for-your-market-can-you-believe-the-price/",
            ],
        },
        {
            "source_domain": "joblot.stocklear.eu",
            "source_name": "Stocklear",
            "status": "VALIDATED_SOURCE",
            "shadow_eligible": True,
            "production_active": False,
            "evidence_urls": [
                "https://joblot.stocklear.eu/auction/21748",
                "https://joblot.stocklear.eu/auction/21762",
            ],
        },
    ],
}


def test_worldwise_shadow_extracts_new_offer_and_blocks_teaching_urls() -> None:
    html = '''
    <a href="/ready-to-profit-athleisure-load-ready-we-have-your-inventory-report-29000-units/">old</a>
    <a href="/epdm-roofing-rolls/">EPDM Roofing Rolls</a>
    <a href="/new-bicycles-load-your-40ft-now/">New Bicycles – Load your 40ft now!</a>
    '''
    rows = extract_shadow_candidates(
        source_domain="www.worldwiseusa.com",
        source_name="WorldWiseUSA",
        page_url="https://www.worldwiseusa.com/latest-stock-lot-offers/",
        html=html,
        teaching_urls=set(VALIDATED_SOURCES["source_candidates"][0]["evidence_urls"]),
    )

    assert [row["source_url"] for row in rows] == [
        "https://www.worldwiseusa.com/epdm-roofing-rolls/",
        "https://www.worldwiseusa.com/new-bicycles-load-your-40ft-now/",
    ]
    assert all(row["shadow_only"] is True for row in rows)
    assert all(row["production_active"] is False for row in rows)


def test_stocklear_shadow_extracts_new_auction_and_blocks_teaching_urls() -> None:
    html = '''
    <a href="/auction/21748">old</a>
    <a href="/auction/21746">Lot of 699 units of assorted products</a>
    <a href="https://joblot.stocklear.eu/auction/21756">Lot of 545 Furniture items</a>
    '''
    rows = extract_shadow_candidates(
        source_domain="joblot.stocklear.eu",
        source_name="Stocklear",
        page_url="https://joblot.stocklear.eu/",
        html=html,
        teaching_urls=set(VALIDATED_SOURCES["source_candidates"][1]["evidence_urls"]),
    )

    assert [row["source_url"] for row in rows] == [
        "https://joblot.stocklear.eu/auction/21746/",
        "https://joblot.stocklear.eu/auction/21756/",
    ]


def test_unvalidated_or_production_active_source_is_never_shadow_scanned() -> None:
    payload = {
        "source_candidates": [
            {
                "source_domain": "example.com",
                "source_name": "Example",
                "status": "CANDIDATE",
                "shadow_eligible": False,
                "production_active": False,
            },
            {
                "source_domain": "other.example",
                "source_name": "Other",
                "status": "VALIDATED_SOURCE",
                "shadow_eligible": True,
                "production_active": True,
            },
        ]
    }

    report = validate_shadow_sources(payload, fetcher=lambda url: "")

    assert report["eligible_source_count"] == 0
    assert report["network_request_count"] == 0
    assert report["production_mutation"] is False


def test_shadow_validation_finds_novel_candidates_without_promoting_them() -> None:
    pages = {
        "https://www.worldwiseusa.com/latest-stock-lot-offers/": '<a href="/epdm-roofing-rolls/">EPDM Roofing Rolls</a>',
        "https://joblot.stocklear.eu/": '<a href="/auction/21746">Lot of 699 units</a>',
    }

    report = validate_shadow_sources(
        VALIDATED_SOURCES,
        fetcher=lambda url: pages[url],
        max_candidates_per_source=5,
    )

    assert report["eligible_source_count"] == 2
    assert report["network_request_count"] == 2
    assert report["novel_candidate_count"] == 2
    assert report["source_results"][0]["production_active"] is False
    assert report["source_results"][1]["production_active"] is False
    assert report["automatic_promotion"] is False
    assert report["production_mutation"] is False


def test_shadow_validation_is_bounded_per_source() -> None:
    html = "".join(
        f'<a href="/auction/{22000 + index}">Lot {index}</a>' for index in range(20)
    )
    payload = {
        "source_candidates": [VALIDATED_SOURCES["source_candidates"][1]]
    }

    report = validate_shadow_sources(
        payload,
        fetcher=lambda url: html,
        max_candidates_per_source=3,
    )

    assert report["novel_candidate_count"] == 3
    assert report["max_candidates_per_source"] == 3


def test_exact_detail_page_is_required_before_shadow_recovery() -> None:
    discovery = {
        "source_results": [
            {
                "source_domain": "joblot.stocklear.eu",
                "source_name": "Stocklear",
                "novel_candidates": [
                    {
                        "source_url": "https://joblot.stocklear.eu/auction/21746",
                        "title": "Lot of 699 units of assorted products",
                        "shadow_only": True,
                        "production_active": False,
                    }
                ],
            }
        ]
    }
    page = """
    Lot of 699 units of assorted products
    Number of pallets Equivalent to 5 standard pallets
    Quality Functional customer returns
    Starting date Tue, August 18, 2026
    Last bid 1 400,00 € VAT excluded
    """

    report = verify_shadow_candidates(discovery, fetcher=lambda url: page)

    assert report["detail_verification_request_count"] == 1
    assert report["verified_new_opportunity_count"] == 1
    [row] = report["verified_new_opportunities"]
    assert row["verification_status"] == "SHADOW_RECOVERED_OPPORTUNITY"
    assert row["source_page_verified"] is True
    assert row["production_active"] is False


def test_unproven_detail_page_never_becomes_recovered_opportunity() -> None:
    discovery = {
        "source_results": [
            {
                "source_domain": "www.worldwiseusa.com",
                "source_name": "WorldWiseUSA",
                "novel_candidates": [
                    {
                        "source_url": "https://www.worldwiseusa.com/about-us/",
                        "title": "About us",
                        "shadow_only": True,
                        "production_active": False,
                    }
                ],
            }
        ]
    }

    report = verify_shadow_candidates(
        discovery,
        fetcher=lambda url: "We are an international trading company.",
    )

    assert report["verified_new_opportunity_count"] == 0


def test_end_to_end_shadow_recovers_unseen_opportunity_without_production_change() -> None:
    pages = {
        "https://www.worldwiseusa.com/latest-stock-lot-offers/": '<a href="/epdm-roofing-rolls/">EPDM Roofing Rolls</a>',
        "https://joblot.stocklear.eu/": '<a href="/auction/21746">Lot of 699 units</a>',
        "https://www.worldwiseusa.com/epdm-roofing-rolls/": "EPDM Roofing Rolls 10 & 12ft widths 50 to 200ft lengths. Stock lot available. Load now.",
        "https://joblot.stocklear.eu/auction/21746/": "Lot of 699 units. Number of pallets 5. Quality Functional customer returns. Last bid 1 400 EUR.",
    }

    report = run_shadow_source_validation(
        VALIDATED_SOURCES,
        fetcher=lambda url: pages[url],
        max_candidates_per_source=3,
        max_detail_requests=4,
    )

    assert report["verdict"] == "SHADOW_RECOVERED_NEW_OPPORTUNITIES"
    assert report["verified_new_opportunity_count"] == 2
    assert report["teaching_url_recovery_count"] == 0
    assert report["production_mutation"] is False
    assert report["automatic_promotion"] is False
    assert report["production_active_source_count"] == 0
