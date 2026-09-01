from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.exa_shadow_page_verification import EXACT_LOT_CANDIDATE
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


def _load_runner():
    path = Path("scripts/run_exa_exact_lot_checkpoint.py")
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_dedupe_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(url: str) -> dict[str, object]:
    return {
        "classification": EXACT_LOT_CANDIDATE,
        "title": "Kläder restparti",
        "url": url,
        "final_url": url,
        "evidence": {
            "project_domain": CLOTHING_INVENTORY,
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def test_exact_lot_rows_dedupes_www_and_trailing_slash_variants() -> None:
    runner = _load_runner()
    verification = {
        "verified_pages": [
            _row("https://grossist.se/restpartier/1/20/parti/2359"),
            _row("https://www.grossist.se/restpartier/1/20/parti/2359/"),
        ]
    }
    rows = runner._exact_lot_rows(verification, {"exact_lots": []})
    assert len(rows) == 1
    assert rows[0]["url"] == "https://grossist.se/restpartier/1/20/parti/2359"


def test_identity_key_preserves_distinct_query_parameters() -> None:
    runner = _load_runner()
    first = runner._exact_lot_identity_key("https://www.example.com/item/42/?lot=1")
    second = runner._exact_lot_identity_key("https://example.com/item/42?lot=2")
    assert first == "https://example.com/item/42?lot=1"
    assert second == "https://example.com/item/42?lot=2"
    assert first != second


def test_identity_key_normalizes_default_https_port_only() -> None:
    runner = _load_runner()
    assert (
        runner._exact_lot_identity_key("https://www.example.com:443/item/42/")
        == "https://example.com/item/42"
    )
    assert (
        runner._exact_lot_identity_key("https://www.example.com:8443/item/42/")
        == "https://example.com:8443/item/42"
    )
