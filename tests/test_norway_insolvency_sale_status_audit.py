"""Offline tests only: no real HTTP, paid services, purchases or database writes."""
from datetime import datetime, timezone

import pytest

from scripts.audit_norway_insolvency_sale_links import (
    audit, index_says_closed, item_says_closed, named_estate, official_match,
)
from scripts.run_norway_insolvency_sale_links import SOURCES

NOW = datetime(2026, 9, 21, 6, tzinfo=timezone.utc)
LOT = "https://www.vareauksjonen.no/Event/LotDetails/288689/Lot-400-Hawaiifestartikler-blomsterkranser-og-pynt"
TITLE = "Lot 400- Hawaii-/festartikler – blomsterkranser og pynt Vis overvåkningsliste"


def events(*, populated=False):
    rows = ([{"source_country": "NO", "organisation_number": "123456789",
              "company_name": "Nord Industri AS", "event_kinds": ["konkurs"],
              "official_url": "https://data.brreg.no/enhetsregisteret/api/enheter/123456789"}]
            if populated else [])
    return {"schema_version": "norway-insolvency-event-sample-1", "events": rows}


def raw(*, title=TITLE, url=LOT):
    return {"schema_version": "no-insolvency-multisource-evidence-1",
            "scope": "NO_ONLY_BANKRUPTCY_LIQUIDATION_ALL_SECTORS",
            "source_errors": [], "verified_insolvency_sale_count": 0,
            "review_only_unverified_direct_leads": [{
                "url": url, "source": "Vareauksjonen", "title": title,
                "organisation_number": None, "official_event_url": None,
                "sale_status": "UNVERIFIED_NO_SOURCE_NATIVE_OPEN_PROOF",
            }]}


def test_vare_homepage_sold_excludes_even_if_parent_auction_is_active():
    homepage = (
        "PAUSE Varelager og konkursbo " + TITLE.split(" Vis overvåkningsliste")[0] +
        " 1 Bud Nåværende bud kr 275,00 Solgt Lot 400- Hawaii pynt PAUSE"
    )
    pages = {SOURCES["Vareauksjonen"]: homepage,
             LOT: "<h1>KOSTYMER FRA KONKURSBO Aktiv</h1><h1>Lot 400- Hawaii pynt</h1><p>Gi bud</p>"}
    result = audit(raw(), events(), loader=lambda url: pages[url], now=NOW)
    assert result["precheck_unverified_lead_count"] == 1
    assert result["sale_closed_excluded_after_recheck"] == 1
    assert result["closed_or_sold_evidence"][0]["reason"] == "SOURCE_INDEX_ITEM_SOLD_OR_ENDED"
    assert result["unverified_lead_count"] == 0
    assert result["verified_insolvency_sale_count"] == 0


def test_other_lot_sold_not_misattributed_to_our_lot():
    index = "Lot 400- Hawaii pynt Aktiv PAUSE Lot 401- Hawaii kjoler 1 Bud Solgt"
    assert not index_says_closed(index, "Lot 400- Hawaii pynt")
    assert index_says_closed(index, "Lot 401- Hawaii kjoler")
    assert item_says_closed("<h1>Lot 400- Hawaii pynt</h1><p>Avsluttet.</p>", "Lot 400- Hawaii pynt")


def test_explicit_estate_matches_sample_but_never_proves_sale_or_seller():
    title = "Lot 400- Hawaii pynt"
    pages = {SOURCES["Vareauksjonen"]: title + " 0 Bud kr 100,00 Aktiv PAUSE",
             LOT: "<h1>Konkursboet etter Nord Industri AS</h1><h1>Lot 400- Hawaii pynt</h1><p>Bud nå</p>"}
    result = audit(raw(title=title), events(populated=True), loader=lambda url: pages[url],
                   registry_lookup=lambda _: pytest.fail("Sample match must not call public API"), now=NOW)
    lead = result["review_only_unverified_direct_leads"][0]
    assert lead["organisation_number"] == "123456789"
    assert lead["official_entity_status_confirmed"] is True
    assert lead["relation_evidence"] == "NAMED_ESTATE_MATCHES_OFFICIAL_SAMPLED_INSOLVENCY"
    assert lead["seller_identity_verified"] is lead["availability_verified"] is False
    assert result["named_estates_registry_confirmed"] == 1
    assert result["verified_insolvency_sale_count"] == 0


def test_named_estate_outside_ten_company_sample_uses_exact_official_registry():
    title = "Lot 400- Hawaii pynt"
    pages = {SOURCES["Vareauksjonen"]: title + " 0 Bud Aktiv PAUSE",
             LOT: "<h1>Konkursbo etter Nord Industri AS</h1><h1>Lot 400- Hawaii pynt</h1>"}
    seen = []
    def lookup(name):
        seen.append(name)
        return {"_embedded": {"enheter": [{"navn": "Nord Industri AS",
            "organisasjonsnummer": "123456789", "konkurs": True,
            "forretningsadresse": {"landkode": "NO"}}]}}
    result = audit(raw(title=title), events(), loader=lambda url: pages[url], registry_lookup=lookup, now=NOW)
    lead = result["review_only_unverified_direct_leads"][0]
    assert seen == ["Nord Industri AS"]
    assert lead["official_entity_status_confirmed"] is True
    assert lead["official_event_url"].endswith("/123456789")
    assert lead["relation_evidence"] == "NAMED_ESTATE_MATCHES_LIVE_OFFICIAL_INSOLVENCY"
    assert result["official_name_lookups"] == 1
    assert result["verified_insolvency_sale_count"] == 0


def test_no_match_or_no_official_insolvency_never_invents_identity():
    for row in ({"navn": "Other AS", "organisasjonsnummer": "123456789", "konkurs": True},
                {"navn": "Nord Industri AS", "organisasjonsnummer": "123456789", "konkurs": False},
                {"navn": "Nord Industri AS", "organisasjonsnummer": "123456789", "konkurs": True,
                 "forretningsadresse": {"landkode": "SE"}}):
        assert official_match("Nord Industri AS", {"_embedded": {"enheter": [row]}}) is None
    assert named_estate("<h1>Fra konkursbo</h1><p>Alle varer kan komme fra konkursbo</p>") is None


def test_failed_item_fetch_is_quarantined_and_foreign_url_is_not_fetched():
    pages = {SOURCES["Vareauksjonen"]: TITLE}
    result = audit(raw(), events(), loader=lambda url: pages[url], now=NOW)
    assert result["unverified_lead_count"] == 0
    assert result["status_check_quarantined"][0]["reason"] == "ITEM_STATUS_FETCH_FAILED"
    unsafe = audit(raw(url="https://evil.example/Event/LotDetails/288689/Lot-400"),
                   events(), loader=lambda _: pytest.fail("Foreign HTTP forbidden"), now=NOW)
    assert unsafe["status_check_quarantined"][0]["reason"] == "INVALID_OR_NON_NORWEGIAN_ITEM_URL"


def test_invalid_schema_and_unbounded_input_rejected():
    with pytest.raises(ValueError, match="Norway-only"):
        audit({"schema_version": "wrong"}, events(), loader=lambda _: "")
    too_many = raw()
    too_many["review_only_unverified_direct_leads"] *= 10
    with pytest.raises(ValueError, match="Unbounded"):
        audit(too_many, events(), loader=lambda _: "")
