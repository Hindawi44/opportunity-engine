from opportunity_engine.source_ingestion.auksjonen import build_snapshot as build_auksjonen_snapshot
from opportunity_engine.source_ingestion.auksjonen import parse_public_listings as parse_auksjonen
from opportunity_engine.source_ingestion.finn import build_snapshot as build_finn_snapshot
from opportunity_engine.source_ingestion.finn import parse_public_listings as parse_finn
from opportunity_engine.source_ingestion.multisource import merge_snapshots

CAPTURED_AT = "2026-07-24T12:00:00+00:00"

AUKSJONEN_HTML = '''
<html><body>
<a href="https://www.auksjonen.no/auksjon/berryalloc-route-66-123456">BerryAlloc Route 66 10 000 kr</a>
<a href="https://www.auksjonen.no/auksjon/verktoysett-234567">Verktøysett 6 500 kr</a>
</body></html>
'''

FINN_HTML = '''
<html><head><script type="application/ld+json">
{"@type":"ItemList","itemListElement":[
 {"@type":"Product","name":"Kontormøbler komplett","url":"https://www.finn.no/bap/forsale/ad.html?finnkode=400001001","offers":{"price":12000},"location":{"name":"Namsos"}},
 {"@type":"Product","name":"BerryAlloc Route 66","url":"https://www.finn.no/bap/forsale/ad.html?finnkode=400001002","offers":{"price":10000}}
]}
</script></head><body>
<a href="https://example.com/ad?finnkode=9">External 100 kr</a>
<a href="https://www.finn.no/bap/forsale/ad.html?finnkode=400001003">Missing price</a>
</body></html>
'''


def test_v36_multi_source_acceptance():
    auksjonen = build_auksjonen_snapshot(parse_auksjonen(AUKSJONEN_HTML), captured_at=CAPTURED_AT)
    finn = build_finn_snapshot(parse_finn(FINN_HTML), captured_at=CAPTURED_AT)
    merged = merge_snapshots([auksjonen, finn])

    assert [snapshot_source for snapshot_source in merged["sources"]] == ["Auksjonen.no", "FINN.no"]
    assert len(auksjonen["opportunities"]) == 2
    assert len(finn["opportunities"]) == 2
    assert merged["opportunities_received"] == 4
    assert merged["unique_opportunities"] == 3
    assert merged["duplicate_count"] == 1
    assert merged["automatic_purchase_decision"] is False

    for item in merged["opportunities"]:
        assert item["opportunity_id"]
        assert item["source"]["url"].startswith("https://")
        assert item["source"]["asking_price_nok"] > 0
        assert item["verified_cost_evidence"]["auction_fee_nok"] is None


def test_finn_rejects_nonpublic_and_missing_price():
    listings = parse_finn(FINN_HTML)
    assert {item.listing_id for item in listings} == {"400001001", "400001002"}
