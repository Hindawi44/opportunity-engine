from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_anchor_outcome", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lot(url: str, query: str) -> dict:
    return {
        "url": url,
        "final_url": url,
        "query": query,
    }


def _anchor_query(
    query: str,
    *,
    anchor_type: str,
    anchor_value: str,
    anchor_origin: str,
) -> dict:
    return {
        "query": query,
        "query_stage": "COMMERCIAL_ANCHOR",
        "commercial_anchor": {
            "type": anchor_type,
            "value": anchor_value,
            "origin": anchor_origin,
            "qualification_evidence": False,
        },
    }


def test_outcome_evidence_credits_only_anchor_query_that_added_strict_lot() -> None:
    module = _load_runner()
    first_query = "Deutschland Bekleidung Salzmann Restwaren Restposten Großhandel Lager zu verkaufen"
    second_query = "Deutschland Bekleidung Jack & Jones Restposten Großhandel Lager zu verkaufen"
    pre = [_lot("https://example.test/product/existing", "primary query")]
    final = [
        *pre,
        _lot("https://example.test/product/new-1", first_query),
        _lot("https://example.test/product/new-2", first_query),
    ]

    evidence = module._commercial_anchor_outcome_evidence(
        market="DE",
        query_rows=[
            _anchor_query(
                first_query,
                anchor_type="WHOLESALER",
                anchor_value="Salzmann Restwaren",
                anchor_origin="EVIDENCE_BACKED_MARKET_ENTITY_V1",
            ),
            _anchor_query(
                second_query,
                anchor_type="BRAND",
                anchor_value="Jack & Jones",
                anchor_origin="EVIDENCE_BACKED_MARKET_ENTITY_V1",
            ),
        ],
        pre_anchor_exact_lots=pre,
        final_exact_lots=final,
    )

    assert evidence["status"] == "SUCCESS"
    assert evidence["project_domain"] == CLOTHING_INVENTORY
    assert evidence["added_strict_exact_lot_count"] == 2
    assert evidence["attributed_added_strict_exact_lot_count"] == 2
    assert evidence["unattributed_added_strict_exact_lot_count"] == 0
    assert evidence["attribution_complete"] is True
    assert evidence["successful_outcome_count"] == 1

    salzmann, jack = evidence["outcomes"]
    assert salzmann["anchor_value"] == "Salzmann Restwaren"
    assert salzmann["anchor_origin"] == "EVIDENCE_BACKED_MARKET_ENTITY_V1"
    assert salzmann["outcome"] == "STRICT_EXACT_LOT_SUCCESS"
    assert salzmann["strict_exact_lot_added_count"] == 2
    assert salzmann["strict_exact_lot_urls"] == [
        "https://example.test/product/new-1",
        "https://example.test/product/new-2",
    ]
    assert jack["outcome"] == "NO_NEW_STRICT_EXACT_LOT"
    assert jack["strict_exact_lot_added_count"] == 0

    for row in evidence["outcomes"]:
        assert row["anchor_is_qualification_evidence"] is False
        assert row["learning_evidence_only"] is True
        assert row["automatic_query_activation"] is False
        assert row["automatic_source_promotion"] is False
        assert row["production_query_mutation"] is False
        assert row["production_mutation"] is False


def test_missing_query_provenance_never_grants_anchor_credit() -> None:
    module = _load_runner()
    anchor_query = "Nederland kleding Pronovias restpartij groothandel voorraad te koop"
    new_url = "https://example.test/product/unattributed"

    evidence = module._commercial_anchor_outcome_evidence(
        market="NL",
        query_rows=[
            _anchor_query(
                anchor_query,
                anchor_type="BRIDAL",
                anchor_value="Pronovias",
                anchor_origin="CONTROLLED_GLOBAL_CATALOG_V1",
            )
        ],
        pre_anchor_exact_lots=[],
        final_exact_lots=[_lot(new_url, "")],
    )

    assert evidence["added_strict_exact_lot_count"] == 1
    assert evidence["attributed_added_strict_exact_lot_count"] == 0
    assert evidence["unattributed_added_strict_exact_lot_count"] == 1
    assert evidence["unattributed_added_strict_exact_lot_urls"] == [new_url]
    assert evidence["attribution_complete"] is False
    assert evidence["successful_outcome_count"] == 0
    assert evidence["outcomes"][0]["outcome"] == "NO_NEW_STRICT_EXACT_LOT"


def test_no_anchor_stage_produces_valid_zero_learning_evidence() -> None:
    module = _load_runner()
    evidence = module._commercial_anchor_outcome_evidence(
        market="FR",
        query_rows=[{"query": "France vêtements stock", "query_stage": "PRIMARY"}],
        pre_anchor_exact_lots=[_lot("https://example.test/product/1", "France vêtements stock")],
        final_exact_lots=[_lot("https://example.test/product/1", "France vêtements stock")],
    )

    assert evidence["status"] == "VALID_ZERO"
    assert evidence["outcome_count"] == 0
    assert evidence["successful_outcome_count"] == 0
    assert evidence["added_strict_exact_lot_count"] == 0
    assert evidence["anchor_is_qualification_evidence"] is False
    assert evidence["learning_evidence_only"] is True
