from pathlib import Path

runner = Path("scripts/run_exa_exact_lot_checkpoint.py")
text = runner.read_text(encoding="utf-8")
blocks = {
'''    "NO": (
        "Norge klær vareparti nettauksjon auksjon plagg til salgs pris stk",
        "Norge overskuddslager klær til salgs vareparti",
        "Norge kleslager restparti engros mote",
    ),''': '''    "NO": (
        "Norge klær vareparti nettauksjon konkursbo lager pris antall stk",
        "Norge arbeidsklær overskuddsvarer auksjon høyeste bud stk",
    ),''',
'''    "DE": (
        "Deutschland Restposten Bekleidung Großhandel Lager",
        "Deutschland Sonderposten Kleidung zu verkaufen Großhandel",
        "Deutschland Bekleidung Restposten Stück Preis Großhandel Angebot",
    ),''': '''    "DE": (
        "Deutschland Lagerware Bekleidung Mindestabnahme angebotene Menge Nettopreis Stück",
        "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück",
    ),''',
}
for old, new in blocks.items():
    if text.count(old) != 1:
        raise SystemExit("expected one query-pack block")
    text = text.replace(old, new)
runner.write_text(text, encoding="utf-8")

Path("tests/test_norway_alternative_route_discovery_v1.py").write_text('''from __future__ import annotations

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
''', encoding="utf-8")

Path("tests/test_germany_source_diversity_query_v1.py").write_text('''from __future__ import annotations

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


def test_germany_uses_two_proven_source_neutral_primary_queries() -> None:
    queries = _load_script().MARKET_EXACT_LOT_QUERY_PACKS["DE"]
    assert queries == (
        "Deutschland Lagerware Bekleidung Mindestabnahme angebotene Menge Nettopreis Stück",
        "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück",
    )


def test_germany_queries_stay_market_domain_and_source_neutral() -> None:
    queries = _load_script().MARKET_EXACT_LOT_QUERY_PACKS["DE"]
    assert len(queries) == 2
    for query in queries:
        assert _market_anchored(query, "DE")
        assert classify_project_domain(text=query) == CLOTHING_INVENTORY
        assert "site:" not in query.casefold()
        assert "restposten24" not in query.casefold()
        assert "grosshandel24" not in query.casefold()
    assert all(token in queries[0].casefold() for token in ("mindestabnahme", "menge", "nettopreis", "stück"))
    assert all(token in queries[1].casefold() for token in ("restposten", "grosshandel", "sonderposten", "preis", "menge"))
''', encoding="utf-8")

gate_path = Path("tests/test_de_evidence_backed_anchor_gate_v1.py")
gate = gate_path.read_text(encoding="utf-8")
old = "batch_sizes = (3, 2, 2, 2, 2)"
if gate.count(old) != 1:
    raise SystemExit("expected one DE seven-hit fixture")
gate_path.write_text(gate.replace(old, "batch_sizes = (4, 3, 2, 2)"), encoding="utf-8")
