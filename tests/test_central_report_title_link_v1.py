from __future__ import annotations

from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    render_daily_central_report,
)


def test_daily_central_report_shows_title_and_source_link_for_each_top_item() -> None:
    brief = {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE", "IT"],
        "today_snapshot": {
            "actionable_now_count": 1,
            "market_watch_count": 1,
            "fabric_candidate_count": 1,
            "fabric_ai_status": "SUCCESS",
        },
        "top_actionable_opportunity": {
            "headline": "Current Norwegian clothing stock",
            "source_urls": ["https://example.test/opportunity"],
        },
        "top_market_signal": {
            "headline": "German retailer liquidation signal",
            "source_urls": ["https://register.example/company"],
        },
        "top_fabric_supplier": {
            "source_name": "Fabric House",
            "title": "Italian deadstock fabrics",
            "source_url": "https://fabric-house.example/item",
            "ai_review_priority": "HIGH",
        },
        "primary_human_action": {
            "action_type": "REVIEW_TOP_ACTIONABLE_OPPORTUNITY",
            "target": "Current Norwegian clothing stock",
            "reason": "Current commercial opportunity comes first.",
        },
    }

    text = render_daily_central_report(brief)

    assert "العنوان: Current Norwegian clothing stock" in text
    assert "الرابط: https://example.test/opportunity" in text
    assert "العنوان: German retailer liquidation signal" in text
    assert "الرابط: https://register.example/company" in text
    assert "العنوان: Fabric House — Italian deadstock fabrics" in text
    assert "الرابط: https://fabric-house.example/item" in text
    assert "AI: HIGH" in text
