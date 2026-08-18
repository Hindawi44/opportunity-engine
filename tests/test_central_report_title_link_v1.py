from __future__ import annotations

from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    render_daily_central_report,
)


def test_daily_central_report_shows_only_useful_opportunity_fields() -> None:
    brief = {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE", "IT"],
        "top_actionable_opportunity": {
            "headline": "Current Norwegian clothing stock",
            "source_name": "Auksjonen.no",
            "source_country": "NO",
            "location": "Oslo",
            "quantity": 280,
            "price_nok": 4200,
            "why_useful": "Verified active inventory lot",
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
    }

    text = render_daily_central_report(brief)

    assert "العنوان: Current Norwegian clothing stock" in text
    assert "المصدر: Auksjonen.no" in text
    assert "البلد/الموقع: NO | Oslo" in text
    assert "السعر: 4200 NOK" in text
    assert "الكمية/المحتوى: 280" in text
    assert "لماذا مفيدة: Verified active inventory lot" in text
    assert "الرابط: https://example.test/opportunity" in text
    assert "German retailer liquidation signal" not in text
    assert "Fabric House" not in text
    assert "AI: HIGH" not in text


def test_daily_central_report_returns_truthful_zero_without_side_noise() -> None:
    text = render_daily_central_report(
        {
            "top_actionable_opportunity": None,
            "top_market_signal": {"headline": "Early signal noise"},
            "top_fabric_supplier": {"source_name": "Bridal Fabrics"},
        }
    )

    assert text == "0 فرص مفيدة اليوم.\n"
