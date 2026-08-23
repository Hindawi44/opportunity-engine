from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.daily_learning_runtime import run_daily_learning_runtime
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    save_missed_opportunity_memory,
)
from opportunity_engine.root_cause_feedback_router import write_root_cause_feedback_router


NOW = datetime(2026, 8, 23, 19, 0, tzinfo=timezone.utc)


def _case(*, case_id: str, company: str, evidence: str) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="LEGACY_TEST",
        observed_at=NOW,
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company=company,
        ground_truth_url=f"https://example.no/{case_id.casefold()}",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=evidence,
        root_cause="QUERY_GAP",
        learning_status="DIAGNOSED",
    )


def _write_case_file(path: Path, schema: str, cases: list[MissedOpportunityCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": schema,
                "cases": [case.to_dict() for case in cases],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_root_cause_router_quarantines_restored_out_of_domain_legacy_cases(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output = tmp_path / "output"
    memory = input_root / "learning" / "missed-opportunities.json"

    save_missed_opportunity_memory(
        memory,
        [
            _case(
                case_id="LEGACY-BAUHAUS",
                company="BAUHAUS",
                evidence=(
                    "BAUHAUS Norge opphørssalg. Hele lagerbeholdningen med "
                    "byggematerialer, verktøy, fliser og trelast skal ut."
                ),
            ),
            _case(
                case_id="LEGACY-CLOTHING",
                company="Example Fashion AS",
                evidence=(
                    "Klesbutikk legges ned. Hele varelageret av klær, jakker og bukser selges ut."
                ),
            ),
        ],
    )

    report = write_root_cause_feedback_router(output, input_root=input_root)

    assert report["known_case_count"] == 1
    assert report["active_route_count"] == 1
    assert report["routes"][0]["case_id"] == "LEGACY-CLOTHING"
    assert report["out_of_domain_excluded_case_count"] == 1
    assert report["out_of_domain_excluded_case_ids"] == ["LEGACY-BAUHAUS"]
    assert report["project_domain_gate_enforced"] is True


def test_daily_runtime_quarantines_legacy_memory_and_curated_inbox_before_learning(tmp_path: Path) -> None:
    learning_dir = tmp_path / "learning"
    inbox = tmp_path / "missed-opportunity-inbox.json"
    validation = tmp_path / "query-gap-validation-cases.json"
    active_queries = tmp_path / "active-queries.json"
    promotions = tmp_path / "query-promotions.json"

    save_missed_opportunity_memory(
        learning_dir / "missed-opportunities.json",
        [
            _case(
                case_id="LEGACY-BAUHAUS",
                company="BAUHAUS",
                evidence="Opphørssalg på byggematerialer, verktøy, fliser og trelast.",
            )
        ],
    )
    _write_case_file(
        inbox,
        "missed-opportunity-inbox-1.0",
        [
            _case(
                case_id="LEGACY-LENE-INTERIOR",
                company="Lene Interiør",
                evidence="Lene Interiør legges ned. Stort avslutningssalg på alle varer i butikken.",
            ),
            _case(
                case_id="CURRENT-CLOTHING-MISS",
                company="Example Fashion AS",
                evidence="Klesbutikk stenger. Hele varelageret av klær og jakker skal ut.",
            ),
        ],
    )
    _write_case_file(validation, "query-gap-validation-cases-1.0", [])
    active_queries.write_text('{"queries": []}', encoding="utf-8")
    promotions.write_text(
        '{"schema_version":"query-promotion-gate-1.0","decisions":[]}',
        encoding="utf-8",
    )

    report = run_daily_learning_runtime(
        learning_dir=learning_dir,
        inbox_path=inbox,
        validation_cases_path=validation,
        active_query_config=active_queries,
        promotion_config_path=promotions,
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
        observed_at=NOW,
    )

    assert report["known_missed_opportunity_count"] == 1
    assert report["out_of_domain_excluded_case_count"] == 2
    assert report["out_of_domain_excluded_case_ids"] == [
        "LEGACY-BAUHAUS",
        "LEGACY-LENE-INTERIOR",
    ]
    assert report["project_domain_gate_enforced"] is True

    persisted = json.loads(
        (learning_dir / "missed-opportunities.json").read_text(encoding="utf-8")
    )
    assert persisted["case_count"] == 1
    assert persisted["cases"][0]["case_id"] == "CURRENT-CLOTHING-MISS"


def test_daily_runtime_fails_closed_for_validation_holdout_without_domain_evidence(tmp_path: Path) -> None:
    learning_dir = tmp_path / "learning"
    inbox = tmp_path / "missed-opportunity-inbox.json"
    validation = tmp_path / "query-gap-validation-cases.json"
    active_queries = tmp_path / "active-queries.json"
    promotions = tmp_path / "query-promotions.json"

    _write_case_file(
        inbox,
        "missed-opportunity-inbox-1.0",
        [
            _case(
                case_id="CURRENT-CLOTHING-MISS",
                company="Example Fashion AS",
                evidence="Klesbutikk stenger. Hele varelageret av klær og bukser skal ut.",
            )
        ],
    )
    _write_case_file(
        validation,
        "query-gap-validation-cases-1.0",
        [
            _case(
                case_id="LEGACY-GENERIC-HOLDOUT",
                company="Generic Store AS",
                evidence="",
            )
        ],
    )
    active_queries.write_text('{"queries": []}', encoding="utf-8")
    promotions.write_text(
        '{"schema_version":"query-promotion-gate-1.0","decisions":[]}',
        encoding="utf-8",
    )

    report = run_daily_learning_runtime(
        learning_dir=learning_dir,
        inbox_path=inbox,
        validation_cases_path=validation,
        active_query_config=active_queries,
        promotion_config_path=promotions,
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
        observed_at=NOW,
    )

    assert report["validation_case_count"] == 0
    assert report["out_of_domain_excluded_validation_case_count"] == 1
    assert report["out_of_domain_excluded_validation_case_ids"] == [
        "LEGACY-GENERIC-HOLDOUT"
    ]
    assert report["project_domain_gate_enforced"] is True
