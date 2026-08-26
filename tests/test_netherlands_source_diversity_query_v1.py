from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"
EXPECTED_QUERY = (
    "Nederland kleding groothandel partij pakket pallet te koop prijs per stuk voorraad"
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_nl_source_diversity", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_netherlands_keeps_one_primary_query_with_alternative_b2b_route() -> None:
    module = _load_script()
    queries = module.MARKET_EXACT_LOT_QUERY_PACKS["NL"]

    assert queries == (EXPECTED_QUERY,)
    assert len(queries) == 1


def test_netherlands_diversity_query_stays_source_neutral_and_exact_lot_shaped() -> None:
    query = EXPECTED_QUERY
    folded = query.casefold()

    assert _market_anchored(query, "NL")
    assert classify_project_domain(text=query) == CLOTHING_INVENTORY
    assert "site:" not in folded
    assert "merkandi" not in folded
    assert "partijhandelaren" not in folded
    assert "marktplaats" not in folded
    assert "te koop" in folded
    assert "prijs" in folded
    assert "stuk" in folded
    assert "pakket" in folded
    assert "pallet" in folded
