"""No real HTTP, paid API, SQLite or seller action in these contracts."""
from datetime import datetime, timezone

import pytest

from scripts.run_norway_insolvency_sale_links import SOURCES, discover, exact_item, vare_catalog

NOW = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
NORSK_LOT = "https://norskavvikling.no/produkt/parti-fra-konkursbo/"
VARE_LOT = "https://www.vareauksjonen.no/Event/LotDetails/209267/Bilder-og-bord"
VARE_CATALOG = "https://www.vareauksjonen.no/Event/Details/199258/Konkursbo-etter-Naromsorg"
AUCTION_LOT = "https://www.auksjonen.no/auksjon/torget/Parti_fra_konkursbo/627689"


def events():
    return {"schema_version": "norway-insolvency-event-sample-1", "events": [{
        "source_country": "NO", "organisation_number": "123456789",
        "company_name": "Nord Industri AS",
        "official_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789",
        "event_kinds": ["konkurs"],
    }]}


def mock_pages():
    return {
        SOURCES["Norsk Avvikling"]: (
            '<a href="/produkt/parti-fra-konkursbo/">Parti fra konkursbo</a>'
            '<a href="/produkt/regular/">Vanlig restlager</a>'
            '<a href="https://evil.example/produkt/parti-fra-konkursbo/">konkursbo</a>'
        ),
        SOURCES["Vareauksjonen"]: '<a href="/Event/LotDetails/209267/Bilder-og-bord">Bilder fra konkursbo</a>',
        SOURCES["Auksjonen"]: '<a href="/auksjon/torget/Parti_fra_konkursbo/627689">Parti fra konkursbo</a>',
        NORSK_LOT: '<html><h1>Parti fra konkursbo</h1><p>Nord Industri AS 123456789. Til salgs</p><p>Legg til i handlekurv</p></html>',
        VARE_LOT: '<html><h1>Konkursbo etter Nord Industri AS</h1><h1>Bilder og bord</h1><p>Avsluttet. Solgt</p></html>',
        AUCTION_LOT: '<html><h1>Parti fra konkursbo</h1><p>Fra et ukjent konkursbo. Gi bud</p></html>',
    }


def test_collects_three_distinct_norwegian_sites_and_never_calls_generic_sale_opportunity():
    pages = mock_pages()
    report = discover(events(), loader=lambda url: pages[url], now=NOW)
    assert len(report["marketplace_sources"]) == 3
    assert all(row["status"] == "READ_BOUNDED" for row in report["marketplace_sources"])
    assert report["candidate_exact_urls_from_indices"] == 3
    assert report["detail_pages_checked"] == 3
    assert report["closed_pages_excluded"] == 1
    assert report["unverified_lead_count"] == 2
    assert {lead["url"] for lead in report["review_only_unverified_direct_leads"]} == {NORSK_LOT, AUCTION_LOT}
    assert report["verified_insolvency_sale_count"] == 0
    assert report["verified_insolvency_sale_links"] == []
    assert report["paid_provider_requests"] == 0
    assert all(report[key] is False for key in ("automatic_contact", "automatic_bid", "automatic_purchase", "automatic_payment"))


def test_exact_identity_is_investigation_not_verified_sale_or_seller():
    report = discover(events(), loader=lambda url: mock_pages()[url], now=NOW)
    linked = next(lead for lead in report["review_only_unverified_direct_leads"] if lead["source"] == "Norsk Avvikling")
    assert linked["organisation_number"] == "123456789"
    assert linked["official_event_url"].endswith("/123456789")
    assert linked["relation_evidence"] == "ORGANISATION_NUMBER_ON_PAGE_NOT_SELLER_VERIFIED"
    assert linked["availability_verified"] is linked["inventory_verified"] is linked["seller_identity_verified"] is False
    unknown = next(lead for lead in report["review_only_unverified_direct_leads"] if lead["source"] == "Auksjonen")
    assert unknown["organisation_number"] is None
    assert unknown["relation_evidence"] == "NO_OFFICIAL_COMPANY_MATCH_SOURCE_CLAIM_ONLY"


def test_false_index_claim_cannot_bypass_specific_item_heading():
    pages = mock_pages()
    pages[NORSK_LOT] = '<h1>Vanlig bil</h1><p>Alle produkter kan være fra konkursbo i våre generelle vilkår.</p>'
    report = discover(events(), loader=lambda url: pages[url], now=NOW)
    assert all(lead["url"] != NORSK_LOT for lead in report["review_only_unverified_direct_leads"])


def test_real_vare_lot_route_is_item_but_event_details_are_navigation_only():
    index = SOURCES["Vareauksjonen"]
    assert exact_item("Vareauksjonen", VARE_LOT, index) == VARE_LOT
    assert exact_item("Vareauksjonen", VARE_CATALOG, index) is None
    assert vare_catalog(VARE_CATALOG) == VARE_CATALOG
    assert vare_catalog("https://www.vareauksjonen.no/Event/Details/199258/") is not None
    assert vare_catalog(VARE_LOT) is None
    assert exact_item("Vareauksjonen", VARE_LOT + "?item=1", index) is None
    assert exact_item("Vareauksjonen", "https://evil.example/Event/LotDetails/209267/Bilder-og-bord", index) is None
    assert vare_catalog("https://evil.example/Event/Details/199258") is None


def test_bounded_vare_catalog_expands_real_lot_without_promoting_to_sale():
    pages = mock_pages()
    pages[SOURCES["Vareauksjonen"]] = (
        f'<a href="{VARE_CATALOG}">Konkursbo etter Nord Industri AS</a>'
        '<a href="/Event/Details/200000/Vanlig-auksjon">Vanlig auksjon</a>'
    )
    pages[VARE_CATALOG] = (
        '<h1>Konkursbo etter Nord Industri AS</h1><p>Aktiv. Første objekt stenges senere</p>'
        f'<a href="{VARE_LOT}">Bilder og bord</a>'
        '<a href="https://evil.example/Event/LotDetails/987654/Foreign">foreign</a>'
    )
    pages[VARE_LOT] = (
        '<h1>Konkursbo etter Nord Industri AS</h1><h1>Bilder og bord</h1>'
        '<p>Objektnr. 122 Aktiv. Beskrivelse: 1 bord</p>'
    )
    report = discover(events(), loader=lambda url: pages[url], now=NOW)
    assert report["vare_catalogs_checked"] == 1
    assert report["vare_catalogs_closed"] == 0
    assert report["candidate_exact_urls_from_indices"] == 3
    assert report["detail_pages_checked"] == 3
    assert report["marketplace_sources"][1]["catalog_navigation_links"] == 2
    assert report["marketplace_sources"][1]["status"] == "CATALOG_SCAN_BOUNDED_INCOMPLETE"
    vare = next(lead for lead in report["review_only_unverified_direct_leads"] if lead["source"] == "Vareauksjonen")
    assert vare["url"] == VARE_LOT
    assert vare["organisation_number"] == "123456789"
    assert vare["relation_evidence"] == "COMPANY_NAME_ON_PAGE_NOT_SELLER_VERIFIED"
    assert not vare["seller_identity_verified"] and not vare["availability_verified"]
    assert report["verified_insolvency_sale_count"] == 0


def test_closed_vare_catalog_blocks_all_its_lots():
    pages = mock_pages()
    pages[SOURCES["Vareauksjonen"]] = f'<a href="{VARE_CATALOG}">Konkursbo etter Nord Industri AS</a>'
    pages[VARE_CATALOG] = (
        '<h1>Konkursbo etter Nord Industri AS</h1><p>Lukket (#199258)</p>'
        f'<a href="{VARE_LOT}">Bilder og bord</a>'
    )
    report = discover(events(), loader=lambda url: pages[url], now=NOW)
    assert report["vare_catalogs_checked"] == 1
    assert report["vare_catalogs_closed"] == 1
    assert report["candidate_exact_urls_from_indices"] == 2
    assert report["verified_insolvency_sale_count"] == 0
    assert all(lead["source"] != "Vareauksjonen" for lead in report["review_only_unverified_direct_leads"])


def test_url_allowlist_rejects_foreign_hosts_parent_queries_and_unsafe_ports():
    for source, index in SOURCES.items():
        assert exact_item(source, index, index) is None
        assert exact_item(source, "https://evil.example/produkt/konkursbo/", index) is None
    assert exact_item("Norsk Avvikling", NORSK_LOT + "?buy=1", SOURCES["Norsk Avvikling"]) is None
    assert exact_item("Vareauksjonen", "https://www.vareauksjonen.no/Event/Details/199258/", SOURCES["Vareauksjonen"]) is None
    assert exact_item("Auksjonen", "https://www.auksjonen.no/auksjoner/torget/vareparti-og-konkursbo", SOURCES["Auksjonen"]) is None
    assert exact_item("Norsk Avvikling", "http://norskavvikling.no/produkt/konkursbo/", SOURCES["Norsk Avvikling"]) is None
    assert exact_item("Norsk Avvikling", "https://norskavvikling.no:444/produkt/konkursbo/", SOURCES["Norsk Avvikling"]) is None


def test_single_source_failure_is_reported_not_false_zero_and_case_limit_is_hard():
    pages = mock_pages()
    del pages[SOURCES["Vareauksjonen"]]
    report = discover(events(), loader=lambda url: pages[url], max_details=1, now=NOW)
    assert len(report["source_errors"]) == 1
    assert report["marketplace_sources"][1]["status"] == "FAILED_NOT_ZERO"
    assert report["detail_pages_checked"] == 1
    assert report["verified_insolvency_sale_count"] == 0
    for invalid in (0, 10):
        with pytest.raises(ValueError):
            discover(events(), max_details=invalid, loader=lambda url: pages[url])


def test_rejects_fake_registry_or_wrong_market_without_network():
    bad = events()
    bad["events"][0]["official_url"] = "https://untrusted.example/123456789"
    with pytest.raises(ValueError, match="Official organisation evidence"):
        discover(bad, loader=lambda _: "")
    bad = events()
    bad["events"][0]["source_country"] = "SE"
    with pytest.raises(ValueError, match="Invalid event source"):
        discover(bad, loader=lambda _: "")
    with pytest.raises(ValueError, match="Official Norway"):
        discover({"events": []}, loader=lambda _: "")
