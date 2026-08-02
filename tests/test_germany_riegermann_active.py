from __future__ import annotations

from dataclasses import dataclass

import pytest

from opportunity_engine.discovery.germany_riegermann_active import (
    DEFAULT_ACTIVE_AUCTIONS_URL,
    fetch_riegermann_auction_index,
    parse_riegermann_auction_index,
    run_riegermann_active_auction_discovery,
)
from opportunity_engine.discovery.germany_riegermann_live import (
    RiegermannLiveResult,
)


CABRINI_CATALOG = (
    "https://riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh?Lstatus=1"
)
CABRINI_INFORMATION = (
    "https://riegermann.de/de/2019_versteigerung_cabrini_gmbh/a/908"
)
VEHICLE_CATALOG = (
    "https://riegermann.de/de/objekte/au-999/"
    "fahrzeugversteigerung?Lstatus=1"
)
VEHICLE_INFORMATION = (
    "https://riegermann.de/de/fahrzeugversteigerung/a/999"
)


def _active_index_html() -> str:
    return f"""
    <!doctype html>
    <html><body><main>
      <h2>Laufende Auktionen</h2>
      <h3>Versteigerung Cabrini GmbH</h3>
      <div class="auction-entry">
        <h4>DE-55450 Langenlonsheim, An den Nahewiesen 12 + 13</h4>
        <p>Aktuell | Terminauktion | Jetzt bieten</p>
        <a href="{CABRINI_CATALOG}">Online-Katalog</a>
        <a href="{CABRINI_INFORMATION}">Informationen</a>
        <p>Vorräte und Waren aus dem Bereich Mode- und Lederbekleidung.</p>
        <p>Damenlederjacken, Lederhosen und Lederblazer.</p>
      </div>
      <h3>Fahrzeugversteigerung</h3>
      <div class="auction-entry">
        <h4>DE-13088 Berlin</h4>
        <p>Aktuell | Terminauktion | Jetzt bieten</p>
        <a href="{VEHICLE_CATALOG}">Online-Katalog</a>
        <a href="{VEHICLE_INFORMATION}">Informationen</a>
        <p>Transporter, Anhänger und Pkw.</p>
      </div>
    </main></body></html>
    """


def test_active_index_parser_finds_exact_auction_pairs_and_clothing_evidence():
    entries = parse_riegermann_auction_index(
        DEFAULT_ACTIVE_AUCTIONS_URL,
        _active_index_html(),
    )

    assert [entry.auction_id for entry in entries] == ["908", "999"]
    cabrini, vehicle = entries
    assert cabrini.title == "Versteigerung Cabrini GmbH"
    assert cabrini.catalog_url == CABRINI_CATALOG
    assert cabrini.information_url == CABRINI_INFORMATION
    assert cabrini.listing_status == "ACTIVE"
    assert cabrini.location == (
        "DE-55450 Langenlonsheim, An den Nahewiesen 12 + 13"
    )
    assert cabrini.clothing_evidence is True
    assert "lederbekleidung" in cabrini.clothing_terms
    assert vehicle.clothing_evidence is False


def test_active_index_parser_deduplicates_repeated_auction_links():
    source = _active_index_html().replace(
        f'<a href="{CABRINI_INFORMATION}">Informationen</a>',
        (
            f'<a href="{CABRINI_INFORMATION}">Informationen</a>'
            f'<a href="{CABRINI_CATALOG}&ord=title">Katalog erneut</a>'
        ),
    )

    entries = parse_riegermann_auction_index(DEFAULT_ACTIVE_AUCTIONS_URL, source)

    assert [entry.auction_id for entry in entries].count("908") == 1


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200
    content_type: str = "text/html; charset=utf-8"

    def __post_init__(self) -> None:
        self.content = self.text.encode("utf-8")
        self.encoding = "utf-8"
        self.headers = {"content-type": self.content_type}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        return self.response


def test_index_fetch_fails_closed_when_redirect_leaves_auction_index():
    session = FakeSession(
        FakeResponse(
            "https://riegermann.de/de/login",
            "<!doctype html><html><body>login</body></html>",
        )
    )

    with pytest.raises(ValueError, match="auction index"):
        fetch_riegermann_auction_index(
            DEFAULT_ACTIVE_AUCTIONS_URL,
            session=session,
        )


def _live_result(auction_id: str, title: str) -> RiegermannLiveResult:
    candidate = {
        "title": title,
        "scenario": "AUCTION",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "reason": "verified Riegermann clothing auction event",
        "page_role": "AUCTION_EVENT",
        "opportunity_identity": f"riegermann-auction:{auction_id}",
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "listing_status": "ACTIVE",
        "market_code": "DE",
        "currency": "EUR",
        "location": None,
        "company_name": None,
        "inventory_type": "clothing_auction_event",
        "price": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "source_urls": [f"https://riegermann.de/de/objekte/au-{auction_id}/x"],
        "source_providers": ["Riegermann"],
        "verification": [],
    }
    diagnostics = {
        "auction_identity": f"riegermann-auction:{auction_id}",
        "catalog_item_url_count": 2,
        "parsed_child_lot_count": 2,
        "ordinary_child_lot_count": 2,
        "promoted_bulk_lot_count": 0,
        "single_garment_candidate_count": 0,
    }
    discovery = {
        "all_discovered_candidates": [candidate],
        "discovery_top5": [],
        "search_run_report": {"riegermann_live": diagnostics},
    }
    return RiegermannLiveResult(
        discovery_result=discovery,
        diagnostics=diagnostics,
    )


def test_active_discovery_runs_only_explicit_clothing_auctions():
    session = FakeSession(
        FakeResponse(DEFAULT_ACTIVE_AUCTIONS_URL, _active_index_html())
    )
    calls: list[tuple[str, str | None]] = []

    def fake_runner(catalog_url: str, **kwargs):
        calls.append((catalog_url, kwargs.get("information_url")))
        return _live_result("908", "Versteigerung Cabrini GmbH")

    active = run_riegermann_active_auction_discovery(
        session=session,
        auction_runner=fake_runner,
        auction_limit=3,
        item_verification_limit=0,
    )
    report = active.discovery_result["search_run_report"]
    diagnostics = report["riegermann_active"]

    assert calls == [(CABRINI_CATALOG, CABRINI_INFORMATION)]
    assert diagnostics["auction_entries_discovered"] == 2
    assert diagnostics["active_clothing_entries_discovered"] == 1
    assert diagnostics["selected_auction_count"] == 1
    assert diagnostics["successful_auction_count"] == 1
    assert diagnostics["failed_auction_count"] == 0
    assert diagnostics["catalog_item_url_count"] == 2
    assert diagnostics["parsed_child_lot_count"] == 2
    assert report["source_mode"] == "RIEGERMANN_ACTIVE"
    assert report["source_target"] == "RIEGERMANN_ACTIVE_AUCTIONS"
    assert report["query_pack"] == "RIEGERMANN_ACTIVE_INDEX_V1"
    identities = {
        candidate["opportunity_identity"]
        for candidate in active.discovery_result["all_discovered_candidates"]
    }
    assert identities == {"riegermann-auction:908"}


def test_active_discovery_zero_clothing_results_is_valid():
    vehicle_only = _active_index_html().split(
        "<h3>Versteigerung Cabrini GmbH</h3>",
        1,
    )[0] + "<h3>Fahrzeugversteigerung</h3>" + _active_index_html().split(
        "<h3>Fahrzeugversteigerung</h3>",
        1,
    )[1]
    session = FakeSession(FakeResponse(DEFAULT_ACTIVE_AUCTIONS_URL, vehicle_only))

    active = run_riegermann_active_auction_discovery(
        session=session,
        auction_runner=lambda *args, **kwargs: pytest.fail("runner called"),
    )
    report = active.discovery_result["search_run_report"]

    assert report["status"] == "PASS"
    assert report["merged_candidates"] == 0
    assert report["riegermann_active"]["selected_auction_count"] == 0
    assert active.discovery_result["all_discovered_candidates"] == []
