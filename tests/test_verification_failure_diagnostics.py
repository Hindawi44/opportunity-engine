from scripts.run_clothing_inventory_discovery_search import (
    collect_verification_failure_details,
)


def test_collect_verification_failure_details_reports_only_failed_hard_gate_candidates():
    result = {
        "all_discovered_candidates": [
            {
                "title": "Vareparti med arbeidstøy",
                "source_urls": ["https://auksjonen.no/auksjon/arbeidstoy/185420"],
                "opportunity_identity": "url-id:185420",
                "textile_category": "CLOTHING_INVENTORY",
                "post_verification_top5_block_reason": "verification_failed",
                "verification": [
                    {
                        "url": "https://auksjonen.no/auksjon/arbeidstoy/185420",
                        "verified": False,
                        "error": "HTTP Error 403: Forbidden",
                        "page_role": "UNRESOLVED_SOURCE",
                        "listing_status": "UNKNOWN",
                    }
                ],
            },
            {
                "title": "Ended item",
                "post_verification_top5_block_reason": "listing_ended_or_unavailable",
                "verification": [
                    {
                        "verified": True,
                        "listing_status": "ENDED",
                    }
                ],
            },
        ]
    }

    assert collect_verification_failure_details(result) == [
        {
            "title": "Vareparti med arbeidstøy",
            "url": "https://auksjonen.no/auksjon/arbeidstoy/185420",
            "error": "HTTP Error 403: Forbidden",
            "page_role": "UNRESOLVED_SOURCE",
            "listing_status": "UNKNOWN",
            "opportunity_identity": "url-id:185420",
            "textile_category": "CLOTHING_INVENTORY",
        }
    ]


def test_collect_verification_failure_details_fails_closed_on_invalid_payload():
    assert collect_verification_failure_details({}) == []
    assert collect_verification_failure_details({"all_discovered_candidates": "invalid"}) == []
