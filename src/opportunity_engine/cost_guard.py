"""Fail-closed guard for paid Brave discovery during manual GitHub runs.

Scheduled production discovery remains enabled. A workflow_dispatch run is
considered a diagnostic/manual run and must not spend Brave credit unless an
operator explicitly opts in, the run is the dedicated bounded $10 Brave test
branch, or the request is one of the already-bounded direct source scans executed
by the repository's auto-dispatched operator checkpoint.

The automated-checkpoint exception is deliberately narrow: workflow, actor, job,
market, source and query budget must all match the allow-list below. Other Brave
callers in the same job remain blocked because they do not provide a bounded
source scope.
"""
from __future__ import annotations

import os
from typing import Any, Mapping


MANUAL_PAID_BRAVE_OVERRIDE = "OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL"
MANUAL_PAID_BRAVE_BLOCK_REASON = "MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED"
AUTOMATED_CHECKPOINT_WORKFLOW = "Multi-Market Daily Operator Checkpoint"
AUTOMATED_CHECKPOINT_JOB = "operator-read-only-checkpoint"
AUTOMATED_CHECKPOINT_ACTOR = "github-actions[bot]"
AUTOMATED_CHECKPOINT_BOUNDED_SOURCE_BUDGETS = {
    ("SE", "blinto"): 8,
    ("SE", "klaravik"): 8,
    ("SE", "psauction"): 8,
    ("DE", "sen-sen"): 6,
}

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

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _environment(environment: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return environment if environment is not None else os.environ


def _manual_override_enabled(env: Mapping[str, str]) -> bool:
    value = str(env.get(MANUAL_PAID_BRAVE_OVERRIDE) or "").strip().casefold()
    return value in _TRUTHY


def _ref_name(env: Mapping[str, str]) -> str:
    direct = str(env.get("GITHUB_REF_NAME") or "").strip()
    if direct:
        return direct
    ref = str(env.get("GITHUB_REF") or "").strip()
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


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
    try:
        attempt = int(str(env.get("GITHUB_RUN_ATTEMPT") or "1").strip())
    except ValueError:
        return False
    return attempt == 1


def _automated_checkpoint_bounded_scope_allowed(
    env: Mapping[str, str],
    *,
    market: str | None,
    source: str | None,
    query_budget: int | None,
) -> bool:
    """Allow only the fixed direct-source scans in an auto-dispatched checkpoint."""
    if str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold() != "workflow_dispatch":
        return False
    if str(env.get("GITHUB_WORKFLOW") or "").strip() != AUTOMATED_CHECKPOINT_WORKFLOW:
        return False
    if str(env.get("GITHUB_JOB") or "").strip() != AUTOMATED_CHECKPOINT_JOB:
        return False
    if str(env.get("GITHUB_ACTOR") or "").strip().casefold() != AUTOMATED_CHECKPOINT_ACTOR:
        return False

    market_code = str(market or "").strip().upper()
    source_key = str(source or "").strip().casefold()
    max_budget = AUTOMATED_CHECKPOINT_BOUNDED_SOURCE_BUDGETS.get(
        (market_code, source_key)
    )
    if max_budget is None:
        return False
    try:
        requested_budget = int(query_budget or 0)
    except (TypeError, ValueError):
        return False
    return 1 <= requested_budget <= max_budget


def manual_paid_brave_incremental_budget(
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Return the fixed $10 manual-run budget when paid Brave is explicitly enabled.

    The budget applies only to workflow_dispatch executions that are intentionally
    paid: either the explicit override or the dedicated first-attempt comparison
    branch. Scheduled runs and the bot's narrow direct-source exception are not
    part of this one-shot test budget.
    """
    env = _environment(environment)
    event_name = str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold()
    if event_name != "workflow_dispatch":
        return None
    if not (_manual_override_enabled(env) or _manual_bounded_test_branch_allowed(env)):
        return None
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
    """Return a block reason only for non-authorized workflow_dispatch runs."""
    env = _environment(environment)
    event_name = str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold()
    if event_name != "workflow_dispatch":
        return None

    if _manual_override_enabled(env):
        return None

    if _manual_bounded_test_branch_allowed(env):
        return None

    if _automated_checkpoint_bounded_scope_allowed(
        env,
        market=market,
        source=source,
        query_budget=query_budget,
    ):
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
    raise RuntimeError(
        f"{reason}: manual GitHub runs are zero-cost by default; "
        f"set {MANUAL_PAID_BRAVE_OVERRIDE}=true only for an intentional paid run"
    )
