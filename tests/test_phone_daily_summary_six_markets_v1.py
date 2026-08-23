from opportunity_engine.discovery.phone_readable_market_bulletin import (
    enrich_phone_readable_market_bulletin,
    render_phone_readable_market_bulletin,
)


def _signal(signal_id: str, country: str, title: str) -> dict:
    return {
        "signal_id": signal_id,
        "signal_type": "BUSINESS_CLOSURE",
        "value": title,
        "source": "Example Source",
        "observed_at": "2026-08-23T05:20:00Z",
        "confidence": 0.8,
        "source_country": country,
        "source_url": f"https://example.test/{country.lower()}",
        "title": title,
        "company_name": f"Example {country}",
        "seller_name": None,
        "location": "Example City",
        "first_observed_at": "2026-08-23T05:20:00Z",
        "latest_observed_at": "2026-08-23T05:20:00Z",
        "event_date": None,
        "evidence": [],
        "related_opportunity_id": None,
        "status": "WATCH",
        "metadata": {"signal_only": True},
    }


def test_phone_daily_summary_names_all_six_operated_markets() -> None:
    signals = [
        _signal("closure:FR:one", "FR", "French clothing closure"),
        _signal("closure:IT:one", "IT", "Italian stock liquidation"),
        _signal("closure:NL:one", "NL", "Dutch inventory closure"),
    ]
    brief = {
        "generated_at": "2026-08-23T05:51:00Z",
        "counts": {
            "new_signals_today": 3,
            "changed_signals_since_previous_checkpoint": 0,
            "early_signals_to_watch": 3,
            "current_direct_opportunities": 0,
            "unavailable_or_failed_sources": 0,
        },
        "early_signals_to_watch": signals,
        "current_direct_opportunities": [],
        "selected_human_action": {"action": "VERIFY_MARKET_SIGNAL"},
    }

    enriched = enrich_phone_readable_market_bulletin(
        brief,
        {"current_signals": signals},
    )
    rendered = render_phone_readable_market_bulletin(enriched)

    assert "الأسواق: النرويج | السويد | ألمانيا | فرنسا | إيطاليا | هولندا" in rendered
    assert "السوق: فرنسا" in rendered
    assert "السوق: إيطاليا" in rendered
    assert "السوق: هولندا" in rendered
