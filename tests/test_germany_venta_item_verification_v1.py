from __future__ import annotations

from opportunity_engine.discovery.germany_venta_active import VentaActiveWatchResult
from opportunity_engine.discovery.germany_venta_item_verification import (
    apply_venta_exact_item_verification,
    strict_clothing_title,
)


ITEM_URL = (
    "https://auction.venta24.de/item/id/6001_1_24_Damenjacken_55001.html"
)


class _FakeResponse:
    def __init__(self, url: str, text: str) -> None:
        self.url = url
        self.status_code = 200
        self.encoding = "utf-8"
        self.content = text.encode("utf-8")
        self.headers = {"content-type": "text/html; charset=utf-8"}

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"unexpected URL: {url}")
        return _FakeResponse(url, self.pages[url])


def _result(candidate: dict) -> VentaActiveWatchResult:
    diagnostics = {
        "catalog_runs": [
            {
                "opportunity_identity": candidate["opportunity_identity"],
                "full_catalog_clothing_scope": False,
            }
        ],
        "clothing_catalog_count": 1,
        "clothing_child_lot_count": len(candidate.get("child_lots") or []),
        "observed_bulk_lot_count": sum(
            bool(item.get("bulk_evidence")) for item in candidate.get("child_lots") or []
        ),
        "promoted_bulk_lot_count": 0,
    }
    report = {
        "venta_active": diagnostics,
        "source_adapter": {
            "parent_candidate_count": 1,
            "child_lot_count": diagnostics["clothing_child_lot_count"],
            "observed_bulk_lot_count": diagnostics["observed_bulk_lot_count"],
            "promoted_bulk_candidate_count": 0,
            "single_garment_candidate_count": 0,
        },
        "false_positive_guard_triggered": 0,
    }
    discovery = {
        "all_discovered_candidates": [candidate],
        "discovery_top5": [],
        "search_run_report": report,
        "source_adapter": report["source_adapter"],
    }
    return VentaActiveWatchResult(discovery_result=discovery, diagnostics=diagnostics)


def test_fixture_compounds_are_not_clothing_titles() -> None:
    assert strict_clothing_title("Kleiderhaken, wandmontiert") is False
    assert strict_clothing_title("5 Kleiderstangen, fahrbar") is False
    assert strict_clothing_title("Kleiderständer aus Metall") is False
    assert strict_clothing_title("24 Damenjacken") is True
    assert strict_clothing_title("20 Damenkleider") is True


def test_today_style_kleiderstangen_false_positive_is_removed_without_item_request() -> None:
    candidate = {
        "opportunity_identity": "venta-auction:5385",
        "child_lots": [
            {
                "object_id": "54661",
                "canonical_url": "https://auction.venta24.de/item/id/5385_851_1_Kleiderhaken_wandmontiert_54661.html",
                "title": "Kleiderhaken, wandmontiert",
                "quantity": 1,
                "listing_status": "ACTIVE",
                "clothing_terms": ["kleider"],
                "bulk_evidence": False,
                "ordinary_single_garment": True,
            },
            {
                "object_id": "55008",
                "canonical_url": "https://auction.venta24.de/item/id/5385_1311_5_Kleiderstangen_fahrbar_55008.html",
                "title": "Kleiderstangen, fahrbar",
                "quantity": 5,
                "listing_status": "ACTIVE",
                "clothing_terms": ["kleider"],
                "bulk_evidence": True,
                "ordinary_single_garment": False,
            },
        ],
        "missing_information": ["exact item-page verification for observed bulk clothing lots"],
    }
    session = _FakeSession({})

    corrected = apply_venta_exact_item_verification(_result(candidate), session=session)

    assert corrected.discovery_result["all_discovered_candidates"] == []
    assert session.calls == []
    diagnostics = corrected.discovery_result["search_run_report"]["venta_active"]
    assert diagnostics["lexical_non_clothing_lot_count"] == 2
    assert diagnostics["clothing_catalog_count"] == 0
    assert corrected.discovery_result["search_run_report"]["no_opportunities_found"] is True


def test_exact_bulk_item_page_extracts_source_backed_shipping_fields() -> None:
    candidate = {
        "opportunity_identity": "venta-auction:6001",
        "title": "Modehaus inventory auction",
        "location": None,
        "child_lots": [
            {
                "object_id": "55001",
                "canonical_url": ITEM_URL,
                "title": "Damenjacken",
                "quantity": 24,
                "listing_status": "ACTIVE",
                "clothing_terms": ["jacken"],
                "bulk_evidence": True,
                "ordinary_single_garment": False,
                "opportunity_identity": "venta-object:55001",
            }
        ],
        "missing_information": [
            "exact item-page verification for observed bulk clothing lots",
            "cross-border logistics basis",
            "documented final payable price",
        ],
        "verification": [],
    }
    page = """
    <!doctype html><html><body>
      <h1>6001.1 =&gt; 24 Damenjacken</h1>
      <p>Standort | Lagerstr. 4 58095 Hagen</p>
      <p>Gesamtgewicht | 120 kg</p>
      <p>Abmessungen | 120 x 80 x 100 cm</p>
      <p>Paletten | 2</p>
      <p>Startpreis | 500,00 EUR</p>
      <p>Aktuelles Gebot | 650,00 EUR</p>
      <p>Aufgeld | 18 %</p>
      <p>zzgl. 19 % MwSt.</p>
    </body></html>
    """
    session = _FakeSession({ITEM_URL: page})

    corrected = apply_venta_exact_item_verification(_result(candidate), session=session)

    retained = corrected.discovery_result["all_discovered_candidates"]
    assert len(retained) == 1
    item = retained[0]
    assert item["exact_item_page_verified"] is True
    assert item["source_item_url"] == ITEM_URL
    assert item["source_postal_code"] == "58095"
    assert item["source_city"] == "Hagen"
    assert item["weight_kg"] == 120.0
    assert item["length_cm"] == 120.0
    assert item["width_cm"] == 80.0
    assert item["height_cm"] == 100.0
    assert item["pallet_count"] == 2
    assert item["source_start_or_minimum_price_eur"] == 500.0
    assert item["source_displayed_bid_eur"] == 650.0
    assert item["buyer_premium_percent"] == 18.0
    assert item["vat_percent"] == 19.0
    assert item["shipment_input_missing"] == []
    assert item["location"] == "Lagerstr. 4 58095 Hagen"
    assert "exact item-page verification for observed bulk clothing lots" not in item["missing_information"]
    assert item["missing_information"] == [
        "cross-border logistics basis",
        "documented final payable price",
    ]
    diagnostics = corrected.discovery_result["search_run_report"]["venta_active"]
    assert diagnostics["exact_item_pages_requested"] == 1
    assert diagnostics["exact_item_pages_verified"] == 1
    assert diagnostics["verified_bulk_lot_count"] == 1
    assert diagnostics["exact_item_verification_errors"] == []
