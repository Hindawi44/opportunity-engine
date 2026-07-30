import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichmentCollector,
    build_official_estate_url,
    build_single_estate_endpoint,
    is_approved_single_estate_endpoint,
    normalize_single_estate_record,
    write_estate_manager_artifacts,
)

ESTATE_ORGNR = "938018014"


def menswear_record(**overrides):
    record = {
        "orgnr": ESTATE_ORGNR,
        "navn": "MENSWEAR NORGE AS KONKURSBO",
        "stiftelsesdato": "2026-07-01",
        "naeringskode": "46.420",
        "naeringsbeskrivelse": "Engroshandel med klær og skotøy",
        "kommune": "OSLO",
        "aktiv": 1,
        "debitor_navn": "MENSWEAR NORGE AS",
        "debitor_orgnr": "986425284",
        "bostyrer": "Adv. Henrik Schumann Sager",
        "adresse": "must not be retained",
    }
    record.update(overrides)
    return record


def test_single_estate_endpoint_is_exact_and_bounded():
    endpoint = build_single_estate_endpoint(ESTATE_ORGNR)
    assert endpoint == f"https://konkurs.app/api/konkursbo/{ESTATE_ORGNR}"
    assert is_approved_single_estate_endpoint(endpoint, estate_orgnr=ESTATE_ORGNR)
    assert not is_approved_single_estate_endpoint(
        "https://konkurs.app/api/konkursbo?size=100",
        estate_orgnr=ESTATE_ORGNR,
    )
    assert not is_approved_single_estate_endpoint(
        f"https://evil.example/api/konkursbo/{ESTATE_ORGNR}",
        estate_orgnr=ESTATE_ORGNR,
    )
    with pytest.raises(ValueError):
        build_single_estate_endpoint("bad")


def test_record_retains_only_company_identity_and_professional_role():
    enrichment = normalize_single_estate_record(
        menswear_record(),
        requested_estate_orgnr=ESTATE_ORGNR,
        captured_at="2026-07-30T10:00:00+00:00",
    )
    payload = enrichment.to_dict()

    assert payload["estate_orgnr"] == ESTATE_ORGNR
    assert payload["debtor_orgnr"] == "986425284"
    assert payload["estate_manager_name"] == "Adv. Henrik Schumann Sager"
    assert payload["estate_manager_identified"] is True
    assert payload["lead_stage"] == "ESTATE_MANAGER_IDENTIFIED"
    assert payload["professional_role_only"] is True
    assert payload["person_data_scope"] == "PUBLIC_PROFESSIONAL_ROLE_ONLY"
    assert payload["official_estate_url"] == build_official_estate_url(ESTATE_ORGNR)
    assert "address" not in payload
    assert "phone" not in payload
    assert "email" not in payload
    assert payload["public_sale_found"] is False
    assert payload["inventory_sale_verified"] is False
    assert payload["top5_eligible"] is False
    assert payload["analysis_eligible"] is False
    assert payload["automatic_contact"] is False


def test_collector_performs_one_selected_lookup():
    calls = []

    def fetch_json(url):
        calls.append(url)
        return menswear_record()

    enrichment = EstateManagerEnrichmentCollector(
        estate_orgnr=ESTATE_ORGNR,
        fetch_json=fetch_json,
    ).collect()

    assert calls == [build_single_estate_endpoint(ESTATE_ORGNR)]
    assert enrichment.debtor_name == "MENSWEAR NORGE AS"


def test_invalid_or_inactive_response_fails_closed():
    with pytest.raises(ValueError):
        normalize_single_estate_record(
            menswear_record(orgnr="938018015"),
            requested_estate_orgnr=ESTATE_ORGNR,
        )
    with pytest.raises(ValueError):
        normalize_single_estate_record(
            menswear_record(aktiv=0),
            requested_estate_orgnr=ESTATE_ORGNR,
        )
    with pytest.raises(ValueError):
        normalize_single_estate_record(
            menswear_record(debitor_orgnr="bad"),
            requested_estate_orgnr=ESTATE_ORGNR,
        )


def test_missing_manager_remains_reviewable_but_unidentified():
    enrichment = normalize_single_estate_record(
        menswear_record(bostyrer=None),
        requested_estate_orgnr=ESTATE_ORGNR,
    )
    payload = enrichment.to_dict()
    assert payload["estate_manager_name"] is None
    assert payload["estate_manager_identified"] is False
    assert payload["lead_stage"] == "ESTATE_MANAGER_UNKNOWN"
    assert payload["operator_review_required"] is True


def test_artifacts_never_create_a_commercial_opportunity(tmp_path: Path):
    enrichment = normalize_single_estate_record(
        menswear_record(),
        requested_estate_orgnr=ESTATE_ORGNR,
    )
    paths = write_estate_manager_artifacts(enrichment, tmp_path)

    payload = json.loads(paths["enrichment"].read_text(encoding="utf-8"))
    commercial_top5 = json.loads(
        paths["commercial_top5"].read_text(encoding="utf-8")
    )
    summary = paths["summary"].read_text(encoding="utf-8")

    assert payload["estate_manager_identified"] is True
    assert commercial_top5 == []
    assert "Public sale found: false" in summary
    assert "Commercial Top 5 count: 0" in summary
    assert "Automatic contact/bid/purchase/payment: false" in summary
