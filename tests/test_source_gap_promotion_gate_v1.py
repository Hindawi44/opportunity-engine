from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.source_gap_safe_followup import (
    write_safe_source_gap_adaptive_followup_with_continuity,
)
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    save_missed_opportunity_memory,
)
from opportunity_engine.source_gap_promotion_gate import (
    load_source_gap_promotion_decisions,
    select_promoted_source_gap_cases,
)


def _case(case_id: str = "source-gap-real-1") -> MissedOpportunityCase:
    return MissedOpportunityCase(
        case_id=case_id,
        market_code="NO",
        discovered_by="AUTOMATIC_SOURCE_VERIFIED_GAP_DETECTOR",
        observed_at=datetime(2026, 8, 22, 8, 0, tzinfo=timezone.utc),
        opportunity_type="VERIFIED_BULK_CLOTHING_STOCK",
        stock_proven=True,
        ground_truth_company="Eksempel Arbeidsklær AS",
        ground_truth_url="https://ny.auksjonen.no/auksjon/gammelt-varelager/424242",
        trace=DiscoveryTrace(query_generated=True, search_hit=False),
        root_cause="SOURCE_GAP",
        learning_status="DIAGNOSED",
    )


class Provider:
    name = "test"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return []


def test_source_gap_stays_shadow_only_without_explicit_promotion() -> None:
    case = _case()
    assert select_promoted_source_gap_cases([case], {}) == []


def test_exact_promotion_selects_only_existing_source_gap_case() -> None:
    case = _case()
    decisions = {
        "source-gap-real-1": "PROMOTED",
        "invented-case": "PROMOTED",
    }

    assert [item.case_id for item in select_promoted_source_gap_cases([case], decisions)] == [
        "source-gap-real-1"
    ]


def test_disabled_source_gap_is_rolled_back_without_deleting_case() -> None:
    case = _case()
    assert select_promoted_source_gap_cases(
        [case], {case.case_id: "DISABLED"}
    ) == []
    assert case.case_id == "source-gap-real-1"


def test_source_gap_promotion_config_requires_auditable_decision(tmp_path: Path) -> None:
    path = tmp_path / "source-gap-promotions.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "source-gap-promotion-gate-1.0",
                "decisions": [
                    {
                        "case_id": "source-gap-real-1",
                        "status": "PROMOTED",
                        "reason": "Shadow domain follow-up proved useful coverage.",
                        "approved_at": "2026-08-22T10:45:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_source_gap_promotion_decisions(path) == {
        "source-gap-real-1": "PROMOTED"
    }


def test_safe_writer_does_not_spend_source_gap_search_without_promotion(tmp_path: Path) -> None:
    output_dir = tmp_path / "checkpoint"
    input_root = tmp_path / "inputs"
    output_dir.mkdir(parents=True)
    (output_dir / "unified-market-cases.json").write_text('{"cases": []}', encoding="utf-8")
    save_missed_opportunity_memory(
        input_root / "learning" / "missed-opportunities.json",
        [_case()],
    )
    provider = Provider()

    report = write_safe_source_gap_adaptive_followup_with_continuity(
        output_dir,
        environment={
            "INPUT_ROOT": input_root.as_posix(),
            "BRAVE_SEARCH_API_KEY": "test-key",
        },
        provider_factory=lambda market, key: provider,
        promotion_config_path=tmp_path / "missing-promotions.json",
        max_cases=1,
    )

    assert report["source_gap_shadow_case_count"] == 1
    assert report["source_gap_promoted_case_count"] == 0
    assert report["source_gap_search_request_count"] == 0
    assert report["promotion_gate_enforced"] is True
    assert provider.calls == []


def test_safe_writer_executes_promoted_source_gap_inside_same_budget(tmp_path: Path) -> None:
    output_dir = tmp_path / "checkpoint"
    input_root = tmp_path / "inputs"
    output_dir.mkdir(parents=True)
    (output_dir / "unified-market-cases.json").write_text('{"cases": []}', encoding="utf-8")
    case = _case()
    save_missed_opportunity_memory(
        input_root / "learning" / "missed-opportunities.json",
        [case],
    )
    promotions = tmp_path / "source-gap-promotions.json"
    promotions.write_text(
        json.dumps(
            {
                "schema_version": "source-gap-promotion-gate-1.0",
                "decisions": [
                    {
                        "case_id": case.case_id,
                        "status": "PROMOTED",
                        "reason": "Shadow coverage passed the promotion threshold.",
                        "approved_at": "2026-08-22T10:45:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    provider = Provider()

    report = write_safe_source_gap_adaptive_followup_with_continuity(
        output_dir,
        environment={
            "INPUT_ROOT": input_root.as_posix(),
            "BRAVE_SEARCH_API_KEY": "test-key",
        },
        provider_factory=lambda market, key: provider,
        promotion_config_path=promotions,
        max_cases=1,
    )

    assert report["source_gap_shadow_case_count"] == 1
    assert report["source_gap_promoted_case_count"] == 1
    assert report["source_gap_selected_count"] == 1
    assert report["source_gap_search_request_count"] == 1
    assert report["follow_up_case_budget"] == 1
    assert len(provider.calls) == 1


def test_daily_hook_uses_safe_source_gap_writer() -> None:
    hook = Path(
        "src/opportunity_engine/discovery/unified_market_intelligence_river_cli_hook.py"
    ).read_text(encoding="utf-8")

    assert "write_safe_source_gap_adaptive_followup_with_continuity" in hook
    assert "write_source_gap_adaptive_followup_with_continuity" not in hook
