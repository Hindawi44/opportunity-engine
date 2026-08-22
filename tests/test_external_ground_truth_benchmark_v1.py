from __future__ import annotations

from opportunity_engine.external_ground_truth_benchmark import evaluate_external_ground_truth


def _benchmark() -> dict:
    return {
        "schema_version": "external-ground-truth-benchmark-1.0",
        "captured_at": "2026-08-22T11:12:00Z",
        "opportunities": [
            {
                "case_id": "worldwise-athleisure-29000",
                "source_name": "WorldWiseUSA",
                "source_url": "https://www.worldwiseusa.com/ready-to-profit-athleisure-load-ready-we-have-your-inventory-report-29000-units/",
                "evidence_url": "https://www.worldwiseusa.com/latest-stock-lot-offers/",
                "title": "Athleisure load ready - 29,000 units",
                "stock_proven": True,
                "public_evidence_verified": True,
            }
        ],
    }


def test_external_verified_lot_absent_from_engine_is_confirmed_source_gap() -> None:
    report = evaluate_external_ground_truth(
        _benchmark(),
        documents={
            "multi-market-daily-checkpoint.json": {
                "deduplicated_opportunities": [
                    {"source_url": "https://ny.auksjonen.no/auksjon/example/1"}
                ]
            }
        },
    )

    assert report["benchmark_count"] == 1
    assert report["baseline_found_count"] == 0
    assert report["confirmed_miss_count"] == 1
    assert report["root_cause_counts"] == {"SOURCE_GAP": 1}
    [case] = report["cases"]
    assert case["baseline_found"] is False
    assert case["source_domain_seen_by_baseline"] is False
    assert case["confirmed_miss"] is True
    assert case["root_cause"] == "SOURCE_GAP"


def test_exact_url_in_engine_is_not_a_miss() -> None:
    benchmark = _benchmark()
    url = benchmark["opportunities"][0]["source_url"]
    report = evaluate_external_ground_truth(
        benchmark,
        documents={"checkpoint.json": {"source_urls": [url]}},
    )

    assert report["baseline_found_count"] == 1
    assert report["confirmed_miss_count"] == 0
    assert report["cases"][0]["baseline_found"] is True
    assert report["cases"][0]["root_cause"] is None


def test_domain_seen_without_exact_lot_is_source_coverage_gap() -> None:
    report = evaluate_external_ground_truth(
        _benchmark(),
        documents={
            "signals.json": {
                "source_url": "https://www.worldwiseusa.com/other-stock-lot/"
            }
        },
    )

    [case] = report["cases"]
    assert case["baseline_found"] is False
    assert case["source_domain_seen_by_baseline"] is True
    assert case["confirmed_miss"] is True
    assert case["root_cause"] == "SOURCE_COVERAGE_GAP"


def test_unverified_external_claim_never_becomes_ground_truth() -> None:
    benchmark = _benchmark()
    benchmark["opportunities"][0]["public_evidence_verified"] = False

    report = evaluate_external_ground_truth(benchmark, documents={})

    assert report["confirmed_miss_count"] == 0
    assert report["cases"][0]["confirmed_miss"] is False
    assert report["cases"][0]["root_cause"] is None


def test_benchmark_is_read_only_and_cannot_promote_production() -> None:
    report = evaluate_external_ground_truth(_benchmark(), documents={})

    assert report["automatic_promotion"] is False
    assert report["production_mutation"] is False
    assert report["network_requests"] == 0
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False
