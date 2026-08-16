from opportunity_engine.discovery.sweden_blinto import build_blinto_clothing_queries
from opportunity_engine.discovery.sweden_klaravik import build_klaravik_clothing_queries


def _query_map(queries):
    return {query.query_id: query.query for query in queries}


def test_blinto_query_pack_targets_commercial_inventory_without_known_waste():
    queries = build_blinto_clothing_queries()
    query_texts = [query.query for query in queries]
    by_id = _query_map(queries)

    assert len(queries) == 8
    assert len(set(query_texts)) == 8
    assert all(text.startswith("site:blinto.se/auction ") for text in query_texts)

    assert '"överskott av nya kläder"' not in " ".join(query_texts)
    assert "varselkläder parti totalt" not in " ".join(query_texts)
    assert "secondhand kläder parti" not in " ".join(query_texts)

    assert "restlager kläder" in by_id["se-bl-03"]
    assert "restparti arbetskläder varselkläder" in by_id["se-bl-07"]
    assert "lagerparti kläder skor" in by_id["se-bl-08"]


def test_klaravik_query_pack_replaces_zero_yield_phrases_with_stock_intent():
    queries = build_klaravik_clothing_queries()
    query_texts = [query.query for query in queries]
    by_id = _query_map(queries)

    assert len(queries) == 8
    assert len(set(query_texts)) == 8
    assert all(
        text.startswith("site:klaravik.se/auktion/produkt ")
        for text in query_texts
    )

    joined = " ".join(query_texts)
    assert '"kläder och skor"' not in joined
    assert "secondhand kläder skor" not in joined

    assert "varulager kläder skor" in by_id["se-kl-02"]
    assert "butikslager kläder parti" in by_id["se-kl-07"]
