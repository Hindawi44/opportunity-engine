from pathlib import Path
import json

from opportunity_engine.discovery.search_validation_gate import (
    SearchObservation,
    build_search_validation_report,
    load_observations,
)


def obs(
    run,
    market,
    source,
    *,
    accepted=1,
    verified=1,
    q=10,
    qs=10,
    paid=True,
    requests=10,
):
    return SearchObservation(
        run_label=run,
        artifact_path=f"{run}/{source}.json",
        observed_at=None,
        market_code=market,
        source_name=source,
        execution_status="PASS",
        queries_attempted=q,
        queries_succeeded=qs,
        paid_search=paid,
        paid_requests_made=requests if paid else 0,
        raw_hits=20,
        accepted_leads=accepted,
        rejected_results=5,
        ended_or_historical=0,
        verified_active_leads=verified,
        actionable_leads=0,
    )


def test_one_green_workflow_run_is_not_search_proof():
    report = build_search_validation_report(
        [obs("run1", "NO", "source")], required_markets=["NO"]
    )
    source = report["sources"][0]
    assert source["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "MIN_LIVE_RUNS_NOT_MET" in source["reasons"]
    assert report["progression_gate_open"] is False


def test_source_is_proven_only_after_repeated_verified_active_runs():
    rows = [
        obs("run1", "NO", "source", verified=1),
        obs("run2", "NO", "source", verified=1),
        obs("run3", "NO", "source", accepted=0, verified=0),
    ]
    report = build_search_validation_report(rows, required_markets=["NO"])
    source = report["sources"][0]
    assert source["verdict"] == "PROVEN"
    assert source["productive_run_rate"] == 0.666667
    assert source["verified_active_run_count"] == 2
    assert report["overall_verdict"] == "PROVEN"
    assert report["next_stage_authorized"] == "MEMORY_FOLLOW_UP"
    assert report["downstream_progression_authorized"]["new_math_work"] is False


def test_repeated_zero_verified_results_are_not_proven():
    rows = [
        obs(f"run{i}", "SE", "source", accepted=5, verified=0)
        for i in range(1, 4)
    ]
    report = build_search_validation_report(rows, required_markets=["SE"])
    source = report["sources"][0]
    assert source["verdict"] == "NOT_PROVEN"
    assert "REPEATED_VERIFIED_ACTIVE_LEADS_NOT_PROVEN" in source["reasons"]


def test_paid_request_accounting_is_required_before_proof():
    rows = [
        obs(f"run{i}", "DE", "source", verified=1, requests=None)
        for i in range(1, 4)
    ]
    report = build_search_validation_report(rows, required_markets=["DE"])
    source = report["sources"][0]
    assert source["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "PAID_REQUEST_ACCOUNTING_INCOMPLETE" in source["reasons"]


def test_loader_reads_existing_search_run_shape_without_network(tmp_path: Path):
    run = tmp_path / "run191" / "multi-market-inputs" / "se-psauction"
    run.mkdir(parents=True)
    payload = {
        "schema_version": "clothing-inventory-discovery-search-1.3",
        "status": "PASS",
        "execution_status": "PASS",
        "market_code": "SE",
        "source_target": "psauction.se",
        "queries_submitted": 8,
        "hits_received": 47,
        "merged_candidates": 27,
        "strong_leads_requiring_verification": 21,
        "confirmed_sales": 0,
        "ended_or_historical": 6,
        "top5_count": 0,
        "analysis_eligible_count": 0,
        "source_diagnostics": {
            "requests_made": 8,
            "raw_hits": 72,
            "accepted_hits": 47,
            "rejected_hits": 25,
            "query_diagnostics": [
                {"status": "SUCCESS"} for _ in range(8)
            ],
        },
    }
    (run / "search-run-report.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    rows = load_observations([tmp_path / "run191"])
    assert len(rows) == 1
    row = rows[0]
    assert row.market_code == "SE"
    assert row.source_name == "psauction.se"
    assert row.paid_requests_made == 8
    assert row.raw_hits == 72
    assert row.accepted_leads == 21
    assert row.verified_active_leads == 0
