from __future__ import annotations

from opportunity_engine.discovery import germany_clothing_inventory as germany_discovery
from opportunity_engine.discovery.auksjonen_exact_item_verification import (
    parse_auksjonen_item_page,
)
from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    render_daily_central_report,
)
from opportunity_engine.discovery.clothing_inventory_search import (
    ARTICLE_OR_INFO,
    ITEM_LISTING,
    UNKNOWN,
    PageVerification,
)


SEN_SEN_URL = (
    "https://sen-sen.de/php/o7580-1_Textilien-Warenbestand_aus_Insolvenz&subof=2."
    "?ScrollNumber=0&auktion=3590&auktionflag=0&searchstring=%2A&snumber=2"
)


def test_auksjonen_condition_detects_new_stock_in_original_packaging() -> None:
    html = """
    <html><body>
      <h1>280 stk GSA jakke oransje (art GSA11030) str 56/60</h1>
      <p>Stort samlet parti med 280 stk nye/uåpnede GSA arbeidsjakker.</p>
      <p>Tilstand: nye plagg i original emballasje, palletert</p>
    </body></html>
    """

    parsed = parse_auksjonen_item_page(html)

    assert parsed["condition"] == "NEW_OR_UNUSED"


def test_sen_sen_inventory_detail_is_preserved_as_listing_when_activity_unknown(
    monkeypatch,
) -> None:
    base = PageVerification(
        url=SEN_SEN_URL,
        title="Sen & Sen: 1 Textilien-Warenbestand aus Insolvenz",
        text="Komplett-Verkauf bevorzugt. Weitere Infos und Bilder auf Anfrage.",
        bounded_context=None,
        listing_status=UNKNOWN,
        page_role=ARTICLE_OR_INFO,
        opportunity_identity=None,
        identity_stable=False,
        verified=True,
    )
    monkeypatch.setattr(germany_discovery, "verify_public_page", lambda url: base)

    verified = germany_discovery.verify_germany_public_page(SEN_SEN_URL)

    assert verified.opportunity_identity == "sen-sen:o7580"
    assert verified.identity_stable is True
    assert verified.page_role == ITEM_LISTING
    assert verified.clothing_inventory_evidence is True
    assert verified.sale_evidence is True
    assert verified.event_scenario == "COMPANY_BANKRUPTCY"
    assert verified.listing_status == UNKNOWN


def test_final_report_hides_fabric_and_early_signal_noise_when_no_useful_opportunity() -> None:
    brief = {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE", "IT"],
        "today_snapshot": {
            "actionable_now_count": 7,
            "market_watch_count": 88,
            "fabric_candidate_count": 33,
            "fabric_ai_status": "SKIPPED_NO_API_KEY",
        },
        "top_actionable_opportunity": None,
        "top_market_signal": {
            "headline": "Brautkleider kaufen | Outlet & Second Hand",
            "source_urls": ["https://example.test/bridal-signal"],
        },
        "top_fabric_supplier": {
            "source_name": "Bridal Fabrics",
            "title": "Organza fabrics",
            "source_url": "https://example.test/bridal-fabrics",
        },
        "primary_human_action": {
            "action_type": "VERIFY_TOP_FABRIC_SUPPLIER",
            "target": "Bridal Fabrics",
            "reason": "Synthetic report-noise fixture.",
        },
    }

    text = render_daily_central_report(brief)

    assert "0 فرص مفيدة اليوم." in text
    assert "Bridal Fabrics" not in text
    assert "Brautkleider" not in text
    assert "أفضل مورد أقمشة" not in text
    assert "أهم إشارة سوق" not in text


def test_final_report_uses_simple_useful_opportunity_fields() -> None:
    brief = {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE"],
        "today_snapshot": {},
        "top_actionable_opportunity": {
            "headline": "280 stk nye arbeidsjakker",
            "source_name": "Auksjonen",
            "market_code": "NO",
            "location": "Oslo",
            "price_nok": 4200,
            "quantity": 280,
            "recommended_next_action": "Strong verified inventory lot",
            "source_urls": ["https://example.test/lot"],
        },
        "top_market_signal": {"headline": "Noise"},
        "top_fabric_supplier": {"source_name": "Bridal Fabrics"},
        "primary_human_action": {},
    }

    text = render_daily_central_report(brief)

    assert "العنوان: 280 stk nye arbeidsjakker" in text
    assert "المصدر: Auksjonen" in text
    assert "البلد/الموقع: NO | Oslo" in text
    assert "السعر: 4200 NOK" in text
    assert "الكمية/المحتوى: 280" in text
    assert "لماذا مفيدة: Strong verified inventory lot" in text
    assert "الرابط: https://example.test/lot" in text
    assert "Bridal Fabrics" not in text
    assert "Noise" not in text
