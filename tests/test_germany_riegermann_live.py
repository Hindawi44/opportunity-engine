from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from opportunity_engine.discovery.germany_riegermann_live import (
    extract_riegermann_item_urls,
    fetch_riegermann_public_page,
    run_riegermann_live_discovery,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "riegermann"
CATALOG_URL = (
    "https://www.riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh?Lstatus=1"
)
INFORMATION_URL = (
    "https://www.riegermann.de/de/2019_versteigerung_cabrini_gmbh/a/908"
)
BULK_URL = "https://riegermann.de/de/l/73490/posten-lederjacken-24-stueck"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        try:
            return self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"unexpected URL: {url}") from exc


def test_public_fetch_requires_exact_identity_and_html():
    html = _fixture("cabrini_active_catalog.html")
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(
                "https://www.riegermann.de/de/objekte/au-908/"
                "versteigerung_cabrini_gmbh?Lstatus=1",
                html,
            )
        }
    )

    page = fetch_riegermann_public_page(CATALOG_URL, session=session)

    assert page.identity_kind == "AUCTION_CATALOG"
    assert page.auction_id == "908"
    assert page.object_id is None
    assert page.status_code == 200
    assert page.response_bytes == len(html.encode("utf-8"))
    assert len(page.sha256) == 64
    assert session.calls[0][1]["allow_redirects"] is True
    assert "User-Agent" in session.calls[0][1]["headers"]


def test_public_fetch_rejects_redirect_that_changes_auction_identity():
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(
                "https://www.riegermann.de/de/objekte/au-909/other-auction",
                "<html><body>other</body></html>",
            )
        }
    )

    with pytest.raises(RuntimeError, match="changed auction or item identity"):
        fetch_riegermann_public_page(CATALOG_URL, session=session)


def test_public_fetch_rejects_oversized_response():
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(
                CATALOG_URL,
                "<html><body>" + ("x" * 200) + "</body></html>",
            )
        }
    )

    with pytest.raises(RuntimeError, match="exceeds"):
        fetch_riegermann_public_page(
            CATALOG_URL,
            session=session,
            max_response_bytes=50,
        )


def test_extract_item_urls_is_exact_unique_and_bounded():
    urls = extract_riegermann_item_urls(
        CATALOG_URL,
        _fixture("cabrini_active_catalog.html"),
    )

    assert urls == (
        "https://riegermann.de/de/l/73457/damen-lederjacke-groesse-36",
        "https://riegermann.de/de/l/73458/damen-ledermantel-groesse-40",
        "https://riegermann.de/de/l/73490/posten-lederjacken-24-stueck",
    )


def test_live_adapter_fetches_parent_and_only_promoted_bulk_item_page():
    catalog = _fixture("cabrini_active_catalog.html")
    sold_bulk = _fixture("sold_bulk_item.html")
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(CATALOG_URL, catalog),
            INFORMATION_URL: FakeResponse(INFORMATION_URL, catalog),
            BULK_URL: FakeResponse(BULK_URL, sold_bulk),
        }
    )

    live = run_riegermann_live_discovery(
        CATALOG_URL,
        information_url=INFORMATION_URL,
        session=session,
        item_verification_limit=10,
    )
    result = live.discovery_result
    candidates = result["all_discovered_candidates"]
    report = result["search_run_report"]

    assert report["status"] == "PASS"
    assert report["source_mode"] == "RIEGERMANN"
    assert report["source_target"] == "RIEGERMANN_AUCTION_908"
    assert report["riegermann_live"]["catalog_item_url_count"] == 3
    assert report["riegermann_live"]["parsed_child_lot_count"] == 3
    assert report["riegermann_live"]["ordinary_child_lot_count"] == 2
    assert report["riegermann_live"]["promoted_bulk_lot_count"] == 1
    assert report["riegermann_live"]["promoted_item_pages_requested"] == 1
    assert report["riegermann_live"]["promoted_item_pages_verified"] == 1
    assert report["riegermann_live"]["single_garment_candidate_count"] == 0

    assert {
        candidate["opportunity_identity"] for candidate in candidates
    } == {
        "riegermann-auction:908",
        "riegermann-object:73490",
    }
    parent = next(
        candidate
        for candidate in candidates
        if candidate["opportunity_identity"] == "riegermann-auction:908"
    )
    bulk = next(
        candidate
        for candidate in candidates
        if candidate["opportunity_identity"] == "riegermann-object:73490"
    )

    assert parent["verification"][0]["verified"] is True
    assert parent["verification"][0]["page_role"] == "AUCTION_EVENT"
    assert parent["top5_eligible"] is False
    assert bulk["exact_item_page_verified"] is True
    assert bulk["verification"][0]["verified"] is True
    assert bulk["verification"][0]["quantity"] == 24
    assert bulk["final_sale_price_eur"] == 650.0
    assert bulk["final_sale_price_trusted"] is True
    assert bulk["price_nok"] is None
    assert bulk["bid_price_nok"] is None
    assert result["discovery_top5"] == []

    requested_urls = [url for url, _ in session.calls]
    assert requested_urls == [CATALOG_URL, INFORMATION_URL, BULK_URL]
    assert not any("/73457/" in url or "/73458/" in url for url in requested_urls)


def test_live_adapter_keeps_bulk_unverified_when_item_limit_is_zero():
    catalog = _fixture("cabrini_active_catalog.html")
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(CATALOG_URL, catalog),
        }
    )

    live = run_riegermann_live_discovery(
        CATALOG_URL,
        session=session,
        item_verification_limit=0,
    )
    bulk = next(
        candidate
        for candidate in live.discovery_result["all_discovered_candidates"]
        if candidate["opportunity_identity"] == "riegermann-object:73490"
    )

    assert bulk["exact_item_page_verified"] is False
    assert bulk["verification"] == []
    assert bulk["top5_eligible"] is False
    assert len(session.calls) == 1
