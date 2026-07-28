from opportunity_engine.discovery.finn_indexed_rescue import (
    FINN_INDEXED_LISTING_QUERIES,
    extract_finn_item_id,
    run_finn_indexed_retrieval,
)
from opportunity_engine.discovery.search_provider import SearchHit


class FakeProvider:
    name = "Fake Brave"

    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, *, count=10):
        self.calls.append((query, count))
        return self.hits[:count]


def test_rescue_queries_copy_the_successful_manual_site_search_shape():
    assert len(FINN_INDEXED_LISTING_QUERIES) == 8
    assert {query.query_id for query in FINN_INDEXED_LISTING_QUERIES} == {
        f"finn-index-{number:02d}" for number in range(1, 9)
    }
    for query in FINN_INDEXED_LISTING_QUERIES:
        assert "site:finn.no/recommerce/forsale/item" in query.query
        assert '-"ønskes kjøpt"' in query.query
        assert "-kjøpes" in query.query
        assert query.asset_scope == "CLOTHING_INVENTORY"


def test_extract_finn_item_id_accepts_only_specific_item_urls():
    assert extract_finn_item_id(
        "https://www.finn.no/recommerce/forsale/item/457076453?utm_source=x"
    ) == "457076453"
    assert extract_finn_item_id(
        "https://www.finn.no/bap/forsale/ad.html?finnkode=431015947"
    ) == "431015947"
    assert extract_finn_item_id(
        "https://www.finn.no/recommerce/forsale/search?q=vareparti"
    ) is None
    assert extract_finn_item_id("https://example.no/item/457076453") is None
    assert extract_finn_item_id("http://www.finn.no/recommerce/forsale/item/1") is None


def test_rescue_retrieves_manual_style_candidates_before_strict_verification():
    hits = [
        SearchHit(
            "15 nye Rains jakker selges samlet",
            "https://www.finn.no/recommerce/forsale/item/457076453",
            "15 stk nye jakker med merkelapp.",
            "Fake Brave",
        ),
        SearchHit(
            "Ca. 150 par nye damesko selges samlet",
            "https://www.finn.no/recommerce/forsale/item/431015947",
            "Stort parti pumps og loafers.",
            "Fake Brave",
        ),
        SearchHit(
            "Klær, sko og vesker med stativ",
            "https://www.finn.no/recommerce/forsale/item/468298756",
            "Stort parti klær, sko og vesker selges samlet.",
            "Fake Brave",
        ),
        SearchHit(
            "80 arbeidsbukser i populære størrelser",
            "https://www.finn.no/recommerce/forsale/item/470000001",
            "Partisalg: 80 stk arbeidsbukser.",
            "Fake Brave",
        ),
        SearchHit(
            "300-400 nye damebukser",
            "https://www.finn.no/recommerce/forsale/item/470000002",
            "Restlager med 300 stk damebukser selges samlet.",
            "Fake Brave",
        ),
        SearchHit(
            "Stort parti Rains jakker",
            "https://www.finn.no/recommerce/forsale/item/470000003",
            "Flere nye jakker selges samlet som ett parti.",
            "Fake Brave",
        ),
        SearchHit(
            "Ønskes kjøpt: parti med klær",
            "https://www.finn.no/recommerce/forsale/item/470000004",
            "Kjøpes, jeg søker etter et varelager.",
            "Fake Brave",
        ),
        SearchHit(
            "FINN søkeresultat",
            "https://www.finn.no/recommerce/forsale/search?q=vareparti",
            "Kategori og filtre.",
            "Fake Brave",
        ),
    ]
    provider = FakeProvider(hits)

    report = run_finn_indexed_retrieval(
        provider,
        queries=FINN_INDEXED_LISTING_QUERIES[:1],
        results_per_query=20,
        minimum_specific_items=5,
    )

    assert provider.calls[0][1] == 20
    assert report["hits_received"] == 8
    assert report["non_finn_item_hits_excluded"] == 1
    assert report["unique_finn_item_urls"] == 7
    assert report["retrieval_eligible_items"] == 6
    assert report["rescue_success"] is True
    assert report["reference_items_recovered"] == [
        "431015947",
        "457076453",
        "468298756",
    ]
    assert report["reference_recall"] == 1.0
    assert report["page_verification_performed"] is False
    assert report["analysis_engine_used"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_purchase_decision"] is False

    by_id = {item["item_id"]: item for item in report["items"]}
    assert by_id["470000004"]["buyer_intent"] is True
    assert by_id["470000004"]["retrieval_eligible"] is False
    assert by_id["457076453"]["retrieval_eligible"] is True


def test_rescue_fails_objectively_below_the_fixed_minimum():
    provider = FakeProvider([
        SearchHit(
            "15 nye Rains jakker selges samlet",
            "https://www.finn.no/recommerce/forsale/item/457076453",
            "15 stk nye jakker.",
            "Fake Brave",
        )
    ])

    report = run_finn_indexed_retrieval(
        provider,
        queries=FINN_INDEXED_LISTING_QUERIES[:1],
        minimum_specific_items=5,
    )

    assert report["retrieval_eligible_items"] == 1
    assert report["rescue_success"] is False
