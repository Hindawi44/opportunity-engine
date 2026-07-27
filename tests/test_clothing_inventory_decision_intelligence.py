from datetime import datetime, timezone

from scripts.run_clothing_inventory_single_case import (
    build_final_report,
    enrich_with_comparables,
    enrich_with_costs,
    enrich_with_decision,
    build_operator_summary,
)


def _verified_comparables(prices: tuple[int, int, int]) -> dict[str, object]:
    sources = (
        (
            "https://www.finn.no/bap/forsale/ad.html?finnkode=300001",
            "FINN.no",
        ),
        (
            "https://www.auksjonen.no/auksjoner/clothing-inventory/300002",
            "Auksjonen.no",
        ),
        (
            "https://arbeidsklaer.no/produkter/clothing-inventory-300003",
            "Arbeidsklaer.no",
        ),
    )
    return {
        "comparables": [
            {
                "title": f"Verified clothing inventory comparable {index}",
                "url": url,
                "price_nok": price,
                "source_name": source_name,
                "observed_at": f"2026-07-26T12:0{index}:00Z",
                "similarity_score": 0.90 - (index * 0.03),
                "verified": True,
            }
            for index, (price, (url, source_name)) in enumerate(
                zip(prices, sources, strict=True),
                start=1,
            )
        ]
    }


def _verified_costs() -> dict[str, object]:
    rows = (
        ("auction_price", 200, "https://www.auksjonen.no/auksjoner/arbeidsjakke/300001", False),
        ("auction_fee", 40, "https://www.auksjonen.no/kundeservice/vilkar", False),
        ("vat", 60, "https://www.auksjonen.no/kundeservice/vilkar", False),
        ("transport", 350, "https://www.bring.no/tjenester/pakker-og-gods", False),
        ("dismantling", 0, "https://www.auksjonen.no/auksjoner/arbeidsjakke/300001", True),
        ("storage", 0, "https://namsos.kommune.no/naering", True),
    )
    return {
        "costs": [
            {
                "component": component,
                "amount_nok": amount,
                "currency": "NOK",
                "source_url": url,
                "source_name": "Verified cost source",
                "observed_at": f"2026-07-26T13:0{index}:00Z",
                "basis": f"Published or written {component} evidence",
                "zero_cost_confirmed": zero,
                "verified": True,
            }
            for index, (component, amount, url, zero) in enumerate(rows, start=1)
        ]
    }


def test_incomplete_case_uses_existing_policy_and_remains_watch() -> None:
    report = enrich_with_decision(build_final_report())

    assert report["decision_invoked"] is True
    assert report["final_decision"] == "WATCH"
    assert report["decision_intelligence"]["decision_confidence"] == "LOW"
    assert report["requires_human_approval"] is False
    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_payment"] is False


def test_complete_strong_case_reaches_buy_review_with_human_approval() -> None:
    report = enrich_with_comparables(
        build_final_report(),
        _verified_comparables((30000, 32000, 34000)),
        now=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    report = enrich_with_costs(report, _verified_costs())
    report = enrich_with_decision(report)

    assert report["market_comparables"]["accepted_count"] == 3
    assert report["final_outcome"] == "ANALYSIS_READY"
    assert report["financial_integration"]["decision_gate"] == (
        "READY_FOR_FINANCIAL_REVIEW"
    )
    assert report["opportunity_score"] >= 75
    assert report["final_decision"] == "BUY_REVIEW"
    assert report["final_decision_ar"] == "مراجعة للشراء"
    assert report["maximum_safe_bid_nok"] is not None
    assert report["requires_human_approval"] is True
    assert report["automatic_purchase_decision"] is False
    assert report["automatic_bid"] is False

    summary = build_operator_summary(report)
    assert "Final decision: BUY_REVIEW" in summary
    assert "Human approval required: True" in summary
    assert "Automatic purchase/bid/contact/payment: false" in summary
