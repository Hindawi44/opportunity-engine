from opportunity_engine.ods.finn import FinnApiClient


ATOM = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>urn:finn:123456</id>
    <title>Butikkinnredning med hyller</title>
    <summary>Komplett innredning for butikk</summary>
    <updated>2026-07-22T08:00:00Z</updated>
    <link rel="alternate" href="https://www.finn.no/bap/forsale/ad.html?finnkode=123456" />
  </entry>
  <entry>
    <id>urn:finn:999999</id>
    <title>Personbil selges</title>
    <summary>Brukt bil</summary>
    <updated>2026-07-22T08:00:00Z</updated>
    <link rel="alternate" href="https://www.finn.no/car/used/ad.html?finnkode=999999" />
  </entry>
</feed>'''


def test_targeted_search_deduplicates_and_excludes_vehicles():
    calls = []

    def transport(url, timeout, headers):
        calls.append(url)
        return ATOM

    client = FinnApiClient(api_key="key", org_id="org", transport=transport)
    documents = client.search_targeted_business_listings(rows_per_query=5)

    assert len(documents) == 1
    assert documents[0].title == "Butikkinnredning med hyller"
    assert documents[0].metadata["targeted_business_listing"] is True
    assert documents[0].metadata["discovery_query"]
    assert documents[0].url and "finnkode=123456" in documents[0].url
    assert len(calls) > 1


def test_rows_per_query_is_bounded():
    client = FinnApiClient(api_key="key", org_id="org", transport=lambda *_: ATOM)

    try:
        client.search_targeted_business_listings(rows_per_query=0)
    except ValueError as exc:
        assert "rows_per_query" in str(exc)
    else:
        raise AssertionError("expected ValueError")
