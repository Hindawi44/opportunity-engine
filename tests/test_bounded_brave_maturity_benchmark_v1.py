from __future__ import annotations

from opportunity_engine.cost_guard import (
    AUTOMATED_CHECKPOINT_JOB,
    AUTOMATED_CHECKPOINT_WORKFLOW,
    MANUAL_PAID_BRAVE_BENCHMARK_BRANCH,
    MANUAL_PAID_BRAVE_BENCHMARK_BUDGET_ID,
    MANUAL_PAID_BRAVE_BENCHMARK_MAX_REQUESTS,
    MANUAL_PAID_BRAVE_BLOCK_REASON,
    MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD,
    manual_paid_brave_block_reason,
    manual_paid_brave_incremental_budget,
)


BENCHMARK_ENV = {
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_WORKFLOW": AUTOMATED_CHECKPOINT_WORKFLOW,
    "GITHUB_JOB": AUTOMATED_CHECKPOINT_JOB,
    "GITHUB_ACTOR": "Hindawi44",
    "GITHUB_REF_NAME": MANUAL_PAID_BRAVE_BENCHMARK_BRANCH,
    "GITHUB_RUN_ATTEMPT": "1",
    "BRAVE_SEARCH_API_KEY": "would-be-paid-key",
}


def test_dedicated_maturity_benchmark_is_allowed_with_small_global_cap() -> None:
    assert manual_paid_brave_block_reason(BENCHMARK_ENV) is None

    budget = manual_paid_brave_incremental_budget(BENCHMARK_ENV)
    assert budget is not None
    assert budget["budget_id"] == MANUAL_PAID_BRAVE_BENCHMARK_BUDGET_ID
    assert budget["max_requests"] == MANUAL_PAID_BRAVE_BENCHMARK_MAX_REQUESTS == 60
    assert budget["observed_unit_cost_usd"] == MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD
    assert budget["max_incremental_cost_usd"] == 0.30


def test_normal_manual_main_checkpoint_remains_zero_cost_by_default() -> None:
    env = {**BENCHMARK_ENV, "GITHUB_REF_NAME": "main"}
    assert manual_paid_brave_block_reason(env) == MANUAL_PAID_BRAVE_BLOCK_REASON


def test_benchmark_fails_closed_for_bot_wrong_branch_or_rerun() -> None:
    cases = (
        {**BENCHMARK_ENV, "GITHUB_ACTOR": "github-actions[bot]"},
        {**BENCHMARK_ENV, "GITHUB_REF_NAME": "main"},
        {**BENCHMARK_ENV, "GITHUB_RUN_ATTEMPT": "2"},
        {**BENCHMARK_ENV, "GITHUB_WORKFLOW": "Other Workflow"},
        {**BENCHMARK_ENV, "GITHUB_JOB": "other-job"},
    )
    for env in cases:
        assert manual_paid_brave_block_reason(env) == MANUAL_PAID_BRAVE_BLOCK_REASON


def test_explicit_benchmark_override_is_still_scoped_to_operator_main_or_benchmark() -> None:
    main_env = {
        **BENCHMARK_ENV,
        "GITHUB_REF_NAME": "main",
        "OPPORTUNITY_ALLOW_PAID_BRAVE_BENCHMARK": "true",
    }
    assert manual_paid_brave_block_reason(main_env) is None
    assert manual_paid_brave_incremental_budget(main_env)["max_requests"] == 60

    wrong_actor = {**main_env, "GITHUB_ACTOR": "github-actions[bot]"}
    assert manual_paid_brave_block_reason(wrong_actor) == MANUAL_PAID_BRAVE_BLOCK_REASON

    wrong_branch = {**main_env, "GITHUB_REF_NAME": "feature/random"}
    assert manual_paid_brave_block_reason(wrong_branch) == MANUAL_PAID_BRAVE_BLOCK_REASON
