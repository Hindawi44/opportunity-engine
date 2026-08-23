from __future__ import annotations

from typing import Any


def learn_from_run(
    reasoning: dict[str, Any],
    evidence: dict[str, Any],
    final_rank: dict[str, Any],
    *,
    run_id: str,
    prior_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract reusable shadow-only patterns from one completed MIND FORGE run."""
    raise NotImplementedError("fast cross-run learning is not implemented yet")
