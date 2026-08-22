"""Promotion-gated production wrapper for SOURCE_GAP adaptive follow-up.

The existing SOURCE_GAP planner remains useful shadow logic. This wrapper is the
production boundary: only exact missed-opportunity cases with an auditable
PROMOTED decision may consume the existing follow-up case/search budget.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.signal_follow_up_continuity import (
    ProviderFactory,
    _compact,
    _run_memory_plan,
    _write_json,
    write_signal_follow_up_engine_with_continuity,
)
from opportunity_engine.discovery.signal_follow_up_engine import (
    DEFAULT_MAX_CASES,
    DEFAULT_RESULTS_PER_CASE,
    MAX_CASES,
    OUTPUT_FILENAME,
    _attach_to_domain_brief,
)
from opportunity_engine.discovery.source_gap_adaptive_followup import (
    MEMORY_RELATIVE_PATH,
    _active_source_gap_cases,
    _domain_bound_factory,
    _merge_reports,
    build_source_gap_follow_up_plan,
)
from opportunity_engine.missed_opportunity_learning import load_missed_opportunity_memory
from opportunity_engine.source_gap_promotion_gate import (
    load_source_gap_promotion_decisions,
    select_promoted_source_gap_cases,
)

DEFAULT_PROMOTION_CONFIG = Path("config/learning/source_gap_promotions.json")


def write_safe_source_gap_adaptive_followup_with_continuity(
    output_dir: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
    results_per_case: int = DEFAULT_RESULTS_PER_CASE,
    promotion_config_path: str | Path = DEFAULT_PROMOTION_CONFIG,
) -> dict[str, Any]:
    """Run production SOURCE_GAP follow-up only for explicitly promoted cases."""
    directory = Path(output_dir)
    env = environment if environment is not None else os.environ
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    input_root = Path(
        _compact(env.get("INPUT_ROOT"))
        or (directory.parent / "multi-market-inputs").as_posix()
    )

    source_gap_cases = load_missed_opportunity_memory(
        input_root / MEMORY_RELATIVE_PATH
    )
    shadow_cases = _active_source_gap_cases(source_gap_cases)
    decisions = load_source_gap_promotion_decisions(promotion_config_path)
    promoted_cases = select_promoted_source_gap_cases(shadow_cases, decisions)

    plan = build_source_gap_follow_up_plan(promoted_cases, max_cases=bounded)
    source_result = _run_memory_plan(
        plan,
        environment=env,
        provider_factory=_domain_bound_factory(provider_factory),
        results_per_case=results_per_case,
    )
    remaining = max(0, bounded - len(plan))
    base = write_signal_follow_up_engine_with_continuity(
        directory,
        environment=env,
        provider_factory=provider_factory,
        observed_at=observed_at,
        max_cases=remaining,
        results_per_case=results_per_case,
    )
    report = _merge_reports(
        source_result,
        base,
        source_gap_case_count=len(shadow_cases),
        source_gap_selected_count=len(plan),
        follow_up_case_budget=bounded,
        api_key=_compact(env.get("BRAVE_SEARCH_API_KEY")),
    )
    report.update(
        {
            "purpose": "PRIORITIZE_EXPLICITLY_PROMOTED_SOURCE_GAPS_WITHIN_EXISTING_FOLLOW_UP_BUDGET",
            "source_gap_shadow_case_count": len(shadow_cases),
            "source_gap_promoted_case_count": len(promoted_cases),
            "source_gap_promotion_decision_count": len(decisions),
            "source_gap_promotion_config_path": Path(promotion_config_path).as_posix(),
            "promotion_gate_enforced": True,
            "automatic_source_gap_activation": False,
            "production_source_gap_follow_up_requires_explicit_promotion": True,
        }
    )
    _write_json(directory / OUTPUT_FILENAME, report)
    _attach_to_domain_brief(directory, report)
    return report
