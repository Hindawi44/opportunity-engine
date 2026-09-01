from opportunity_engine.discovery.exa_shadow_page_verification import (
    EXACT_LOT_CANDIDATE,
    _classify_page,
)
from opportunity_engine.discovery.source_native_commercial_terms_capture import (
    CAPTURE_VERSION,
    capture_source_native_commercial_terms,
)


def test_capture_explicit_swedish_commercial_terms_without_interpretation():
    captured = capture_source_native_commercial_terms(
        """
        Skick: Nytt i originalförpackning
        Säljare: Example Wholesale AB
        Frakt: Köparen betalar frakt
        """
    )

    assert captured["version"] == CAPTURE_VERSION
    assert captured["condition_candidates"] == ["Skick: Nytt i originalförpackning"]
    assert captured["seller_identity_candidates"] == ["Säljare: Example Wholesale AB"]
    assert captured["fulfilment_candidates"] == ["Frakt: Köparen betalar frakt"]
    assert captured["capture_is_qualification_evidence"] is False
    assert captured["financial_analysis_ready"] is False
    assert captured["automatic_contact"] is False
    assert captured["automatic_purchase"] is False


def test_capture_accepts_explicit_company_number_as_identity_evidence():
    captured = capture_source_native_commercial_terms(
        "Organisationsnummer: 556123-4567"
    )

    assert captured["seller_identity_candidates"] == [
        "Organisationsnummer: 556123-4567"
    ]


def test_capture_fails_closed_on_generic_unlabeled_words():
    captured = capture_source_native_commercial_terms(
        "Vi hjälper säljare med shipping information och condition guides för kläder."
    )

    assert captured["condition_candidates"] == []
    assert captured["seller_identity_candidates"] == []
    assert captured["fulfilment_candidates"] == []


def test_exact_lot_classifier_emits_commercial_terms_capture_without_changing_gate():
    classification, evidence = _classify_page(
        title="Restparti kläder",
        text=(
            "Restparti kläder till salu. 14 000 kr. Kvantitet 140. "
            "Skick: Nytt. Säljare: Example Wholesale AB. "
            "Frakt: Köparen betalar frakt."
        ),
        url="https://example.se/restpartier/1/20/parti/2359",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["source_native_commercial_terms_capture_version"] == CAPTURE_VERSION
    assert evidence["source_native_condition_candidates"] == ["Skick: Nytt"]
    assert evidence["source_native_seller_identity_candidates"] == [
        "Säljare: Example Wholesale AB"
    ]
    assert evidence["source_native_fulfilment_candidates"] == [
        "Frakt: Köparen betalar frakt"
    ]
    assert evidence["source_native_commercial_terms_capture_is_qualification_evidence"] is False


def test_exact_lot_classifier_stays_exact_lot_when_commercial_terms_are_missing():
    classification, evidence = _classify_page(
        title="Restparti kläder",
        text="Restparti kläder till salu. 14 000 kr. Kvantitet 140.",
        url="https://example.se/restpartier/1/20/parti/2359",
    )

    assert classification == EXACT_LOT_CANDIDATE
    assert evidence["source_native_condition_candidates"] == []
    assert evidence["source_native_seller_identity_candidates"] == []
    assert evidence["source_native_fulfilment_candidates"] == []
