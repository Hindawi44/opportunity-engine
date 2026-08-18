from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery import germany_clothing_inventory as germany_discovery
from opportunity_engine.discovery.clothing_inventory_search import PageVerification
from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    _apply_canonical_lifecycle,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    build_unified_opportunity_report,
)


SEN_SEN_URL = (
    "https://sen-sen.de/php/o7580-1_Textilien-Warenbestand_aus_Insolvenz&subof=2."
    "?ScrollNumber=0&auktion=3590&auktionflag=0&searchstring=%2A&snumber=2"
)


def test_sen_sen_exact_detail_keeps_one_identity_through_lifecycle_handoff(
    monkeypatch,
) -> None:
    base = PageVerification(
        url=SEN_SEN_URL,
        title="Sen & Sen: 1 Textilien-Warenbestand aus Insolvenz",
        text="Komplett-Verkauf bevorzugt.",
        bounded_context=None,
        listing_status="UNKNOWN",
        page_role="ARTICLE_OR_INFO",
        opportunity_identity=None,
        identity_stable=False,
        verified=True,
    )
    monkeypatch.setattr(germany_discovery, "verify_public_page", lambda url: base)

    verified = germany_discovery.verify_germany_public_page(SEN_SEN_URL)

    assert verified.opportunity_identity == "sen-sen:o7580"
    assert verified.identity_stable is True
    assert verified.page_role == "ITEM_LISTING"
    assert verified.listing_status == "UNKNOWN"
    assert verified.clothing_inventory_evidence is True
    assert verified.sale_evidence is True
    assert verified.event_scenario == "COMPANY_BANKRUPTCY"

    candidate = {
        "title": base.title,
        "scenario": verified.event_scenario,
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": "verified Sen & Sen inventory detail has unknown active/ended status",
        "page_role": verified.page_role,
        "opportunity_identity": verified.opportunity_identity,
        "identity_stable": verified.identity_stable,
        "top5_eligible": False,
        "analysis_eligible": False,
        "discovery_score": 55,
        "discovery_band": "REVIEW",
        "location": None,
        "company_name": None,
        "inventory_type": verified.inventory_type,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "published_at": None,
        "listing_status": verified.listing_status,
        "source_urls": [SEN_SEN_URL],
        "source_providers": ["Sen & Sen"],
        "evidence_signals": ["textilien", "warenbestand", "insolvenz", "komplett-verkauf"],
        "missing_information": ["active/ended status"],
        "verification": [
            {
                "url": SEN_SEN_URL,
                "title": base.title,
                "verified": True,
                "listing_status": verified.listing_status,
                "page_role": verified.page_role,
                "event_scenario": verified.event_scenario,
            }
        ],
    }
    unified = build_unified_opportunity_report(
        {"all_discovered_candidates": [candidate]},
        generated_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        market_code="DE",
        currency="EUR",
        domain="CLOTHING_INVENTORY",
    )

    assert unified["record_count"] == 1
    assert unified["records"][0]["opportunity_id"] == "sen-sen:o7580"
    assert unified["records"][0]["workflow_status"] == "REQUIRES_VERIFICATION"

    checkpoint_records = [dict(candidate)]
    _apply_canonical_lifecycle(
        checkpoint_records,
        source_name="Sen & Sen",
        unified=unified,
    )

    assert checkpoint_records[0]["_canonical_lifecycle_present"] is True
    assert checkpoint_records[0]["workflow_status"] == "REQUIRES_VERIFICATION"
