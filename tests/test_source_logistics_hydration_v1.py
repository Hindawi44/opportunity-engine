from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.source_logistics_hydration import (
    hydrate_selected_source_logistics,
)
from opportunity_engine.logistics.official_route_freight import (
    _location_input,
    _shipment_input,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_selected_venta_candidate_hydrates_unified_item_for_existing_freight_layer(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "multi-market-daily-operator-checkpoint"
    input_dir = tmp_path / "multi-market-inputs" / "de-venta"
    output_dir.mkdir(parents=True)

    intelligence_id = "intelligence-item:venta"
    _write(
        output_dir / "unified-intelligence-items.json",
        {
            "items": [
                {
                    "intelligence_id": intelligence_id,
                    "stable_identity": "opportunity:venta-auction:6001",
                    "record_kind": "CANONICAL_OPPORTUNITY",
                    "source_country": "DE",
                    "source_url": "https://auction.venta24.de/catalog/6001",
                    "location": None,
                    "details": {"opportunity_identity": "venta-auction:6001"},
                }
            ]
        },
    )
    _write(
        output_dir / "unified-market-cases.json",
        {
            "cases": [
                {
                    "case_id": "case:venta",
                    "item_ids": [intelligence_id],
                }
            ]
        },
    )
    _write(
        input_dir / "all-discovered-candidates.json",
        [
            {
                "opportunity_identity": "venta-auction:6001",
                "source_urls": ["https://auction.venta24.de/catalog/6001"],
                "location": "Lagerstr. 4 58095 Hagen",
                "source_postal_code": "58095",
                "source_city": "Hagen",
                "weight_kg": 120.0,
                "length_cm": 120.0,
                "width_cm": 80.0,
                "height_cm": 100.0,
                "pallet_count": 2,
                "source_item_url": "https://auction.venta24.de/item/55001",
                "exact_item_page_verified": True,
                "shipping_details_source": "VENTA_EXACT_ITEM_PAGE",
            }
        ],
    )
    brief = {"top_actionable_opportunity": {"case_id": "case:venta"}}

    report = hydrate_selected_source_logistics(output_dir, brief)

    assert report["status"] == "HYDRATED"
    assert report["source_page_fetch_performed"] is False
    assert report["estimated_values_added"] is False
    hydrated = json.loads(
        (output_dir / "unified-intelligence-items.json").read_text(encoding="utf-8")
    )["items"][0]
    assert hydrated["location"] == "Lagerstr. 4 58095 Hagen"
    assert hydrated["details"]["source_postal_code"] == "58095"
    assert hydrated["details"]["metadata"]["weight_kg"] == 120.0

    origin = _location_input(hydrated)
    shipment = _shipment_input(hydrated)
    assert origin["postal_code"] == "58095"
    assert origin["city"] == "Hagen"
    assert origin["precision"] == "POSTAL_CODE_LEVEL"
    assert shipment["weight_kg"] == 120.0
    assert shipment["pallet_count"] == 2
    assert shipment["length_cm"] == 120.0
    assert shipment["width_cm"] == 80.0
    assert shipment["height_cm"] == 100.0
