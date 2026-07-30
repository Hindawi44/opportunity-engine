import json
from datetime import date
from pathlib import Path

import pytest

from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    KonkursAppClothingCollection,
    KonkursAppClothingLead,
)
from opportunity_engine.discovery.pre_market_clothing_leads import (
    build_pre_market_pilot,
    score_pre_market_lead,
    write_pre_market_artifacts,
)

TODAY = date(2026, 7, 30)


def clothing_lead(**overrides) -> KonkursAppClothingLead:
    values = {
        "estate_orgnr": "836551362",
        "estate_name": "YELLOW RETAIL AS KONKURSBO",
        "debtor_name": "YELLOW RETAIL AS",
        "url": "https://konkurs.app/konkursbo/836551362",
        "opened_date": "2026-07-15",
        "registered_date": "2026-07-15",
        "industry_code": "46.420",
        "industry_description": "Engroshandel med klær og skotøy",
        "municipality": "KRISTIANSAND",
        "postal_place": "KRISTIANSAND S",
        "mva_registered": True,
        "accounting_year": "2024",
        "accounting_currency": "NOK",
        "revenue": 15_000_000.0,
        "total_assets": 12_000_000.0,
        "total_debt": 7_000_000.0,
        "priority_score": 100,
    }
    values.update(overrides)
    return KonkursAppClothingLead(**values)


def collection(*leads: KonkursAppClothingLead) -> KonkursAppClothingCollection:
    return KonkursAppClothingCollection(
        captured_at="2026-07-30T08:00:00+00:00",
        from_date="2025-07-30",
        endpoints=("https://konkurs.app/api/konkursbo?bounded=1",),
        items_received=len(leads),
        leads=leads,
        scan_complete=True,
    )


def test_recent_large_wholesaler_gets_high_review_signal_without_sale_claim():
    score, breakdown, reasons = score_pre_market_lead(clothing_lead(), today=TODAY)

    assert score == 100
    assert breakdown == {
        "recency": 30,
        "industry": 25,
        "mva_registration": 10,
        "asset_scale": 20,
        "revenue_scale": 15,
    }
    assert "clothing and footwear wholesale industry" in reasons

    result = build_pre_market_pilot(collection(clothing_lead()), today=TODAY)
    payload = result.review_top[0].to_dict()
    assert payload["inventory_signal_band"] == "HIGH"
    assert (
        payload["score_basis"]
        == "HEURISTIC_COMPANY_SIGNAL_NOT_VERIFIED_INVENTORY_PROBABILITY"
    )
    assert payload["public_sale_found"] is False
    assert payload["inventory_sale_verified"] is False
    assert payload["top5_eligible"] is False
    assert payload["analysis_eligible"] is False
    assert payload["automatic_contact"] is False


def test_ranking_prefers_stronger_recent_company_signal():
    weak = clothing_lead(
        estate_orgnr="936798446",
        estate_name="SMALL SHOP AS KONKURSBO",
        debtor_name="SMALL SHOP AS",
        url="https://konkurs.app/konkursbo/936798446",
        opened_date="2025-08-01",
        registered_date="2025-08-01",
        industry_code="47.710",
        industry_description="Detaljhandel med klær",
        mva_registered=False,
        revenue=None,
        total_assets=None,
        total_debt=None,
        priority_score=20,
    )
    strong = clothing_lead()

    result = build_pre_market_pilot(
        collection(weak, strong),
        review_limit=1,
        today=TODAY,
    )

    assert result.review_top[0].source_lead.debtor_name == "YELLOW RETAIL AS"
    assert result.review_top[0].inventory_signal_score == 100
    assert result.leads[1].inventory_signal_score == 20


def test_artifacts_create_review_queue_but_keep_commercial_top5_empty(tmp_path: Path):
    result = build_pre_market_pilot(collection(clothing_lead()), today=TODAY)
    paths = write_pre_market_artifacts(result, tmp_path)

    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    review_top = json.loads(paths["review_top"].read_text(encoding="utf-8"))
    commercial_top5 = json.loads(
        paths["commercial_top5"].read_text(encoding="utf-8")
    )
    summary = paths["summary"].read_text(encoding="utf-8")

    assert report["schema_version"] == "pre-market-clothing-leads-pilot-1.0"
    assert report["score_is_verified_probability"] is False
    assert report["commercial_top5_count"] == 0
    assert report["person_data_retained"] is False
    assert len(review_top) == 1
    assert review_top[0]["lead_stage"] == "PRE_MARKET_LEAD"
    assert review_top[0]["operator_review_required"] is True
    assert "bostyrer" not in review_top[0]
    assert commercial_top5 == []
    assert "not verified inventory probability" in summary
    assert "Commercial Top 5 count: 0" in summary


def test_review_limit_is_bounded():
    source = collection(clothing_lead())
    with pytest.raises(ValueError):
        build_pre_market_pilot(source, review_limit=0, today=TODAY)
    with pytest.raises(ValueError):
        build_pre_market_pilot(source, review_limit=21, today=TODAY)
