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


NOW = datetime(2026, 8, 23, 19, 0, tzinfo=timezone.utc)


def _case(case_id: str, evidence: str) -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="LEGACY_TEST",
        observed_at=NOW,
        opportunity_type="STORE_CLOSURE_STOCK_LIQUIDATION",
        stock_proven=True,
        ground_truth_company=case_id,
        ground_truth_url=f"https://example.no/{case_id.casefold()}",
        trace=DiscoveryTrace(query_generated=False),
        learning_evidence_text=evidence,
        root_cause="QUERY_GAP",
        learning_status="DIAGNOSED",
    )


def _write_cases(path: Path, schema: str, cases: list[MissedOpportunityCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": schema, "cases": [case.to_dict() for case in cases]}),
        encoding="utf-8",
    )


def test_daily_runtime_removes_stale_shadow_proof_supported_only_by_out_of_domain_cases(
    tmp_path: Path,
) -> None:
    learning_dir = tmp_path / "learning"
    learning_dir.mkdir(parents=True)
    inbox = tmp_path / "inbox.json"
    validation = tmp_path / "validation.json"
    queries = tmp_path / "queries.json"
    promotions = tmp_path / "promotions.json"

    bauhaus = _case(
        "LEGACY-BAUHAUS",
        "Opphørssalg. Byggematerialer, verktøy, fliser og trelast skal ut.",
    )
    save_missed_opportunity_memory(learning_dir / "missed-opportunities.json", [bauhaus])
    _write_cases(inbox, "missed-opportunity-inbox-1.0", [])
    _write_cases(validation, "query-gap-validation-cases-1.0", [])
    queries.write_text('{"queries": []}', encoding="utf-8")
    promotions.write_text(
        '{"schema_version":"query-promotion-gate-1.0","decisions":[]}',
        encoding="utf-8",
    )

    stale_shadow = {
        "schema_version": "learned-query-overlay-1.0",
        "markets": {
            "NO": [
                {
                    "term": "avviklingssalg",
                    "signal_type": "BUSINESS_CLOSURE",
                    "precision": 0.333333,
                    "source_verdict": "PROVEN",
                    "evaluation_scope": "HOLDOUT_TRANSFER",
                    "evaluation_scopes": ["HOLDOUT_TRANSFER"],
                    "support_case_ids": ["LEGACY-BAUHAUS"],
                    "transfer_validation_case_ids": ["LEGACY-GENERIC-HOLDOUT"],
                    "recovered_case_ids": ["LEGACY-GENERIC-HOLDOUT"],
                    "independent_transfer_case_count": 1,
                }
            ]
        },
        "max_terms_per_market": 5,
        "active_term_count": 1,
        "automatic_query_activation": False,
    }
    (learning_dir / "shadow-keyword-overlay.json").write_text(
        json.dumps(stale_shadow), encoding="utf-8"
    )

    report = run_daily_learning_runtime(
        learning_dir=learning_dir,
        inbox_path=inbox,
        validation_cases_path=validation,
        active_query_config=queries,
        promotion_config_path=promotions,
        environment={"GITHUB_EVENT_NAME": "workflow_dispatch"},
        observed_at=NOW,
    )

    cleaned = json.loads(
        (learning_dir / "shadow-keyword-overlay.json").read_text(encoding="utf-8")
    )
    assert cleaned["active_term_count"] == 0
    assert cleaned["markets"] == {}
    assert report["out_of_domain_excluded_shadow_term_count"] == 1
    assert report["out_of_domain_excluded_shadow_terms"] == ["NO:avviklingssalg"]
    assert report["project_domain_gate_enforced"] is True
