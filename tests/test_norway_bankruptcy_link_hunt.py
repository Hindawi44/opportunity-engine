"""Bankruptcy-first Norway link chase rejects traders, surplus and liquidation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.search_provider import SearchHit
from scripts.run_norway_bankruptcy_link_hunt import (
    hunt_bankruptcy_links,
    render_arabic,
)
from scripts.run_norway_openai_search_intelligence import build_bankruptcy_hunt_brief


NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
ORG = "123456789"
COMPANY = "Nord Industri AS"
OFFICIAL = f"https://data.brreg.no/enhetsregisteret/api/enheter/{ORG}"
SALE_URL = "https://advokatfirma.no/konkursbo/nord-industri"


class FakeProvider:
    def __init__(self, name: str, hits: list[SearchHit]) -> None:
        self.name = name
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        self.calls.append((query, count))
        return list(self.hits)


def event_report() -> dict:
    return {
        "schema_version": "norway-insolvency-event-sample-1",
        "scope": "NO_ONLY_OFFICIAL_BANKRUPTCY_ALL_SECTORS",
        "captured_at": NOW.isoformat(),
        "events": [
            {
                "organisation_number": ORG,
                "company_name": COMPANY,
                "official_url": OFFICIAL,
                "source_country": "NO",
                "event_kinds": ["konkurs"],
                "event_date": "2026-09-23",
                "location": "Namsos",
            }
        ],
    }


def hit(
    url: str = SALE_URL,
    *,
    provider: str = "Exa",
    title: str = "Nord Industri AS konkursbo - auksjon",
    description: str = "Konkursboets driftsmidler selges på auksjon",
) -> SearchHit:
    return SearchHit(title=title, url=url, description=description, provider=provider)


def active_bankruptcy_html() -> str:
    return f"""
    <html><head><title>{COMPANY} konkursbo – auksjon</title></head>
    <body><h1>Driftsmidler selges fra konkursboet</h1>
    <p>Organisasjonsnummer {ORG[:3]} {ORG[3:6]} {ORG[6:]}.</p>
    <p>Gi bud på maskiner og inventar.</p></body></html>
    """


def test_exa_link_is_kept_only_after_page_proves_bankruptcy_identity_and_sale():
    exa = FakeProvider("Exa", [hit()])
    brave = FakeProvider("Brave Search", [hit(provider="Brave Search")])
    report = hunt_bankruptcy_links(
        event_report(),
        exa=exa,
        brave=brave,
        loader=lambda url: active_bankruptcy_html(),
        now=NOW,
    )

    assert len(exa.calls) == 1
    assert brave.calls == []
    assert "avvikling" not in exa.calls[0][0].casefold()
    assert ORG in exa.calls[0][0]
    assert "bostyrer" in exa.calls[0][0].casefold()
    assert report["verified_bankruptcy_sale_link_count"] == 1
    link = report["verified_bankruptcy_sale_links"][0]
    assert link["classification"] == "OFFICIAL_BANKRUPTCY_LINKED_ASSET_SALE"
    assert link["official_bankruptcy_url"] == OFFICIAL
    assert link["sale_url"] == SALE_URL
    assert link["identity_match_method"] == "OFFICIAL_ORGANISATION_NUMBER_ON_PAGE"
    assert link["liquidation_only"] is False
    assert link["surplus_only"] is False
    assert link["dealer_only"] is False
    assert link["inventory_contents_verified"] is False
    assert link["human_review_required"] is True
    assert report["policy"]["search_snippet_never_sufficient"] is True
    assert "إفلاس مثبت الربط" in render_arabic(report)


def test_known_watchlist_sale_url_is_rechecked_without_paid_search():
    persisted = event_report()
    persisted["events"][0]["known_sale_urls"] = [SALE_URL]
    exa = FakeProvider("Exa", [hit()])
    brave = FakeProvider("Brave Search", [hit(provider="Brave Search")])

    report = hunt_bankruptcy_links(
        persisted,
        exa=exa,
        brave=brave,
        loader=lambda url: active_bankruptcy_html(),
        now=NOW,
    )

    assert exa.calls == []
    assert brave.calls == []
    assert report["known_link_rechecks"] == 1
    assert report["coverage"] == "DIRECT_WATCHLIST_RECHECK_ONLY"
    assert report["paid_provider_requests"] == 0
    assert report["events_searched"] == 1
    assert report["verified_bankruptcy_sale_link_count"] == 1
    assert (
        report["verified_bankruptcy_sale_links"][0]["search_provider"]
        == "Watchlist direct recheck"
    )


def test_failed_direct_watchlist_read_is_not_reported_as_a_clean_zero():
    persisted = event_report()
    persisted["events"][0]["known_sale_urls"] = [SALE_URL]

    def unavailable(url: str) -> str:
        raise RuntimeError("temporary page outage")

    report = hunt_bankruptcy_links(
        persisted,
        exa=None,
        brave=None,
        loader=unavailable,
        now=NOW,
    )

    assert report["coverage"] == "DIRECT_WATCHLIST_RECHECK_FAILED"
    assert report["paid_provider_requests"] == 0
    assert report["rejected_hits"][0]["reason"] == "PAGE_READ_FAILED:RuntimeError"


def test_surplus_dealer_exa_result_is_rejected_then_brave_fallback_runs():
    exa = FakeProvider(
        "Exa",
        [
            hit(
                "https://grossistlager.no/restlager/arbeidsklaer",
                title="Grossist selger restlager",
                description="Overskuddsvarer og partivarer fra forhandler",
            )
        ],
    )
    brave = FakeProvider("Brave Search", [hit(provider="Brave Search")])
    loaded: list[str] = []

    def loader(url: str) -> str:
        loaded.append(url)
        return active_bankruptcy_html()

    report = hunt_bankruptcy_links(
        event_report(), exa=exa, brave=brave, loader=loader, now=NOW
    )

    assert len(exa.calls) == len(brave.calls) == 1
    assert loaded == [SALE_URL]
    assert report["verified_bankruptcy_sale_link_count"] == 1
    assert report["verified_bankruptcy_sale_links"][0]["search_provider"] == "Brave Search"
    assert any(
        row["reason"] == "SEARCH_RESULT_IS_LIQUIDATION_SURPLUS_OR_TRADER"
        for row in report["rejected_hits"]
    )


@pytest.mark.parametrize(
    ("html", "reason"),
    [
        (
            f"<title>{COMPANY} avvikling</title><p>{ORG} restlager selges av grossist</p>",
            "LIQUIDATION_SURPLUS_OR_TRADER_NOT_BANKRUPTCY",
        ),
        (
            "<title>Annet Selskap AS konkursbo</title><p>987654321 inventar selges på auksjon</p>",
            "OFFICIAL_BANKRUPT_COMPANY_NOT_IDENTIFIED_ON_PAGE",
        ),
        (
            f"<title>{COMPANY} konkursbo omtalt</title><p>{ORG} grossist selger restlager og utstyr</p>",
            "NO_EXPLICIT_BANKRUPTCY_ESTATE_SALE_RELATION",
        ),
        (
            f"<title>{COMPANY} konkursbo</title><p>{ORG} auksjonen er avsluttet</p>",
            "SALE_PAGE_EXPLICITLY_ENDED",
        ),
    ],
)
def test_page_must_prove_current_bankruptcy_sale_for_same_official_company(html, reason):
    report = hunt_bankruptcy_links(
        event_report(),
        exa=FakeProvider("Exa", [hit()]),
        brave=None,
        loader=lambda url: html,
        now=NOW,
    )
    assert report["verified_bankruptcy_sale_link_count"] == 0
    assert report["rejected_hits"][0]["reason"] == reason
    assert "لا يوجد رابط يُعرض كفرصة" in render_arabic(report)


def test_foreign_and_generic_index_urls_are_never_read():
    exa = FakeProvider(
        "Exa",
        [
            hit("https://example.com/konkursbo/nord"),
            hit("https://www.auksjonen.no/auksjoner/torget/vareparti-og-konkursbo"),
        ],
    )
    reads: list[str] = []
    report = hunt_bankruptcy_links(
        event_report(),
        exa=exa,
        brave=None,
        loader=lambda url: reads.append(url) or active_bankruptcy_html(),
        now=NOW,
    )
    assert reads == []
    assert report["verified_bankruptcy_sale_link_count"] == 0
    assert {row["reason"] for row in report["rejected_hits"]} == {
        "NON_NORWEGIAN_OR_UNSAFE_URL",
        "GENERIC_INDEX_NOT_EXACT_SALE_PAGE",
    }


def test_mixed_insolvency_input_and_non_bankruptcy_event_fail_closed():
    mixed = event_report()
    mixed["scope"] = "NO_ONLY_INSOLVENCY_LIQUIDATION_ALL_SECTORS"
    with pytest.raises(ValueError, match="Liquidation or mixed insolvency"):
        hunt_bankruptcy_links(mixed, exa=None, brave=None)

    wrong_event = event_report()
    wrong_event["events"][0]["event_kinds"] = ["underAvvikling"]
    with pytest.raises(ValueError, match="official Norwegian bankruptcy"):
        hunt_bankruptcy_links(wrong_event, exa=None, brave=None)


def test_limits_and_no_provider_state_are_explicit():
    report = hunt_bankruptcy_links(event_report(), exa=None, brave=None, now=NOW)
    assert report["coverage"] == "SEARCH_PROVIDERS_UNAVAILABLE"
    assert report["paid_provider_requests"] == 0
    assert report["verified_bankruptcy_sale_links"] == []
    for kwargs in (
        {"max_events": 6},
        {"results_per_query": 6},
        {"max_page_reads": 16},
    ):
        with pytest.raises(ValueError):
            hunt_bankruptcy_links(event_report(), exa=None, brave=None, **kwargs)


def test_openai_receives_only_the_official_event_and_proven_sale_link(tmp_path: Path):
    report = hunt_bankruptcy_links(
        event_report(),
        exa=FakeProvider("Exa", [hit()]),
        brave=None,
        loader=lambda url: active_bankruptcy_html(),
        now=NOW,
    )
    path = tmp_path / "bankruptcy-link-hunt.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    brief = build_bankruptcy_hunt_brief(path)
    assert brief["market_coverage"] == ["NO"]
    assert brief["input_policy"] == "DETERMINISTIC_BANKRUPTCY_LINKS_ONLY"
    assert len(brief["early_signals_to_watch"]) == 2
    assert {row["signal_type"] for row in brief["early_signals_to_watch"]} == {
        "BANKRUPTCY",
        "DIRECT_OPPORTUNITY_CHANGE",
    }
    assert {
        row["metadata"]["event_kind"] for row in brief["early_signals_to_watch"]
    } == {"KONKURS"}
    assert {
        row["metadata"]["organisation_number"]
        for row in brief["early_signals_to_watch"]
    } == {ORG}

    report["verified_bankruptcy_sale_links"][0]["surplus_only"] = True
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Unverified or non-bankruptcy"):
        build_bankruptcy_hunt_brief(path)
