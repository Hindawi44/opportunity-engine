from scripts.build_source_funnel_report import build_payload


def test_source_funnel_distinguishes_collecting_and_unconfigured_sources() -> None:
    coverage = {
        "sources": [
            {"source": "Auksjonen.no", "access_mode": "public", "configured": True, "active": True},
            {
                "source": "Konkurskupp",
                "access_mode": "authorized_feed",
                "configured": False,
                "active": False,
                "required_configuration": ["KONKURSKUPP_FEED_URL"],
            },
            {"source": "Konkurs.app", "access_mode": "limited_public_api", "configured": True, "active": True},
        ]
    }
    snapshot = {"sources": {"Auksjonen.no": 45, "Konkurs.app": 25}, "source_errors": {}}
    channels = {
        "actionable_opportunities": {
            "items": [{"url": "https://www.auksjonen.no/auksjon/torget/example/1"}]
        },
        "bankruptcy_leads": {"items": [{"source": "Konkurs.app", "url": "https://konkurs.app/example"}]},
    }

    payload = build_payload(coverage, snapshot, channels)
    by_source = {row["source"]: row for row in payload["sources"]}

    assert by_source["Auksjonen.no"]["status"] == "collecting"
    assert by_source["Auksjonen.no"]["fetched"] == 45
    assert by_source["Auksjonen.no"]["actionable_selected"] == 1
    assert by_source["Konkurs.app"]["bankruptcy_leads_selected"] == 1
    assert by_source["Konkurskupp"]["status"] == "awaiting_authorized_configuration"
    assert by_source["Konkurskupp"]["fetched"] == 0
    assert payload["summary"]["fetched_total"] == 70


def test_source_funnel_surfaces_collection_errors() -> None:
    coverage = {"sources": [{"source": "FINN.no", "configured": True, "active": True}]}
    snapshot = {"sources": {"FINN.no": 0}, "source_errors": {"FINN.no": "authorization failed"}}

    payload = build_payload(coverage, snapshot, {})
    row = payload["sources"][0]

    assert row["status"] == "error"
    assert row["error"] == "authorization failed"
    assert payload["summary"]["error_count"] == 1
