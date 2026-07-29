from opportunity_engine.discovery.finn_indexed_rescue_queries import FINN_INDEXED_BROAD_RESCUE_QUERIES


def test_broad_rescue_queries_use_supported_domain_scope():
    assert len(FINN_INDEXED_BROAD_RESCUE_QUERIES) == 8
    ids = [query.query_id for query in FINN_INDEXED_BROAD_RESCUE_QUERIES]
    assert ids == [
        "finn-broad-01",
        "finn-broad-02",
        "finn-broad-03",
        "finn-broad-04",
        "finn-broad-05",
        "finn-broad-06",
        "finn-broad-07",
        "finn-broad-08",
    ]
    for query in FINN_INDEXED_BROAD_RESCUE_QUERIES:
        assert "site:finn.no" in query.query
        assert "site:finn.no/" not in query.query
        assert query.asset_scope == "CLOTHING_INVENTORY"
