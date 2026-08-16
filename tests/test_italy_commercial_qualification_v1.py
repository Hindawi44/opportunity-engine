from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.italy_commercial_qualification import (
    ENGINE_VERSION,
    run_italy_commercial_qualification,
)


NOW = datetime(2026, 8, 16, 13, 35, tzinfo=timezone.utc)


def _verified_row(**overrides) -> dict:
    row = {
        "verification_id": "italy-exact-lot:aurora-1",
        "case_id": "persistent-entity-case:it:aurora-moda",
        "case_title": "Aurora Moda S.r.l",
        "title": "Aurora Moda S.r.l. - Lotto abbigliamento",
        "source_url": "https://aste.example.it/aurora-lotto-800-capi",
        "canonical_source_url": "https://aste.example.it/aurora-lotto-800-capi",
        "source_page_verified": True,
        "entity_link_verified": True,
        "exact_lot_evidence": True,
        "sale_status": "ACTIVE",
        "commercial_lead_verified": True,
        "source_page_verification_status": "VERIFIED_ACTIVE_EXACT_LOT_LEAD",
        "clothing_terms": ["abbigliamento"],
        "quantity": 800,
        "source_price_eur": 3500.0,
        "currency": "EUR",
        "sale_deadline_text": "20/08/2026 alle 15:00",
        "location": "Milano",
        "response_sha256": "fixture-sha",
        "promotion_to_opportunity_allowed": False,
    }
    row.update(overrides)
    return row


def _report(*rows: dict) -> dict:
    return {
        "engine_version": "ITALY_EXACT_LOT_VERIFICATION_V1",
        "verifications": list(rows),
    }


def test_verified_active_lot_derives_only_exact_source_unit_economics() -> None:
    report = run_italy_commercial_qualification(
        _report(_verified_row()),
        observed_at=NOW,
    )

    assert report["engine_version"] == ENGINE_VERSION
    assert report["status"] == "SUCCESS"
    assert report["verified_active_exact_lot_input_count"] == 1
    assert report["source_unit_economics_verified_count"] == 1
    assert report["financial_decision_ready_count"] == 0

    row = report["qualifications"][0]
    assert row["qualification_state"] == "SOURCE_UNIT_ECONOMICS_VERIFIED"
    assert row["inventory_category"] == "CLOTHING"
    assert row["source_facts"]["quantity"] == 800
    assert row["source_facts"]["source_total_price_eur"] == 3500.0
    assert row["source_facts"]["source_unit_price_eur"] == 4.375
    assert row["derived_facts"]["source_unit_price_eur"] == 4.375
    assert row["derived_facts"]["estimated"] is False
    assert row["ready_for_market_comparables"] is True
    assert row["ready_for_logistics_evidence"] is True
    assert row["ready_for_financial_decision"] is False
    assert row["financial_decision"] is None
    assert row["profit_nok"] is None
    assert row["roi"] is None
    assert row["maximum_bid"] is None
    assert row["fx_rate_assumed"] is False
    assert row["shipping_cost_assumed"] is False
    assert row["resale_value_assumed"] is False
    assert "verified EUR/NOK FX observation" in row["missing_decision_evidence"]
    assert "verified transport or pickup cost NOK" in row["missing_decision_evidence"]
    assert "at least 3 verified market comparables" in row["missing_decision_evidence"]
    assert row["promotion_to_opportunity_allowed"] is False
    assert row["top5_eligible"] is False
    assert row["analysis_eligible"] is False
    assert row["automatic_contact"] is False
    assert row["automatic_bid"] is False
    assert row["automatic_reservation"] is False
    assert row["automatic_purchase"] is False
    assert row["automatic_payment"] is False


def test_missing_quantity_or_price_never_creates_guessed_unit_economics() -> None:
    no_quantity = _verified_row(
        verification_id="italy-exact-lot:no-qty",
        quantity=None,
    )
    no_price = _verified_row(
        verification_id="italy-exact-lot:no-price",
        source_price_eur=None,
        currency=None,
    )

    report = run_italy_commercial_qualification(
        _report(no_quantity, no_price),
        observed_at=NOW,
    )

    assert report["qualification_count"] == 2
    assert report["source_unit_economics_verified_count"] == 0
    assert all(
        row["qualification_state"] == "SOURCE_ECONOMICS_INCOMPLETE"
        for row in report["qualifications"]
    )
    assert all(
        row["source_facts"]["source_unit_price_eur"] is None
        for row in report["qualifications"]
    )
    assert "source quantity" in report["qualifications"][0]["missing_source_facts"]
    assert "source price EUR" in report["qualifications"][1]["missing_source_facts"]
    assert report["financial_decision_ready_count"] == 0


def test_unverified_ended_or_entity_mismatched_rows_never_enter_qualification() -> None:
    ended = _verified_row(
        verification_id="italy-exact-lot:ended",
        sale_status="ENDED",
        commercial_lead_verified=False,
        source_page_verification_status="SOURCE_PAGE_VERIFIED_ENDED_LOT",
    )
    mismatch = _verified_row(
        verification_id="italy-exact-lot:mismatch",
        entity_link_verified=False,
        commercial_lead_verified=False,
        source_page_verification_status="SOURCE_PAGE_VERIFIED_ENTITY_NOT_CONFIRMED",
    )
    search_only = _verified_row(
        verification_id="italy-exact-lot:search-only",
        source_page_verified=False,
        commercial_lead_verified=False,
        source_page_verification_status="NOT_ATTEMPTED",
    )

    report = run_italy_commercial_qualification(
        _report(ended, mismatch, search_only),
        observed_at=NOW,
    )

    assert report["status"] == "VALID_ZERO_NO_VERIFIED_ACTIVE_EXACT_LOTS"
    assert report["input_exact_lot_row_count"] == 3
    assert report["qualification_count"] == 0
    assert report["qualifications"] == []


def test_bridal_inventory_keeps_distinct_category() -> None:
    report = run_italy_commercial_qualification(
        _report(
            _verified_row(
                verification_id="italy-exact-lot:bridal",
                clothing_terms=["abiti da sposa", "abbigliamento"],
            )
        ),
        observed_at=NOW,
    )

    assert report["qualifications"][0]["inventory_category"] == "BRIDAL"


def test_location_missing_blocks_logistics_readiness_without_guessing() -> None:
    report = run_italy_commercial_qualification(
        _report(_verified_row(location=None)),
        observed_at=NOW,
    )

    row = report["qualifications"][0]
    assert row["ready_for_logistics_evidence"] is False
    assert "source location" in row["missing_source_facts"]
    assert row["shipping_cost_assumed"] is False


def test_valid_zero_exact_lot_report_is_clean_and_safe() -> None:
    report = run_italy_commercial_qualification(
        {"engine_version": "ITALY_EXACT_LOT_VERIFICATION_V1", "verifications": []},
        observed_at=NOW,
    )

    assert report["status"] == "VALID_ZERO_NO_EXACT_LOT_ROWS"
    assert report["qualification_count"] == 0
    assert report["financial_decision_ready_count"] == 0
    assert report["missing_values_are_never_estimated"] is True
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["top5_eligible"] is False
    assert report["analysis_eligible"] is False
    assert report["canonical_market_coverage_unchanged"] == ["NO", "SE", "DE"]
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_reservation"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False
