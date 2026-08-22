from __future__ import annotations

from opportunity_engine.automatic_query_gap_miss_scout import (
    _CLOSURE_MARKERS,
    _LIQUIDATION_MARKERS,
)
from opportunity_engine.promoted_learned_core_discovery import _exact_query


def test_promoted_core_query_requires_verifier_aligned_closure_and_inventory_context() -> None:
    query = _exact_query("avviklingssalg")

    assert query.startswith('"avviklingssalg" ')
    for marker in _CLOSURE_MARKERS:
        assert f'"{marker}"' in query
    for marker in _LIQUIDATION_MARKERS:
        assert f'"{marker}"' in query

    # Learned vocabulary narrows a stable commercial-event query; it must not
    # be sent as a standalone broad search again.
    assert query != '"avviklingssalg"'
