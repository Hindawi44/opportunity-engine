from __future__ import annotations

import importlib.util
from pathlib import Path

from opportunity_engine.discovery.exa_shadow_page_verification import EXACT_LOT_CANDIDATE
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY


def _load_runner():
    path = Path("scripts/run_exa_exact_lot_checkpoint.py")
    spec = importlib.util.spec_from_file_location("run_exa_exact_lot_checkpoint_fresh_preference_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_row(url: str, *, query: str = "") -> dict[str, object]:
    return {
        "classification": EXACT_LOT_CANDIDATE,
        "title": "Kläder restparti",
        "url": url,
        "final_url": url,
        "query": query,
        "provider": "exa",
        "evidence": {
            "project_domain": CLOTHING_INVENTORY,
            "page_subject_domain": CLOTHING_INVENTORY,
            "item_specific_url_evidence": True,
            "inventory_evidence": True,
            "direct_sale_evidence": True,
            "price_evidence": True,
            "quantity_evidence": True,
        },
    }


def _recovery_row(url: str) -> dict[str, object]:
    row = _strict_row(url)
    row["provider"] = "proven_route_recovery"
    row["retrieval_provenance"] = "PROVEN_ROUTE_RECOVERY"
    return row


def _multihop_row(url: str, *, query: str) -> dict[str, object]:
    row = _strict_row(url, query=query)
    row.pop("classification", None)
    return row


def test_fresh_current_exact_lot_replaces_cosmetic_recovery_duplicate() -> None:
    runner = _load_runner()
    query = "Sverige restparti kläder grossist lager"
    verification = {
        "verified_pages": [
            _strict_row(
                "https://cdon.se/produkt/parti-grossist-restparti-klader",
                query=query,
            ),
            _recovery_row("https://grossist.se/restpartier/1/20/parti/2359"),
            _recovery_row("https://www.grossist.se/restpartier/1/20/parti/2359/"),
        ]
    }
    multihop = {
        "exact_lots": [
            _multihop_row(
                "https://www.grossist.se/restpartier/1/20/parti/2359",
                query=query,
            )
        ]
    }

    rows = runner._exact_lot_rows(verification, multihop)

    assert len(rows) == 2
    grossist = next(row for row in rows if "grossist.se" in str(row.get("url")))
    assert grossist["provider"] == "exa"
    assert grossist["query"] == query
    assert grossist["exact_lot_origin"] == "MULTI_HOP"
    assert runner._is_recovery_exact_lot(grossist) is False

    snapshot = runner._fresh_coverage_snapshot(rows)
    assert snapshot["total_strict_exact_lot_count"] == 2
    assert snapshot["fresh_current_strict_exact_lot_count"] == 2
    assert snapshot["reverified_recovery_strict_exact_lot_count"] == 0
    assert snapshot["fresh_current_route_host_count"] == 2
    assert snapshot["fresh_current_route_hosts"] == ["cdon.se", "grossist.se"]


def test_recovery_never_replaces_existing_fresh_identity() -> None:
    runner = _load_runner()
    query = "Sverige restparti kläder grossist lager"
    fresh = _strict_row(
        "https://www.grossist.se/restpartier/1/20/parti/2359/",
        query=query,
    )
    recovery = _recovery_row("https://grossist.se/restpartier/1/20/parti/2359")

    rows = runner._exact_lot_rows(
        {"verified_pages": [fresh, recovery]},
        {"exact_lots": []},
    )

    assert len(rows) == 1
    assert rows[0]["provider"] == "exa"
    assert rows[0]["query"] == query
    assert runner._is_recovery_exact_lot(rows[0]) is False
