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

def test_mynk_bankruptcy_list_is_rejected_before_page_read():
    reads = []
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit(
            "https://mynk.no/signaler/konkurser/byggefirmaer",
            title="Konkurser byggefirmaer: siste 30 dager",
        )]), brave=None,
        loader=lambda url: reads.append(url) or active_bankruptcy_html(), now=NOW,
    )
    assert reads == []
    assert report["verified_bankruptcy_sale_links"] == []
    assert report["rejected_hits"][0]["reason"] == "COMPANY_DIRECTORY_NOT_SALE_PAGE"


@pytest.mark.parametrize("html", [
    f"<title>Konkurser denne uken</title><p>{COMPANY} {ORG}</p>"
    "<p>Et konkursbo selger ofte eiendeler.</p>",
    f"<title>{COMPANY} nyheter</title><p>{ORG}</p>"
    + "<p>Registreringsopplysninger og historikk. </p>" * 40
    + "<p>Konkursboet selger inventar på auksjon.</p>",
    f"<title>Salg fra konkursbo</title><table><tr><td>{COMPANY} {ORG}</td></tr>"
    "<tr><td>Annet Selskap AS 987654321 Konkursboet selger inventar.</td></tr></table>",
    f"<title>{COMPANY} konkursbo</title>"
    "<article><p>Annet Selskap AS 987654321 Konkursboet selger inventar.</p></article>",
    f"<title>Salg fra konkursbo</title><section>{COMPANY} {ORG}</section>"
    "<section>Konkursboet selger inventar for Annet Selskap AS 987654321.</section>",
])
def test_list_faq_and_other_company_sale_are_never_combined(html):
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit()]), brave=None,
        loader=lambda url: html, now=NOW,
    )
    assert report["verified_bankruptcy_sale_links"] == []


def test_sale_identity_in_same_article_still_passes():
    html = f"<title>Auksjon fra konkursbo</title><article><h1>{COMPANY}</h1>"         f"<p>Org.nr. {ORG} Konkursboet selger inventar. Gi bud.</p></article>"
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit()]), brave=None,
        loader=lambda url: html, now=NOW,
    )
    assert report["verified_bankruptcy_sale_link_count"] == 1


ESTATE = "938645558"
CONTEXT_URL = f"https://konkurs.app/konkursbo/{ESTATE}"
TRUSTEE = "Tore M Famestad"


def context_html(*, org=ORG, name=COMPANY):
    return f"<title>{name} KONKURSBO | Konkurs.app</title>"         f"<h1>{name} KONKURSBO</h1><p>Organisasjonsnummer {ESTATE}</p>"         f"<dl><dt>Bostyrer</dt><dd>Adv. {TRUSTEE}</dd>"         "<dt>Bostyrers postadresse</dt><dd>Håkons gate 12, Hamar</dd></dl>"         f"<h2>Om foretaket</h2><p>{name} Organisasjonsnummer {org}</p>"


def follow_up_context():
    return {
        "organisation_number": ORG, "company_name": COMPANY,
        "estate_organisation_number": ESTATE, "trustee_name": TRUSTEE,
        "source_url": CONTEXT_URL, "search_hints_only": True,
    }


def test_konkurs_app_is_read_as_search_context_and_changes_brave_fallback():
    exa = FakeProvider("Exa", [hit(CONTEXT_URL)])
    brave = FakeProvider("Brave Search", [hit(provider="Brave Search")])
    reads = []

    def loader(url):
        reads.append(url)
        return context_html() if url == CONTEXT_URL else active_bankruptcy_html()

    report = hunt_bankruptcy_links(event_report(), exa=exa, brave=brave, loader=loader, now=NOW)
    assert reads == [CONTEXT_URL, SALE_URL]
    assert report["follow_up_contexts"] == [follow_up_context()]
    assert report["verified_bankruptcy_sale_link_count"] == 1
    assert report["verified_bankruptcy_sale_links"][0]["sale_url"] == SALE_URL
    assert ESTATE in brave.calls[0][0] and TRUSTEE in brave.calls[0][0]
    assert len(exa.calls) == len(brave.calls) == 1
    assert report["paid_provider_requests"] == 2 and report["page_reads"] == 2
    assert report["rejected_hits"][0]["reason"] == "BANKRUPTCY_CONTEXT_ONLY_NOT_SALE"


@pytest.mark.parametrize(("org", "name"), [("987654321", COMPANY), (ORG, "Annet Selskap AS")])
def test_wrong_company_context_cannot_redirect_follow_up_search(org, name):
    brave = FakeProvider("Brave Search", [])
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit(CONTEXT_URL)]), brave=brave,
        loader=lambda url: context_html(org=org, name=name), now=NOW,
    )
    assert report["follow_up_contexts"] == []
    assert ESTATE not in brave.calls[0][0] and TRUSTEE not in brave.calls[0][0]


def test_context_is_not_a_sale_even_when_it_contains_generic_sale_language():
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit(CONTEXT_URL)]), brave=None,
        loader=lambda url: context_html() + "<p>Konkursboet selger ofte eiendeler.</p>",
        now=NOW,
    )
    assert report["verified_bankruptcy_sale_links"] == []
    assert "لم تثبت عرض بضائع للبيع" in render_arabic(report)


def test_saved_estate_number_is_a_search_hint_not_sale_identity():
    saved = event_report()
    saved["events"][0]["follow_up_context"] = follow_up_context()
    provider = FakeProvider("Exa", [hit()])
    report = hunt_bankruptcy_links(
        saved, exa=provider, brave=None,
        loader=lambda url: f"<title>Auksjon fra konkursbo</title>"
            f"<p>{ESTATE} Konkursboet selger inventar.</p>", now=NOW,
    )
    assert ESTATE in provider.calls[0][0]
    assert report["verified_bankruptcy_sale_links"] == []


@pytest.mark.parametrize("url", [
    "https://konkurs.app.evil.com/konkursbo/938645558",
    "https://other.app/konkursbo/938645558",
    "https://konkurs.app/kommune/HAMAR",
])
def test_konkurs_app_exception_does_not_admit_other_foreign_or_index_pages(url):
    reads = []
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit(url)]), brave=None,
        loader=lambda url: reads.append(url) or context_html(), now=NOW,
    )
    assert reads == [] and report["follow_up_contexts"] == []


def test_page_limit_still_applies_to_context_reads():
    brave = FakeProvider("Brave Search", [hit(provider="Brave Search")])
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit(CONTEXT_URL)]), brave=brave,
        loader=lambda url: context_html(), max_page_reads=1, now=NOW,
    )
    assert report["page_reads"] == 1 and brave.calls == []
    assert report["verified_bankruptcy_sale_links"] == []


def test_organisation_number_cannot_be_assembled_from_unrelated_numbers():
    report = hunt_bankruptcy_links(
        event_report(), exa=FakeProvider("Exa", [hit()]), brave=None,
        loader=lambda url: "<title>Auksjon fra konkursbo</title>"
            "<p>Konkursboet selger inventar. Pris 123 kroner, 456 varer, 789 bud.</p>",
        now=NOW,
    )
    assert report["verified_bankruptcy_sale_links"] == []
