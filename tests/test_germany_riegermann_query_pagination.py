from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.germany_riegermann_query_pagination import (
    build_riegermann_catalog_pagination_plan,
    install_riegermann_query_catalog_compatibility,
    run_riegermann_live_discovery_query_compat,
)

CATALOG_URL = (
    "https://riegermann.de/de/objekte/au-908/"
    "versteigerung_cabrini_gmbh"
)
QUERY_PAGE_1 = (
    "https://riegermann.de/de/objekte?Accid=49&Astatus=0&Lstatus=0&"
    "oldpagesize=2&pagenumber=1&pagesize=2"
)
QUERY_PAGE_2 = (
    "https://riegermann.de/de/objekte?Accid=49&Astatus=0&Lstatus=0&"
    "oldpagesize=2&pagenumber=2&pagesize=2"
)


def _page_number(url: str) -> int:
    return int(parse_qs(urlparse(url).query)["pagenumber"][-1])


def test_query_pagination_plan_expands_public_accid_pages():
    source = """
    <!doctype html><html><body>
      <p>250 Ergebnisse</p>
      <a href="/de/objekte?Accid=49&Astatus=0&Lstatus=0&oldpagesize=96&pagesize=96">96</a>
      <a href="/de/objekte?Accid=49&Astatus=0&Lstatus=0&oldpagesize=96&pagenumber=3&pagesize=96">... 3</a>
    </body></html>
    """

    plan = build_riegermann_catalog_pagination_plan(CATALOG_URL, source)

    assert plan.accid == "49"
    assert plan.total_results == 250
    assert plan.page_size == 96
    assert plan.expected_page_count == 3
    assert [_page_number(url) for url in plan.urls] == [1, 2, 3]
    assert all(urlparse(url).path == "/de/objekte" for url in plan.urls)
    assert all(parse_qs(urlparse(url).query)["Accid"] == ["49"] for url in plan.urls)


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
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        try:
            return self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"unexpected URL: {url}") from exc


def _item(url: str) -> str:
    return f'<a href="{url}">item</a>'


def test_query_pagination_live_run_fetches_every_generated_page():
    install_riegermann_query_catalog_compatibility()
    ordinary_1 = "https://riegermann.de/de/l/73249/damen_lederjacke_groesse_42"
    ordinary_2 = "https://riegermann.de/de/l/73250/damen_lederjacke_groesse_44"
    bulk = "https://riegermann.de/de/l/73490/posten_lederjacken_24_stueck"
    first_html = f"""
    <!doctype html><html><head><title>Versteigerung Cabrini GmbH</title></head><body>
      <h1>Versteigerung Cabrini GmbH</h1><p>Aktuell</p><p>3 Ergebnisse</p>
      {_item(ordinary_1)}
      <a href="/de/objekte?Accid=49&Astatus=0&Lstatus=0&oldpagesize=2&pagesize=2">2</a>
      <a href="/de/objekte?Accid=49&Astatus=0&Lstatus=0&oldpagesize=2&pagenumber=2&pagesize=2">... 2</a>
    </body></html>
    """
    page_1_html = f"""
    <!doctype html><html><body><p>3 Ergebnisse</p>
      {_item(ordinary_1)}{_item(ordinary_2)}
    </body></html>
    """
    page_2_html = f"""
    <!doctype html><html><body><p>3 Ergebnisse</p>{_item(bulk)}</body></html>
    """
    session = FakeSession(
        {
            CATALOG_URL: FakeResponse(CATALOG_URL, first_html),
            QUERY_PAGE_1: FakeResponse(QUERY_PAGE_1, page_1_html),
            QUERY_PAGE_2: FakeResponse(QUERY_PAGE_2, page_2_html),
        }
    )

    live = run_riegermann_live_discovery_query_compat(
        CATALOG_URL,
        session=session,
        item_verification_limit=0,
    )
    report = live.discovery_result["search_run_report"]["riegermann_live"]
    parent = next(
        candidate
        for candidate in live.discovery_result["all_discovered_candidates"]
        if candidate["page_role"] == "AUCTION_EVENT"
    )

    assert session.calls == [CATALOG_URL, QUERY_PAGE_1, QUERY_PAGE_2]
    assert report["catalog_scope_accid"] == "49"
    assert report["catalog_total_results"] == 3
    assert report["catalog_expected_page_count"] == 2
    assert report["catalog_page_count"] == 3
    assert report["catalog_coverage_reason"] == "complete"
    assert report["catalog_coverage_complete"] is True
    assert report["parsed_child_lot_count"] == 3
    assert report["promoted_bulk_lot_count"] == 1
    assert parent["catalog_coverage_complete"] is True
    assert parent["child_lot_count"] == 3
    assert parent["promoted_bulk_lot_count"] == 1


def test_query_pagination_never_marks_one_unproven_page_complete():
    install_riegermann_query_catalog_compatibility()
    ordinary = "https://riegermann.de/de/l/73249/damen_lederjacke_groesse_42"
    first_html = f"""
    <!doctype html><html><head><title>Versteigerung Cabrini GmbH</title></head><body>
      <h1>Versteigerung Cabrini GmbH</h1><p>Aktuell</p>{_item(ordinary)}
    </body></html>
    """
    session = FakeSession({CATALOG_URL: FakeResponse(CATALOG_URL, first_html)})

    live = run_riegermann_live_discovery_query_compat(
        CATALOG_URL,
        session=session,
        item_verification_limit=0,
    )
    report = live.discovery_result["search_run_report"]["riegermann_live"]
    parent = live.discovery_result["all_discovered_candidates"][0]

    assert report["catalog_page_count"] == 1
    assert report["catalog_pagination_evidence_found"] is False
    assert report["catalog_coverage_reason"] == "pagination_not_proven"
    assert report["catalog_coverage_complete"] is False
    assert parent["catalog_coverage_complete"] is False
    assert parent["post_verification_top5_block_reason"] == (
        "catalog_pagination_incomplete"
    )
