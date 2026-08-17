"""Fail-closed guard for paid Brave discovery during manual GitHub runs.

Scheduled production discovery remains enabled.  A workflow_dispatch run is
considered a diagnostic/manual run and must not spend Brave credit unless an
operator explicitly opts in outside the default checkpoint path.
"""
from __future__ import annotations

import os
from typing import Mapping


MANUAL_PAID_BRAVE_OVERRIDE = "OPPORTUNITY_ALLOW_PAID_BRAVE_MANUAL"
MANUAL_PAID_BRAVE_BLOCK_REASON = "MANUAL_WORKFLOW_PAID_BRAVE_BLOCKED"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _environment(environment: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return environment if environment is not None else os.environ


def manual_paid_brave_block_reason(
    environment: Mapping[str, str] | None = None,
) -> str | None:
    """Return a block reason only for non-opted-in workflow_dispatch runs."""
    env = _environment(environment)
    event_name = str(env.get("GITHUB_EVENT_NAME") or "").strip().casefold()
    if event_name != "workflow_dispatch":
        return None

    override = str(env.get(MANUAL_PAID_BRAVE_OVERRIDE) or "").strip().casefold()
    if override in _TRUTHY:
        return None
    return MANUAL_PAID_BRAVE_BLOCK_REASON


def ensure_paid_brave_allowed(
    environment: Mapping[str, str] | None = None,
) -> None:
    """Raise before a paid Brave-backed discovery runner can make requests."""
    reason = manual_paid_brave_block_reason(environment)
    if reason is None:
        return
    raise RuntimeError(
        f"{reason}: manual GitHub runs are zero-cost by default; "
        f"set {MANUAL_PAID_BRAVE_OVERRIDE}=true only for an intentional paid run"
    )
