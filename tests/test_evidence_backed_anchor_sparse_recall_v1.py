from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    build_commercial_anchor_queries,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_sparse_anchor", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_backed_market_anchor_can_rescue_sparse_thin_discovery() -> None:
    module = _load_runner()
    anchors = build_commercial_anchor_queries(
        market="DE", project_domain=CLOTHING_INVENTORY
    )

    assert anchors
    assert anchors[0]["anchor_origin"] == "EVIDENCE_BACKED_MARKET_ENTITY_V1"
    assert module._should_expand_commercial_anchors(
        anchor_queries=anchors,
        strict_exact_lot_count=0,
        unique_discovery_hit_count=7,
    ) is True
    assert module._should_expand_commercial_anchors(
        anchor_queries=anchors,
        strict_exact_lot_count=3,
        unique_discovery_hit_count=7,
    ) is False


def test_global_anchor_stays_blocked_below_general_broadness_floor() -> None:
    module = _load_runner()
    anchors = build_commercial_anchor_queries(
        market="NL", project_domain=CLOTHING_INVENTORY
    )

    assert anchors
    assert anchors[0]["anchor_origin"] == "CONTROLLED_GLOBAL_CATALOG_V1"
    assert module._should_expand_commercial_anchors(
        anchor_queries=anchors,
        strict_exact_lot_count=0,
        unique_discovery_hit_count=7,
    ) is False
    assert module._should_expand_commercial_anchors(
        anchor_queries=anchors,
        strict_exact_lot_count=0,
        unique_discovery_hit_count=8,
    ) is True
