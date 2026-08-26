from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_norway_route_diversity", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_norway_keeps_three_primary_queries_with_one_auction_listing_route() -> None:
    module = _load_script()
    queries = module.MARKET_EXACT_LOT_QUERY_PACKS["NO"]

    assert len(queries) == 3
    assert queries == (
        "Norge klær vareparti nettauksjon auksjon plagg til salgs pris stk",
        "Norge overskuddslager klær til salgs vareparti",
        "Norge kleslager restparti engros mote",
    )


def test_norway_alternative_route_stays_market_domain_and_source_neutral() -> None:
    module = _load_script()
    query = module.MARKET_EXACT_LOT_QUERY_PACKS["NO"][0]

    assert _market_anchored(query, "NO")
    assert classify_project_domain(text=query) == CLOTHING_INVENTORY
    assert "site:" not in query.casefold()
    assert "finn" not in query.casefold()
    assert "auksjonen.no" not in query.casefold()
    assert "nettauksjon" in query.casefold()
    assert "auksjon" in query.casefold()
    assert "vareparti" in query.casefold()
    assert "pris" in query.casefold()
    assert "stk" in query.casefold()
