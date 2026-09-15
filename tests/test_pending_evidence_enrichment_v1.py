from types import SimpleNamespace

from opportunity_engine.discovery.pending_evidence_enrichment import (
    CONDITION_BLOCKER,
    FULFILMENT_BLOCKER,
    PRICE_BLOCKER,
    QUANTITY_BLOCKER,
    SELLER_BLOCKER,
    build_pending_evidence_enrichment,
)
from scripts.run_pending_opportunity_investigation import (
    investigate_pending_opportunities,
    reconcile_investigation_lifecycle,
    select_pending_opportunities,
)


def _record(identity: str, *, url: str, missing_evidence: list[str], score: int = 1):
    return {
        "opportunity_identity": identity,
        "title": f"Stock lot {identity}",
        "market_code": "IT" if "stockitaly24" in url else "DE",
        "source_url": url,
        "listing_status": "ACTIVE",
        "workflow_status": "REQUIRES_VERIFICATION",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "analysis_eligible": False,
        "discovery_score": score,
        "missing_evidence": missing_evidence,
    }


def _exact_stockitaly_page(url: str):
    return SimpleNamespace(
        ok=True,
        title="HUF stock abbigliamento uomo 80 pezzi",
        text="Stock abbigliamento in vendita. 80 pezzi. 10.50 EUR per pezzo.",
        raw_html="",
        final_url=url,
        status_code=200,
        error=None,
    )


def test_stockitaly_product_url_validates_price_and_quantity_only() -> None:
    url = (
        "https://stockitaly24.com/products/"
        "10-50-al-pezzo-huf-stock-abbigliamento-uomo-80-pezzi-multistagione-rif-6286"
    )
    result = build_pending_evidence_enrichment(
        market="IT",
        url=url,
        evidence={
            "source_native_price_candidates": ["€ 10,50", "10,50 EUR"],
            "source_native_quantity_candidates": ["80 pezzi"],
            "source_native_condition_candidates": [],
            "source_native_fulfilment_candidates": [],
            "source_native_seller_identity_candidates": [],
        },
    )

    assert result["status"] == "VALIDATED_FIELDS"
    assert result["validation_source"] == "STOCKITALY24_PRODUCT_URL"
    assert result["validated_price"]["amount_decimal"] == "10.50"
    assert result["validated_price"]["currency"] == "EUR"
    assert result["validated_quantity"] == {"amount": 80, "unit": "COUNT"}
    assert result["price_basis"] == "PER_ITEM"
    assert result["resolved_blockers"] == [PRICE_BLOCKER, QUANTITY_BLOCKER]
    assert result["field_statuses"]["condition"] == "MISSING"
    assert result["qualification_evidence"] is False
    assert result["automatic_purchase"] is False


def test_ambiguous_generic_values_and_raw_commercial_snippets_fail_closed() -> None:
    result = build_pending_evidence_enrichment(
        market="DE",
        url="https://example.test/product/lot-1",
        evidence={
            "source_native_price_candidates": ["10 EUR", "12 EUR"],
            "source_native_price_basis_candidates": ["pro Stück"],
            "source_native_quantity_candidates": ["20 Stück"],
            "source_native_condition_candidates": ["Zustand: Neu"],
            "source_native_fulfilment_candidates": ["Versand: möglich"],
            "source_native_seller_identity_candidates": ["Firma: Example GmbH"],
        },
    )

    assert result["status"] == "NO_VALIDATED_FIELDS"
    assert result["resolved_blockers"] == []
    assert result["field_statuses"]["condition"] == "CAPTURED_UNVALIDATED"
    assert result["field_statuses"]["pickup_or_shipping_terms"] == "CAPTURED_UNVALIDATED"
    assert result["field_statuses"]["seller_or_company_identity"] == "CAPTURED_UNVALIDATED"


def test_durable_exact_lot_with_enrichment_blockers_is_prioritized() -> None:
    old_url = (
        "https://stockitaly24.com/products/"
        "10-50-al-pezzo-huf-stock-abbigliamento-uomo-80-pezzi-multistagione-rif-6286"
    )
    report = {
        "deduplicated_opportunities": [
            _record(
                "generic-new",
                url="https://example.test/product/generic-new",
                missing_evidence=[CONDITION_BLOCKER],
                score=100,
            ),
            _record(
                "verified-old",
                url=old_url,
                missing_evidence=[PRICE_BLOCKER, QUANTITY_BLOCKER, CONDITION_BLOCKER],
                score=1,
            ),
        ]
    }
    state = {
        "records": {
            "verified-old": {
                "attempt_count": 1,
                "last_investigated_at": "2026-09-15T00:00:00+00:00",
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
            }
        }
    }

    selected = select_pending_opportunities(report, limit=1, investigation_state=state)

    assert [item["opportunity_identity"] for item in selected] == ["verified-old"]


def test_investigation_persists_validated_stockitaly_enrichment() -> None:
    url = (
        "https://stockitaly24.com/products/"
        "10-50-al-pezzo-huf-stock-abbigliamento-uomo-80-pezzi-multistagione-rif-6286"
    )
    report = {
        "deduplicated_opportunities": [
            _record(
                "verified-old",
                url=url,
                missing_evidence=[PRICE_BLOCKER, QUANTITY_BLOCKER, CONDITION_BLOCKER],
            )
        ]
    }
    previous_state = {
        "records": {
            "verified-old": {
                "attempt_count": 1,
                "last_investigated_at": "2026-09-15T00:00:00+00:00",
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
            }
        }
    }

    result = investigate_pending_opportunities(
        report,
        limit=1,
        page_fetcher=_exact_stockitaly_page,
        investigation_state=previous_state,
    )

    state = result["investigation_state"]["records"]["verified-old"]
    assert result["evidence_enrichment_targetable_pending_count"] == 1
    assert result["selected_evidence_enrichment_targetable_count"] == 1
    assert state["last_enrichment"]["resolved_blockers"] == [
        PRICE_BLOCKER,
        QUANTITY_BLOCKER,
    ]
    assert result["current_run_enrichment_resolved_counts"] == {
        PRICE_BLOCKER: 1,
        QUANTITY_BLOCKER: 1,
    }


def test_reconciliation_clears_only_validated_price_and_quantity_blockers() -> None:
    identity = "stockitaly:6286"
    url = (
        "https://stockitaly24.com/products/"
        "10-50-al-pezzo-huf-stock-abbigliamento-uomo-80-pezzi-multistagione-rif-6286"
    )
    report = {
        "deduplicated_opportunities": [
            _record(
                identity,
                url=url,
                missing_evidence=[
                    CONDITION_BLOCKER,
                    PRICE_BLOCKER,
                    QUANTITY_BLOCKER,
                    FULFILMENT_BLOCKER,
                    SELLER_BLOCKER,
                ],
            )
        ],
        "analysis_eligible_count": 0,
    }
    enrichment = build_pending_evidence_enrichment(
        market="IT",
        url=url,
        evidence={},
    )
    state = {
        "records": {
            identity: {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_investigated_at": "2026-09-15T00:00:00+00:00",
                "source_url": url,
                "last_evidence": {"item_specific_url_evidence": True},
                "last_enrichment": enrichment,
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(
        report,
        state,
        current_run_enriched_ids=[identity],
    )
    item = reconciled["deduplicated_opportunities"][0]

    assert item["missing_evidence"] == [
        CONDITION_BLOCKER,
        FULFILMENT_BLOCKER,
        SELLER_BLOCKER,
    ]
    assert item["workflow_status"] == "REQUIRES_VERIFICATION"
    assert item["analysis_eligible"] is False
    assert meta["evidence_enrichment_applied_record_count"] == 1
    assert meta["evidence_enrichment_blocker_cleared_count"] == 2
    assert meta["evidence_enrichment_resolved_counts"] == {
        PRICE_BLOCKER: 1,
        QUANTITY_BLOCKER: 1,
    }
    assert meta["promoted_to_active_count"] == 0
    assert meta["commercial_decision_created"] is False
    assert meta["automatic_contact"] is False
    assert meta["automatic_bid"] is False
    assert meta["automatic_purchase"] is False
    assert meta["automatic_payment"] is False


def test_enrichment_may_promote_only_when_it_clears_the_final_blockers() -> None:
    identity = "stockitaly:final"
    url = (
        "https://stockitaly24.com/products/"
        "7-00-al-pezzo-emc-stock-abbigliamento-bambini-101-pezzi-p-e-rif-6285"
    )
    report = {
        "deduplicated_opportunities": [
            _record(
                identity,
                url=url,
                missing_evidence=[PRICE_BLOCKER, QUANTITY_BLOCKER],
            )
        ],
        "analysis_eligible_count": 0,
    }
    state = {
        "records": {
            identity: {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_enrichment": build_pending_evidence_enrichment(
                    market="IT", url=url, evidence={}
                ),
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(
        report,
        state,
        current_run_enriched_ids=[identity],
    )
    item = reconciled["deduplicated_opportunities"][0]

    assert item["missing_evidence"] == []
    assert item["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert item["analysis_eligible"] is True
    assert meta["promoted_to_active_count"] == 1
    assert meta["current_run_promoted_to_active_count"] == 1
    assert reconciled["commercially_qualified_count"] == 0
