import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    CLOTHING_NACE_CODES,
    KonkursAppClothingCollector,
    build_api_endpoint,
    build_public_estate_url,
    is_approved_api_endpoint,
    normalize_api_record,
    write_konkurs_app_artifacts,
)

TODAY = date(2026, 7, 29)


def estate_record(**overrides):
    record = {
        "orgnr": "836551362",
        "navn": "YELLOW RETAIL AS KONKURSBO",
        "stiftelsesdato": "2025-11-10",
        "registreringsdato": "2025-11-10",
        "naeringskode": "46.420",
        "naeringsbeskrivelse": "Engroshandel med klær og skotøy",
        "kommune": "KRISTIANSAND",
        "poststed": "KRISTIANSAND S",
        "adresse": "Skal ikke beholdes",
        "mva_registrert": 1,
        "aktiv": 1,
        "debitor_navn": "YELLOW RETAIL AS",
        "debitor_orgnr": "929576748",
        "bostyrer": "Personnavn skal ikke beholdes",
        "regnskap_aar": "2024",
        "regnskap_valuta": "NOK",
        "regnskap_driftsinntekter": 39_714_528,
        "regnskap_sum_eiendeler": 23_583_821,
        "regnskap_sum_gjeld": 13_136_504,
    }
    record.update(overrides)
    return record


def test_api_endpoint_is_bounded_to_two_clothing_codes():
    for code in CLOTHING_NACE_CODES:
        endpoint = build_api_endpoint(code, from_date="2025-07-29", page_size=50)
        assert is_approved_api_endpoint(endpoint)
        params = parse_qs(urlparse(endpoint).query)
        assert params["page"] == ["1"]
        assert params["status"] == ["aktive"]
        assert params["naeringskode"] == [code]

    assert not is_approved_api_endpoint(
        "https://evil.example/api/konkursbo?naeringskode=47.710&status=aktive"
    )
    assert not is_approved_api_endpoint(
        "https://konkurs.app/api/konkursbo?page=2&size=50&sort=stiftelsesdato"
        "&order=desc&naeringskode=47.710&fra_dato=2025-07-29&status=aktive"
    )
    with pytest.raises(ValueError):
        build_api_endpoint("68.209", from_date="2025-07-29")


def test_live_company_record_becomes_verification_lead_without_person_data():
    lead = normalize_api_record(estate_record(), today=TODAY)

    assert lead is not None
    assert lead.debtor_name == "YELLOW RETAIL AS"
    assert lead.industry_code == "46.420"
    assert lead.url == "https://konkurs.app/konkursbo/836551362"
    payload = lead.to_dict()
    assert payload["opportunity_state"] == "STRONG_LEAD_REQUIRES_VERIFICATION"
    assert payload["inventory_sale_verified"] is False
    assert payload["inventory_quantity_verified"] is False
    assert payload["top5_eligible"] is False
    assert payload["analysis_eligible"] is False
    assert payload["person_data_retained"] is False
    assert "bostyrer" not in payload
    assert "address" not in payload


def test_inactive_or_non_clothing_records_are_rejected():
    assert normalize_api_record(estate_record(aktiv=0), today=TODAY) is None
    assert normalize_api_record(
        estate_record(naeringskode="68.209"),
        today=TODAY,
    ) is None
    assert normalize_api_record(estate_record(orgnr="bad"), today=TODAY) is None


def test_collector_reads_exactly_two_bounded_queries_and_deduplicates():
    calls = []

    def fetch_json(url):
        calls.append(url)
        code = parse_qs(urlparse(url).query)["naeringskode"][0]
        if code == "46.420":
            return {"data": [estate_record()]}
        return {
            "data": [
                estate_record(
                    orgnr="936798446",
                    navn="MALENE BARNESKATTER AS TVANGSAVVIKLINGSBO",
                    debitor_navn="MALENE BARNESKATTER AS",
                    naeringskode="47.710",
                    naeringsbeskrivelse="Detaljhandel med klær",
                    stiftelsesdato="2025-12-17",
                    registreringsdato="2025-12-17",
                    kommune="SOLA",
                    poststed="SOLA",
                    mva_registrert=0,
                    regnskap_driftsinntekter=None,
                    regnskap_sum_eiendeler=None,
                    regnskap_sum_gjeld=None,
                ),
                estate_record(),
            ]
        }

    collection = KonkursAppClothingCollector(
        lookback_days=365,
        page_size=50,
        fetch_json=fetch_json,
        today=TODAY,
    ).collect()

    assert len(calls) == 2
    assert all(is_approved_api_endpoint(url) for url in calls)
    assert collection.items_received == 3
    assert len(collection.leads) == 2
    assert collection.scan_complete is True
    assert collection.errors == ()
    assert collection.leads[0].debtor_name == "YELLOW RETAIL AS"


def test_artifacts_keep_bankruptcy_leads_out_of_commercial_top5(tmp_path: Path):
    collection = KonkursAppClothingCollector(
        fetch_json=lambda url: {"data": [estate_record()]},
        today=TODAY,
    ).collect()

    paths = write_konkurs_app_artifacts(collection, tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    lead_top5 = json.loads(paths["lead_top5"].read_text(encoding="utf-8"))
    commercial_top5 = json.loads(
        paths["commercial_top5"].read_text(encoding="utf-8")
    )
    summary = paths["summary"].read_text(encoding="utf-8")

    assert report["lead_count"] == 1
    assert report["commercial_top5_count"] == 0
    assert report["paid_search_used"] is False
    assert report["openai_api_used"] is False
    assert report["playwright_used"] is False
    assert len(lead_top5) == 1
    assert lead_top5[0]["top5_eligible"] is False
    assert lead_top5[0]["inventory_sale_verified"] is False
    assert commercial_top5 == []
    assert "Verified inventory sales: 0" in summary
    assert "Commercial Top 5 count: 0" in summary


def test_public_estate_url_requires_nine_digit_orgnr():
    assert build_public_estate_url("936798446").endswith("/936798446")
    with pytest.raises(ValueError):
        build_public_estate_url("123")
