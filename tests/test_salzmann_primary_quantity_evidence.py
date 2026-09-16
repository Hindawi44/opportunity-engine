"""Source-specific regression: recommendations must never contaminate quantity."""

from opportunity_engine.discovery.pending_evidence_enrichment import (
    PRICE_BLOCKER,
    QUANTITY_BLOCKER,
    build_pending_evidence_enrichment,
)


URL = "https://salzmann-restwaren.de/product/damen-kleidung-jacken-roecke-hosen-blusen-mix/"


def _evidence(*, labelled="Verfügbare Menge 476", counted="476 Stk"):
    return {
        "item_specific_url_evidence": True,
        "domain_evidence": True,
        "source_native_price_candidates": ["3,45 €", "2,88 €", "1,21 €"],
        "source_native_quantity_candidates": [
            labelled, counted, "32 Stk", "28489 Stk", "2273 Stk",
        ],
        "source_native_price_basis_candidates": [],
        "source_native_condition_candidates": [],
        "source_native_fulfilment_candidates": [],
        "source_native_seller_identity_candidates": [],
    }


def test_primary_stock_count_is_proven_but_related_prices_are_not() -> None:
    result = build_pending_evidence_enrichment(market="DE", url=URL, evidence=_evidence())
    assert result["validation_source"] == "SALZMANN_PRIMARY_AVAILABILITY_ANCHOR_V1"
    assert result["resolved_blockers"] == [QUANTITY_BLOCKER]
    assert PRICE_BLOCKER not in result["resolved_blockers"]
    assert result["validated_price"] is None
    assert result["validated_quantity"]["amount"] == 476
    assert result["validated_quantity"]["unit"] == "COUNT"
    assert result["validated_quantity"]["lot_size_proven"] is False
    assert result["price_basis"] == "UNKNOWN_STARTING_FROM_PRICE"
    assert result["qualification_evidence"] is False
    assert result["automatic_purchase"] is False


def test_mismatched_or_missing_primary_anchor_fails_closed() -> None:
    for first, second in [
        ("Verfügbare Menge 476", "32 Stk"),
        ("Verfügbare Menge 476", "476 Kg"),
        ("Menge: 476", "476 Stk"),
    ]:
        result = build_pending_evidence_enrichment(
            market="DE", url=URL, evidence=_evidence(labelled=first, counted=second)
        )
        assert result["resolved_blockers"] == []
        assert result["validated_quantity"] is None


def test_domain_market_path_and_primary_page_gates_fail_closed() -> None:
    for market, url in [
        ("DE", "https://evil-salzmann-restwaren.de/product/item/"),
        ("DE", "https://salzmann-restwaren.de/product-category/kleidung/"),
        ("IT", URL),
        ("DE", "http://salzmann-restwaren.de/product/item/"),
    ]:
        result = build_pending_evidence_enrichment(
            market=market, url=url, evidence=_evidence()
        )
        assert result["resolved_blockers"] == []
    evidence = _evidence()
    evidence["domain_evidence"] = False
    assert build_pending_evidence_enrichment(
        market="DE", url=URL, evidence=evidence
    )["resolved_blockers"] == []


def test_mass_stock_is_not_wrongly_cast_to_item_count() -> None:
    result = build_pending_evidence_enrichment(
        market="DE", url=URL,
        evidence=_evidence(labelled="Verfügbare Menge 2361", counted="2361 Kg"),
    )
    assert result["validated_quantity"] is None
    assert result["resolved_blockers"] == []
