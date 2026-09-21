"""No HTTP, purchases, foreign source, SQLite or paid providers."""
from datetime import datetime, timezone

import pytest

from scripts.probe_norway_unlabeled_vare_lots import augment
from scripts.run_norway_insolvency_sale_links import SOURCES

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)
BASE = SOURCES["Vareauksjonen"]
FIRST = "https://www.vareauksjonen.no/Event/LotDetails/234501/Bord"
SECOND = "https://www.vareauksjonen.no/Event/LotDetails/234502/Stoler"
THIRD = "https://www.vareauksjonen.no/Event/LotDetails/234503/Utstyr"


def raw(used=6):
    return {"schema_version": "no-insolvency-multisource-evidence-1",
            "scope": "NO_ONLY_BANKRUPTCY_LIQUIDATION_ALL_SECTORS",
            "detail_pages_checked": used, "review_only_unverified_direct_leads": [],
            "source_errors": [], "verified_insolvency_sale_count": 0}


def pages():
    return {
        BASE: (f'<a href="{FIRST}">Bord for salg</a><span>Solgt</span>'
               f'<a href="{SECOND}">Stoler fra lager</a><span>Åpen for bud</span>'
               f'<a href="{THIRD}">Utstyr fra lager</a><span>Åpen for bud</span>'
               '<a href="https://outside.example/Event/LotDetails/234504/Illegal">foreign</a>'),
        SECOND: ('<h1>Konkursboet etter Nord Industri AS</h1><h1>Stoler fra lager</h1>'
                 '<p>Objekt 12. Status ukjent; innhold på siden.</p>'),
        THIRD: ('<h1>Ordinære møbler</h1><h1>Utstyr fra lager</h1>'
                '<p>Vanlig auksjon; ingen konkret konkursselger.</p>'),
    }


def test_unlabeled_individual_heading_gives_review_lead_never_verified():
    documents = pages()
    touched = []
    report = augment(raw(), loader=lambda url: touched.append(url) or documents[url], now=NOW)
    diagnostic = report["vare_unlabeled_lot_probe"]
    assert diagnostic["unlabeled_unique_item_urls"] == 3
    assert diagnostic["homepage_closed_items_not_probed"] == 1
    assert diagnostic["detail_pages_probed"] == 2
    assert diagnostic["estate_heading_matched"] == 1
    assert report["detail_pages_checked"] == 8
    assert FIRST not in touched and "outside.example" not in " ".join(touched)
    assert report["unverified_lead_count"] == 1
    lead = report["review_only_unverified_direct_leads"][0]
    assert (lead["url"], lead["title"]) == (SECOND, "Stoler fra lager")
    assert lead["auction_title"] == "Konkursboet etter Nord Industri AS"
    assert not lead["seller_identity_verified"] and not lead["availability_verified"]
    assert report["verified_insolvency_sale_count"] == 0
    assert report["verified_insolvency_sale_links"] == []


def test_individual_sold_marker_excludes_even_when_homepage_lacks_it():
    documents = pages()
    documents[BASE] = f'<a href="{SECOND}">Stoler fra lager</a>'
    documents[SECOND] = '<h1>Konkursbo etter Test AS</h1><h1>Stoler fra lager</h1><p>Solgt kr 200</p>'
    result = augment(raw(), loader=lambda url: documents[url], now=NOW)
    assert result["vare_unlabeled_lot_probe"]["sold_or_ended_details_excluded"] == 1
    assert result["unverified_lead_count"] == 0


def test_no_extra_read_if_existing_discovery_used_entire_budget():
    touched = []
    report = augment(raw(used=9), max_probe=0, loader=lambda url: touched.append(url) or pages()[url], now=NOW)
    assert report["detail_pages_checked"] == 9
    assert report["vare_unlabeled_lot_probe"]["detail_pages_probed"] == 0
    assert touched == [BASE]
    with pytest.raises(ValueError, match="budget"):
        augment(raw(used=9), max_probe=1, loader=lambda url: pages()[url])


def test_invalid_report_and_failed_source_fail_closed_without_false_zero_claim():
    with pytest.raises(ValueError, match="Norway"):
        augment({"schema_version": "fake"})
    report = augment(raw(), loader=lambda _: (_ for _ in ()).throw(OSError("blocked")), now=NOW)
    assert report["unverified_lead_count"] == 0
    assert report["vare_unlabeled_lot_probe"]["detail_pages_probed"] == 0
    assert report["source_errors"][0]["stage"] == "unlabeled_index"
