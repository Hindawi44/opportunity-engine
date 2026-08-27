from pathlib import Path

import pytest

from opportunity_engine.discovery.search_provider_role_policy import (
    BRAVE,
    BRAVE_SIGNAL_ONLY_ROLE,
    CLOTHING_INVENTORY_DISCOVERY,
    EARLY_MARKET_SIGNAL,
    EXACT_LOT,
    EXA,
    EXA_PRIMARY_ROLE,
    FABRIC_PROCUREMENT,
    primary_provider_for_intent,
    production_routing_snapshot,
    provider_allowed_for_intent,
    provider_role,
    require_provider_for_intent,
)


ROOT = Path(__file__).resolve().parents[1]


def test_provider_roles_match_controlled_comparison_decision():
    assert provider_role(EXA).role == EXA_PRIMARY_ROLE
    assert provider_role(BRAVE).role == BRAVE_SIGNAL_ONLY_ROLE

    assert primary_provider_for_intent(EXACT_LOT) == EXA
    assert primary_provider_for_intent(CLOTHING_INVENTORY_DISCOVERY) == EXA
    assert primary_provider_for_intent(FABRIC_PROCUREMENT) == EXA
    assert primary_provider_for_intent(EARLY_MARKET_SIGNAL) == BRAVE


def test_brave_fails_closed_outside_early_signal_role():
    assert provider_allowed_for_intent(BRAVE, EARLY_MARKET_SIGNAL) is True
    assert provider_allowed_for_intent(BRAVE, EXACT_LOT) is False
    assert provider_allowed_for_intent(BRAVE, CLOTHING_INVENTORY_DISCOVERY) is False
    assert provider_allowed_for_intent(BRAVE, FABRIC_PROCUREMENT) is False

    for intent in (EXACT_LOT, CLOTHING_INVENTORY_DISCOVERY, FABRIC_PROCUREMENT):
        with pytest.raises(RuntimeError, match="SEARCH_PROVIDER_ROLE_BLOCKED"):
            require_provider_for_intent(BRAVE, intent)


def test_exa_remains_allowed_for_exact_lot_and_procurement():
    for intent in (EXACT_LOT, CLOTHING_INVENTORY_DISCOVERY, FABRIC_PROCUREMENT):
        require_provider_for_intent(EXA, intent)


def test_routing_snapshot_is_machine_readable_and_non_promoting():
    snapshot = production_routing_snapshot()
    assert snapshot["exact_lot_primary_provider"] == EXA
    assert snapshot["fabric_procurement_primary_provider"] == EXA
    assert snapshot["early_market_signal_provider"] == BRAVE
    assert snapshot["brave_signal_only"] is True
    assert snapshot["brave_exact_lot_allowed"] is False
    assert snapshot["automatic_provider_activation"] is False
    assert snapshot["automatic_opportunity_promotion"] is False


def test_canonical_production_paths_cannot_silently_swap_provider_roles():
    exact_lot_runner = (ROOT / "scripts/run_exa_exact_lot_checkpoint.py").read_text(
        encoding="utf-8"
    )
    unified_runtime = (
        ROOT / "src/opportunity_engine/discovery/unified_search_runtime_cli_hook.py"
    ).read_text(encoding="utf-8")
    brave_radar = (
        ROOT / "src/opportunity_engine/discovery/brave_market_signal_radar.py"
    ).read_text(encoding="utf-8")

    assert "ExaSearchProvider" in exact_lot_runner
    assert "BraveSearchProvider" not in exact_lot_runner

    assert "ExaSearchProvider" in unified_runtime
    assert 'cycle["primary_search_provider"] = "exa"' in unified_runtime

    assert "BraveSearchProvider" in brave_radar
    assert '"signal_only": True' in brave_radar
    assert '"not_an_opportunity": True' in brave_radar
