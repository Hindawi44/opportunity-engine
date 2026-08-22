from __future__ import annotations

from opportunity_engine.automatic_query_gap_miss_scout import _LIQUIDATION_MARKERS
from opportunity_engine.promoted_learned_core_discovery import _exact_query


def test_promoted_core_query_uses_calibrated_closure_hint_without_duplicating_verifier() -> None:
    query = _exact_query("avviklingssalg")

    # Live calibration proved that copying the whole strict verifier contract
    # into Brave kills recall. Search should retrieve likely closure pages;
    # the fetched source page remains responsible for proving inventory.
    assert query == '"avviklingssalg" "stenge butikken"'
    for marker in _LIQUIDATION_MARKERS:
        assert f'"{marker}"' not in query

    assert query != '"avviklingssalg"'
