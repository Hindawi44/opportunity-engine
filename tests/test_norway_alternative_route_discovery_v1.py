from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_norway_route_diversity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_norway_uses_two_proven_source_neutral_primary_queries() -> None:
    queries = _load_script().MARKET_EXACT_LOT_QUERY_PACKS["NO"]
    assert queries == (
        "Norge klær vareparti nettauksjon konkursbo lager pris antall stk",
        "Norge arbeidsklær overskuddsvarer auksjon høyeste bud stk",
    )


def test_norway_queries_stay_market_domain_and_source_neutral() -> None:
    queries = _load_script().MARKET_EXACT_LOT_QUERY_PACKS["NO"]
    assert len(queries) == 2
    for query in queries:
        assert _market_anchored(query, "NO")
        assert classify_project_domain(text=query) == CLOTHING_INVENTORY
        assert "site:" not in query.casefold()
        assert "finn" not in query.casefold()
        assert "auksjonen.no" not in query.casefold()
    assert all(token in queries[0].casefold() for token in ("nettauksjon", "konkursbo", "pris", "antall"))
    assert all(token in queries[1].casefold() for token in ("arbeidsklær", "overskuddsvarer", "auksjon", "stk"))
