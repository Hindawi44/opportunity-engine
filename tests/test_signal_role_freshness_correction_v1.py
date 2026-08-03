from __future__ import annotations

from opportunity_engine.discovery.signal_role_freshness_correction import (
    correct_signal_roles_and_freshness,
    render_corrected_market_bulletin,
)


def _signal(
    signal_id: str,
    *,
    signal_type: str,
    title: str,
    related_opportunity_id: str | None = None,
    source: str = "Auksjonen.no",
    country: str = "NO",
    location: str | None = "Døvleveien 23, 3170, Sem",
    status: str = "ACTIVE",
    company_name: str | None = None,
) -> dict:
    return {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "value": title,
        "source": source,
        "observed_at": "2026-08-03T16:29:29Z",
        "confidence": 0.8,
        "source_country": country,
        "source_url": f"https://example.test/{signal_id}",
        "title": title,
        "company_name": company_name,
        "seller_name": None,
        "location": location,
        "first_observed_at": "2026-08-03T16:29:29Z",
        "latest_observed_at": "2026-08-03T16:29:29Z",
        "event_date": None,
        "evidence": [],
        "related_opportunity_id": related_opportunity_id,
        "status": status,
        "metadata": {
            "workflow_status": "REQUIRES_VERIFICATION"
            if related_opportunity_id
            else "EARLY_SIGNAL",
            "listing_status": "ACTIVE",
        },
    }


def _opportunity(identity: str, title: str) -> dict:
    return {
        "opportunity_identity": identity,
        "title": title,
        "market_code": "NO",
        "source_name": None,
        "source_url": None,
        "workflow_status": "REQUIRES_VERIFICATION",
        "listing_status": "ACTIVE",
        "discovery_score": 70,
        "location": None,
        "quantity": None,
    }


def test_related_item_listings_and_old_auction_are_not_early_signals() -> None:
    listing = _signal(
        "opportunity-signal:lot-1",
        signal_type="WAREHOUSE_SURPLUS",
        title="10 stk GSA multinorm arbeidsplagg",
        related_opportunity_id="lot-1",
    )
    old_auction = _signal(
        "auction-event:2019-cabrini",
        signal_type="AUCTION_EVENT",
        title="Auktion - 2019 Versteigerung Cabrini GmbH",
        source="Riegermann",
        country="DE",
        location="Langenlonsheim",
    )
    closure = _signal(
        "closure:no:shop",
        signal_type="BUSINESS_CLOSURE",
        title="Clothing shop closing",
        related_opportunity_id=None,
        company_name="Example AS",
    )
    brief = {
        "generated_at": "2026-08-03T16:29:29+00:00",
        "early_signals_to_watch": [listing, old_auction, closure],
        "current_direct_opportunities": [_opportunity("lot-1", listing["title"])],
        "selected_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": "lot-1",
        },
        "counts": {
            "new_signals_today": 0,
            "changed_signals_since_previous_checkpoint": 1,
            "early_signals_to_watch": 3,
            "current_direct_opportunities": 1,
            "unavailable_or_failed_sources": 0,
        },
    }
    persistence = {"current_signals": [listing, old_auction, closure]}

    corrected = correct_signal_roles_and_freshness(brief, persistence)

    assert [item["signal_id"] for item in corrected["early_signals_to_watch"]] == [
        "closure:no:shop"
    ]
    assert corrected["counts"]["early_signals_to_watch"] == 1
    assert corrected["counts"]["current_direct_opportunities"] == 1


def test_same_source_and_location_produce_one_related_lots_action() -> None:
    signals = [
        _signal(
            f"opportunity-signal:lot-{index}",
            signal_type="WAREHOUSE_SURPLUS",
            title=title,
            related_opportunity_id=f"lot-{index}",
        )
        for index, title in enumerate(
            (
                "10 stk GSA multinorm arbeidsplagg",
                "8 stk Blåkläder T-skjorter",
                "Parti Björnkläder arbeidsklær",
            ),
            start=1,
        )
    ]
    brief = {
        "generated_at": "2026-08-03T16:29:29+00:00",
        "early_signals_to_watch": list(signals),
        "current_direct_opportunities": [
            _opportunity(f"lot-{index}", signal["title"])
            for index, signal in enumerate(signals, start=1)
        ],
        "selected_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": "lot-1",
        },
        "counts": {
            "new_signals_today": 0,
            "changed_signals_since_previous_checkpoint": 0,
            "early_signals_to_watch": 3,
            "current_direct_opportunities": 3,
            "unavailable_or_failed_sources": 0,
        },
    }
    persistence = {"current_signals": signals}

    corrected = correct_signal_roles_and_freshness(brief, persistence)
    summary = corrected["phone_readable_summary"]
    text = render_corrected_market_bulletin(corrected)

    assert corrected["counts"]["early_signals_to_watch"] == 0
    assert summary["selected_action_code"] == "REVIEW_RELATED_LOTS"
    assert len(summary["related_lots"]) == 3
    assert corrected["selected_human_action"]["related_opportunity_ids"] == [
        "lot-1",
        "lot-2",
        "lot-3",
    ]
    assert summary["selected_opportunity"]["display_entity_ar"] == "غير معروفة"
    assert "دفعات مرتبطة في المصدر والموقع نفسيهما" in text
    assert "اسأل البائع عن بقية مخزون الملابس" in text
    assert "موثقة" not in text
    assert "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي" in text
