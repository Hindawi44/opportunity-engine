"""Fail-closed guard for paid Brave discovery during GitHub automation.

Scheduled production discovery remains enabled. Diagnostic/manual
``workflow_dispatch`` runs must not spend Brave credit unless an operator
explicitly opts in, uses the dedicated tightly bounded maturity-benchmark
branch, or the run is the legacy bounded $10 Brave test branch.

Repository ``push`` runs are also zero-cost by default. A push may use Brave only
when the specific job sets the explicit push override. This prevents commit or
merge-message based CI validation from silently consuming Brave credit.

Auto-dispatched live-proof/checkpoint runs are intentionally zero-cost. They are
workflow_dispatch executions too, so they remain blocked exactly like any other
manual run unless a dedicated benchmark contract is satisfied.
"""
from __future__ import annotations

import os
from typing import Any, Mapping


MANUAL_PAID_BRAVE_OVERRIDE = "OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL"
MANUAL_PAID_BRAVE_BENCHMARK_OVERRIDE = "OPPORTUNITY_ALLOW_PAID_BRAVE_BENCHMARK"
MANUAL_PAID_BRAVE_BLOCK_REASON = "MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED"
PUSH_PAID_BRAVE_OVERRIDE = "OPPORTUNITY_ALLOW_PAID_BRAVE_PUSH"
PUSH_PAID_BRAVE_BLOCK_REASON = "PUSH_WORKFLOW_PAID_BRAVE_BLOCKED"
AUTOMATED_CHECKPOINT_WORKFLOW = "Multi-Market Daily Operator Checkpoint"
AUTOMATED_CHECKPOINT_JOB = "operator-read-only-checkpoint"

# Dedicated one-shot operator branch used only for the controlled Brave
# comparison after the account ceiling is temporarily raised. The observed
# account economics are $30 / 6000 requests = $0.005/request, so 2000 outbound
# request attempts are a conservative $10 incremental ceiling at the current
# plan price. A rerun attempt is deliberately not authorized.
MANUAL_PAID_BRAVE_TEST_BRANCH = "brave-paid-10usd-test-v1"
MANUAL_PAID_BRAVE_TEST_ACTOR = "hindawi44"
MANUAL_PAID_BRAVE_TEST_BUDGET_ID = "BRAVE_MANUAL_10_USD_V1"
MANUAL_PAID_BRAVE_TEST_MAX_REQUESTS = 2000
MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD = 0.005

# Search-engine maturity benchmark. This is intentionally much smaller than the
# legacy $10 comparison budget: 60 outbound attempts at the observed unit cost
# cap incremental Brave spend at $0.30. The benchmark is authorized only on the
# dedicated branch (or a future explicit workflow opt-in), for the repository
# operator, on the first run attempt. Normal manual main runs remain zero-cost.
MANUAL_PAID_BRAVE_BENCHMARK_BRANCH = "brave-maturity-benchmark-v1"
MANUAL_PAID_BRAVE_BENCHMARK_BUDGET_ID = "BRAVE_MANUAL_MATURITY_BENCHMARK_V1"
MANUAL_PAID_BRAVE_BENCHMARK_MAX_REQUESTS = 60
BENCHMARK_ALLOWED_ACTORS = frozenset({"hindawi44", "github-actions[bot]"})

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _environment(environment: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return environment if environment is not None else os.environ


def _truthy_env(env: Mapping[str, str], name: str) -> bool:
    value = str(env.get(name) or "").strip().casefold()
    return value in _TRUTHY


def _manual_override_enabled(env: Mapping[str, str]) -> bool:
    return _truthy_env(env, MANUAL_PAID_BRAVE_OVERRIDE)


def _push_override_enabled(env: Mapping[str, str]) -> bool:
    return _truthy_env(env, PUSH_PAID_BRAVE_OVERRIDE)


def _ref_name(env: Mapping[str, str]) -> str:
    direct = str(env.get("GITHUB_REF_NAME") or "").strip()
    if direct:
        return direct
    ref = str(env.get("GITHUB_REF") or "").strip()
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


def _first_run_attempt(env: Mapping[str, str]) -> bool:
    try:
        attempt = int(str(env.get("GITHUB_RUN_ATTEMPT") or "1").strip())
    except ValueError:
        return False
    return attempt == 1


def _manual_bounded_test_branch_allowed(env: Mapping[str, str]) -> bool:
    """Authorize exactly one first-attempt bounded Brave comparison branch."""
    if str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold() != "workflow_dispatch":
        return False
    if str(env.get("GITHUB_WORKFLOW") or "").strip() != AUTOMATED_CHECKPOINT_WORKFLOW:
        return False
    if str(env.get("GITHUB_JOB") or "").strip() != AUTOMATED_CHECKPOINT_JOB:
        return False
    if str(env.get("GITHUB_ACTOR") or "").strip().casefold() != MANUAL_PAID_BRAVE_TEST_ACTOR:
        return False
    if _ref_name(env) != MANUAL_PAID_BRAVE_TEST_BRANCH:
        return False
    return _first_run_attempt(env)


def _manual_bounded_benchmark_allowed(env: Mapping[str, str]) -> bool:
    """Authorize one explicitly bounded search-engine maturity benchmark."""
    ref_name = _ref_name(env)
    branch_opt_in = ref_name == MANUAL_PAID_BRAVE_BENCHMARK_BRANCH
    explicit_opt_in = _truthy_env(env, MANUAL_PAID_BRAVE_BENCHMARK_OVERRIDE)
    if not (branch_opt_in or explicit_opt_in):
        return False
    if str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold() != "workflow_dispatch":
        return False
    if str(env.get("GITHUB_WORKFLOW") or "").strip() != AUTOMATED_CHECKPOINT_WORKFLOW:
        return False
    if str(env.get("GITHUB_JOB") or "").strip() != AUTOMATED_CHECKPOINT_JOB:
        return False
    actor = str(env.get("GITHUB_ACTOR") or "").strip().casefold()
    if actor not in BENCHMARK_ALLOWED_ACTORS:
        return False
    if explicit_opt_in and ref_name not in {"main", MANUAL_PAID_BRAVE_BENCHMARK_BRANCH}:
        return False
    return _first_run_attempt(env)


def _blocked_message(reason: str) -> str:
    if reason == PUSH_PAID_BRAVE_BLOCK_REASON:
        return (
            f"{reason}: GitHub push runs are zero-cost by default; set "
            f"{PUSH_PAID_BRAVE_OVERRIDE}=true only in an explicitly authorized paid-live job"
        )
    return (
        f"{reason}: manual GitHub runs are zero-cost by default; use a dedicated "
        "bounded benchmark contract or set "
        f"{MANUAL_PAID_BRAVE_OVERRIDE}=true only for an intentional paid run"
    )


def manual_paid_brave_incremental_budget(
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Return the fixed manual budget or fail closed before Brave transport.

    ``workflow_dispatch`` executions are paid only via the explicit manual
    override, the $0.30 maturity benchmark contract, or the dedicated
    first-attempt comparison branch. ``push`` runs are blocked unless their job
    explicitly opts in via ``PUSH_PAID_BRAVE_OVERRIDE``. Scheduled production
    runs are intentionally unaffected.

    This function is called immediately before every default Brave transport
    attempt, so an unauthorized workflow cannot bypass higher-level guards.
    """
    env = _environment(environment)
    event_name = str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold()

    if event_name == "push":
        if not _push_override_enabled(env):
            raise RuntimeError(_blocked_message(PUSH_PAID_BRAVE_BLOCK_REASON))
        return None

    if event_name != "workflow_dispatch":
        return None

    if _manual_bounded_benchmark_allowed(env):
        return {
            "budget_id": MANUAL_PAID_BRAVE_BENCHMARK_BUDGET_ID,
            "max_requests": MANUAL_PAID_BRAVE_BENCHMARK_MAX_REQUESTS,
            "observed_unit_cost_usd": MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD,
            "max_incremental_cost_usd": (
                MANUAL_PAID_BRAVE_BENCHMARK_MAX_REQUESTS
                * MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD
            ),
        }

    if not (_manual_override_enabled(env) or _manual_bounded_test_branch_allowed(env)):
        raise RuntimeError(_blocked_message(MANUAL_PAID_BRAVE_BLOCK_REASON))
    return {
        "budget_id": MANUAL_PAID_BRAVE_TEST_BUDGET_ID,
        "max_requests": MANUAL_PAID_BRAVE_TEST_MAX_REQUESTS,
        "observed_unit_cost_usd": MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD,
        "max_incremental_cost_usd": (
            MANUAL_PAID_BRAVE_TEST_MAX_REQUESTS
            * MANUAL_PAID_BRAVE_OBSERVED_UNIT_COST_USD
        ),
    }


def manual_paid_brave_block_reason(
    environment: Mapping[str, str] | None = None,
    *,
    market: str | None = None,
    source: str | None = None,
    query_budget: int | None = None,
) -> str | None:
    """Return a block reason for non-authorized manual or push GitHub runs."""
    del market, source, query_budget
    env = _environment(environment)
    event_name = str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold()

    if event_name == "push":
        return None if _push_override_enabled(env) else PUSH_PAID_BRAVE_BLOCK_REASON

    if event_name != "workflow_dispatch":
        return None

    if _manual_bounded_benchmark_allowed(env):
        return None

    if _manual_override_enabled(env):
        return None

    if _manual_bounded_test_branch_allowed(env):
        return None

    return MANUAL_PAID_BRAVE_BLOCK_REASON


def ensure_paid_brave_allowed(
    environment: Mapping[str, str] | None = None,
    *,
    market: str | None = None,
    source: str | None = None,
    query_budget: int | None = None,
) -> None:
    """Raise before a paid Brave-backed discovery runner can make requests."""
    reason = manual_paid_brave_block_reason(
        environment,
        market=market,
        source=source,
        query_budget=query_budget,
    )
    if reason is None:
        return
    raise RuntimeError(_blocked_message(reason))
