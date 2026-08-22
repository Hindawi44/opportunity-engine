from __future__ import annotations

from opportunity_engine.source_discovery_shadow import build_source_shadow_candidates


def _benchmark() -> dict:
    return {
        "schema_version": "external-ground-truth-benchmark-1.0",
        "opportunities": [
            {
                "case_id": "worldwise-1",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/offer-1/",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "APPAREL"},
            },
            {
                "case_id": "worldwise-2",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/offer-2/",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "BUILDING_MATERIALS"},
            },
            {
                "case_id": "worldwise-3",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/offer-3/",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "APPAREL"},
            },
            {
                "case_id": "stocklear-1",
                "source_name": "Stocklear",
                "source_url": "https://joblot.stocklear.eu/auction/1",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "GENERAL_MERCHANDISE"},
            },
            {
                "case_id": "stocklear-2",
                "source_name": "Stocklear",
                "source_url": "https://joblot.stocklear.eu/auction/2",
                "stock_proven": True,
                "public_evidence_verified": True,
                "evidence": {"category": "APPLIANCES"},
            },
        ],
    }


def _benchmark_result() -> dict:
    return {
        "schema_version": "external-ground-truth-benchmark-report-1.0",
        "cases": [
            {"case_id": case_id, "confirmed_miss": True, "root_cause": "SOURCE_GAP"}
            for case_id in (
                "worldwise-1",
                "worldwise-2",
                "worldwise-3",
                "stocklear-1",
                "stocklear-2",
            )
        ],
    }


def test_repeated_verified_source_gaps_become_validated_shadow_sources() -> None:
    report = build_source_shadow_candidates(_benchmark(), _benchmark_result())

    assert report["source_candidate_count"] == 2
    assert report["validated_source_count"] == 2
    assert report["shadow_eligible_source_count"] == 2
    by_domain = {row["source_domain"]: row for row in report["source_candidates"]}

    worldwise = by_domain["www.worldwiseusa.com"]
    assert worldwise["status"] == "VALIDATED_SOURCE"
    assert worldwise["verified_opportunity_count"] == 3
    assert worldwise["evidence_case_ids"] == [
        "worldwise-1",
        "worldwise-2",
        "worldwise-3",
    ]
    assert worldwise["categories"] == ["APPAREL", "BUILDING_MATERIALS"]
    assert worldwise["shadow_eligible"] is True
    assert worldwise["production_active"] is False

    stocklear = by_domain["joblot.stocklear.eu"]
    assert stocklear["status"] == "VALIDATED_SOURCE"
    assert stocklear["verified_opportunity_count"] == 2
    assert stocklear["shadow_eligible"] is True


def test_single_verified_miss_stays_candidate_not_validated() -> None:
    benchmark = _benchmark()
    benchmark["opportunities"] = benchmark["opportunities"][:1]
    result = _benchmark_result()
    result["cases"] = result["cases"][:1]

    report = build_source_shadow_candidates(benchmark, result)

    assert report["source_candidate_count"] == 1
    assert report["validated_source_count"] == 0
    [candidate] = report["source_candidates"]
    assert candidate["status"] == "CANDIDATE"
    assert candidate["shadow_eligible"] is False


def test_duplicate_url_does_not_fake_independent_source_validation() -> None:
    benchmark = _benchmark()
    benchmark["opportunities"] = [
        benchmark["opportunities"][0],
        {
            **benchmark["opportunities"][0],
            "case_id": "worldwise-duplicate",
        },
    ]
    result = {
        "schema_version": "external-ground-truth-benchmark-report-1.0",
        "cases": [
            {"case_id": "worldwise-1", "confirmed_miss": True, "root_cause": "SOURCE_GAP"},
            {"case_id": "worldwise-duplicate", "confirmed_miss": True, "root_cause": "SOURCE_GAP"},
        ],
    }

    report = build_source_shadow_candidates(benchmark, result)

    [candidate] = report["source_candidates"]
    assert candidate["verified_opportunity_count"] == 1
    assert candidate["status"] == "CANDIDATE"
    assert candidate["shadow_eligible"] is False


def test_non_source_gap_and_unconfirmed_cases_do_not_train_source_candidates() -> None:
    result = _benchmark_result()
    result["cases"][0]["root_cause"] = "QUERY_GAP"
    result["cases"][1]["confirmed_miss"] = False

    report = build_source_shadow_candidates(_benchmark(), result)

    by_domain = {row["source_domain"]: row for row in report["source_candidates"]}
    worldwise = by_domain["www.worldwiseusa.com"]
    assert worldwise["verified_opportunity_count"] == 1
    assert worldwise["status"] == "CANDIDATE"
    assert by_domain["joblot.stocklear.eu"]["status"] == "VALIDATED_SOURCE"


def test_source_shadow_learning_never_activates_production() -> None:
    report = build_source_shadow_candidates(_benchmark(), _benchmark_result())

    assert report["automatic_source_addition"] is False
    assert report["automatic_promotion"] is False
    assert report["production_mutation"] is False
    assert report["network_requests"] == 0
    assert all(row["production_active"] is False for row in report["source_candidates"])
