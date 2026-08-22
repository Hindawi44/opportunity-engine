from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    save_missed_opportunity_memory,
)
from opportunity_engine.root_cause_feedback_router import (
    build_root_cause_feedback_report,
    write_root_cause_feedback_router,
)


def _case(
    case_id: str,
    root_cause: str,
    *,
    repeat: bool = False,
    learning_status: str = "DIAGNOSED",
) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="test",
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_BULK_CLOTHING_STOCK",
        stock_proven=True,
        ground_truth_company="Example AS",
        ground_truth_url=f"https://example.no/{case_id}",
        trace=DiscoveryTrace(query_generated=True),
        root_cause=root_cause,
        learning_status=learning_status,
        repeat_miss=repeat,
    )


def test_each_root_cause_routes_to_its_own_adaptation_mechanism() -> None:
    report = build_root_cause_feedback_report(
        [
            _case("query", "QUERY_GAP"),
            _case("source", "SOURCE_GAP"),
            _case("parser", "PARSER_GAP"),
            _case("verify", "VERIFICATION_GAP"),
            _case("report", "REPORTING_GAP"),
        ]
    )

    by_case = {row["case_id"]: row for row in report["routes"]}
    assert by_case["query"]["mechanism"] == "ADAPTIVE_KEYWORD_LEARNING"
    assert by_case["source"]["mechanism"] == "SOURCE_COVERAGE_WATERFALL"
    assert by_case["parser"]["mechanism"] == "PARSER_REGRESSION_QUEUE"
    assert by_case["verify"]["mechanism"] == "VERIFIER_REPAIR_QUEUE"
    assert by_case["report"]["mechanism"] == "REPORTING_INTEGRITY_QUEUE"


def test_only_query_gap_is_keyword_learning_eligible() -> None:
    report = build_root_cause_feedback_report(
        [_case("query", "QUERY_GAP"), _case("source", "SOURCE_GAP")]
    )
    by_case = {row["case_id"]: row for row in report["routes"]}

    assert by_case["query"]["keyword_learning_eligible"] is True
    assert by_case["query"]["automatic_adaptation_available"] is True
    assert by_case["source"]["keyword_learning_eligible"] is False
    assert by_case["source"]["automatic_adaptation_available"] is False
    assert report["keyword_learning_route_count"] == 1


def test_repeat_miss_escalates_priority_without_changing_mechanism() -> None:
    report = build_root_cause_feedback_report(
        [_case("source-normal", "SOURCE_GAP"), _case("source-repeat", "SOURCE_GAP", repeat=True)]
    )
    by_case = {row["case_id"]: row for row in report["routes"]}

    assert by_case["source-normal"]["priority"] == "HIGH"
    assert by_case["source-repeat"]["priority"] == "CRITICAL"
    assert by_case["source-repeat"]["mechanism"] == "SOURCE_COVERAGE_WATERFALL"
    assert by_case["source-repeat"]["repeat_miss"] is True
    assert report["critical_route_count"] == 1


def test_recovered_non_repeat_case_is_not_reopened() -> None:
    report = build_root_cause_feedback_report(
        [_case("done", "QUERY_GAP", learning_status="RECOVERED")]
    )

    [route] = report["routes"]
    assert route["route_status"] == "RECOVERED_MONITOR_ONLY"
    assert route["automatic_adaptation_available"] is False
    assert report["active_route_count"] == 0


def test_unknown_or_unhandled_root_cause_goes_to_manual_diagnostics_not_keywords() -> None:
    report = build_root_cause_feedback_report([_case("rank", "RANKING_GAP")])

    [route] = report["routes"]
    assert route["mechanism"] == "RANKING_POLICY_REVIEW_QUEUE"
    assert route["keyword_learning_eligible"] is False


def test_empty_memory_is_valid_zero() -> None:
    report = build_root_cause_feedback_report([])

    assert report["status"] == "VALID_ZERO_NO_MISSED_OPPORTUNITIES"
    assert report["routes"] == []
    assert report["active_route_count"] == 0


def test_writer_reads_durable_memory_and_attaches_operator_brief(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "checkpoint"
    output_dir.mkdir(parents=True)
    memory = input_root / "learning" / "missed-opportunities.json"
    save_missed_opportunity_memory(
        memory,
        [_case("source", "SOURCE_GAP", repeat=True), _case("parser", "PARSER_GAP")],
    )
    (output_dir / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"status": "SUCCESS"}), encoding="utf-8"
    )

    report = write_root_cause_feedback_router(output_dir, input_root=input_root)

    assert report["status"] == "ACTION_REQUIRED"
    assert report["active_route_count"] == 2
    assert report["mechanism_counts"]["SOURCE_COVERAGE_WATERFALL"] == 1
    assert (output_dir / "root-cause-feedback-router.json").exists()
    brief = json.loads(
        (output_dir / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    assert brief["root_cause_feedback_router"]["critical_route_count"] == 1
    assert report["automatic_contact"] is False
    assert report["automatic_purchase"] is False


def test_daily_hook_runs_router_after_automatic_miss_capture() -> None:
    hook = Path(
        "src/opportunity_engine/discovery/unified_market_intelligence_river_cli_hook.py"
    ).read_text(encoding="utf-8")

    assert "write_root_cause_feedback_router" in hook
    assert hook.index("write_automatic_missed_opportunity_capture(") < hook.index(
        "write_root_cause_feedback_router("
    )
