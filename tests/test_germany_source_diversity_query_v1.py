from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_source_diversity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_germany_keeps_three_primary_queries_with_one_evidence_shaped_slot() -> None:
    module = _load_script()
    queries = module.MARKET_EXACT_LOT_QUERY_PACKS["DE"]

    assert len(queries) == 3
    assert queries[:2] == (
        "Deutschland Restposten Bekleidung Großhandel Lager",
        "Deutschland Sonderposten Kleidung zu verkaufen Großhandel",
    )
    assert queries[2] == "Deutschland Bekleidung Restposten Stück Preis Großhandel Angebot"


def test_germany_diversity_query_stays_market_domain_and_source_neutral() -> None:
    module = _load_script()
    query = module.MARKET_EXACT_LOT_QUERY_PACKS["DE"][2]

    assert _market_anchored(query, "DE")
    assert classify_project_domain(text=query) == CLOTHING_INVENTORY
    assert "site:" not in query.casefold()
    assert "stück" in query.casefold()
    assert "preis" in query.casefold()
    assert "angebot" in query.casefold()
