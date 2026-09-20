"""Regression: Vare auctions name their parent and individual lots separately."""
from scripts.run_norway_insolvency_sale_links import SOURCES, discover

LOT = "https://www.vareauksjonen.no/Event/LotDetails/288689/Lot-400-Hawaiifestartikler"


def test_vare_cards_show_unique_lot_title_and_preserve_parent_as_unverified_context():
    index = SOURCES["Vareauksjonen"]
    html = {
        SOURCES["Norsk Avvikling"]: '<a href="/">Home</a>',
        index: f'<a href="{LOT}">Lot 400 - Hawaiifestartikler Varelager og konkursbo</a>',
        SOURCES["Auksjonen"]: '<a href="/">Home</a>',
        LOT: (
            '<h1>KOSTYMER, HALLOWEEN & PARTY FRA KONKURSBO Aktiv (#283986)</h1>'
            '<h1>Lot 400 - Hawaiifestartikler, blomsterkranser og pynt</h1>'
            '<p>Objektnr. 400. Aktiv. Beskrivelse av objektet.</p>'
        ),
    }
    report = discover({"schema_version": "norway-insolvency-event-sample-1", "events": []},
                      loader=lambda url: html[url])
    assert report["unverified_lead_count"] == 1
    lead = report["review_only_unverified_direct_leads"][0]
    assert lead["url"] == LOT
    assert lead["title"] == "Lot 400 - Hawaiifestartikler, blomsterkranser og pynt"
    assert lead["auction_title"].startswith("KOSTYMER, HALLOWEEN")
    assert lead["organisation_number"] is None
    assert lead["seller_identity_verified"] is False
    assert lead["availability_verified"] is False
    assert report["verified_insolvency_sale_count"] == 0


def test_ended_vare_lot_never_enters_review_despite_bankruptcy_parent_title():
    index = SOURCES["Vareauksjonen"]
    html = {
        SOURCES["Norsk Avvikling"]: '<a href="/">Home</a>',
        index: f'<a href="{LOT}">Lot 400 - Hawaiifestartikler Varelager og konkursbo</a>',
        SOURCES["Auksjonen"]: '<a href="/">Home</a>',
        LOT: ('<h1>KONKURSBO ETTER ET FIRMA</h1><h1>Lot 400 - Hawaiifestartikler</h1>'
              '<p>Objektnr 400. Avsluttet. Selger - Vareauksjonen.</p>'),
    }
    report = discover({"schema_version": "norway-insolvency-event-sample-1", "events": []},
                      loader=lambda url: html[url])
    assert report["closed_pages_excluded"] == 1
    assert report["unverified_lead_count"] == 0
    assert report["verified_insolvency_sale_count"] == 0
