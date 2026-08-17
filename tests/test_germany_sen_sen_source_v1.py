from __future__ import annotations

from collections import defaultdict

from opportunity_engine.discovery.germany_clothing_inventory import german_aliases
from opportunity_engine.discovery.germany_sen_sen import (
    SEN_SEN_HOST,
    SenSenPrefetchedSearchProvider,
    build_sen_sen_clothing_queries,
    canonicalize_sen_sen_detail_url,
    sen_sen_gate_decision,
)
from opportunity_engine.discovery.search_provider import SearchHit


TEXTILE_URL = (
    "https://www.sen-sen.de/php/"
    "t1113-Textil-Warenbestand%2C_Freizeit-_und_Arbeitskleidu%26overlang%3D"
)
RUN190_OBJECT_URL = (
    "https://www.sen-sen.de/php/"
    "o7580-1_Textilien-Warenbestand_aus_Insolvenz&subof=2.?"
    "ScrollNumber=0&snumber=2&auktionflag=0&auktion=3590&searchstring=*"
)


class FakeProvider:
    name = "fake"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = defaultdict(int)

    def search(self, query: str, *, count: int = 10):
        self.calls[query] += 1
        return tuple(self.hits_by_query.get(query, ()))[:count]


def _textile_hit(description: str = "") -> SearchHit:
    return SearchHit(
        title="Textil-Warenbestand, Freizeit- und Arbeitskleidung",
        url=TEXTILE_URL,
        description=(
            description
            or "Liquidationsverkauf aus Insolvenz. EK-Wert ca. 100.000 EUR. "
            "Liste wird auf Anfrage zugesendet. Verkauf gegen Gebot!"
        ),
        provider="fixture",
    )


def _run190_object_hit(description: str = "") -> SearchHit:
    return SearchHit(
        title="Sen & Sen: 1 Textilien-Warenbestand aus Insolvenz",
        url=RUN190_OBJECT_URL,
        description=description or "Komplett-Verkauf bevorzugt. Weitere Infos und Bilder auf Anfrage.",
        provider="run190-fixture",
    )


def test_canonicalizes_only_exact_sen_sen_detail_pages() -> None:
    identity = canonicalize_sen_sen_detail_url(TEXTILE_URL)
    assert identity is not None
    canonical, event_id = identity
    assert canonical.startswith("https://sen-sen.de/php/t1113-")
    assert event_id == "1113"

    object_identity = canonicalize_sen_sen_detail_url(RUN190_OBJECT_URL)
    assert object_identity is not None
    object_canonical, object_id = object_identity
    assert object_canonical.startswith("https://sen-sen.de/php/o7580-")
    assert object_id == "o7580"

    assert canonicalize_sen_sen_detail_url(
        "https://www.sen-sen.de/php/dilib.php?showfolder=term&snumber=108"
    ) is None
    assert canonicalize_sen_sen_detail_url(
        "https://sen-sen.de/php/uploads/Warenbestand%2021Juli2022.pdf"
    ) is None
    assert canonicalize_sen_sen_detail_url("https://example.com/php/t1113-sale") is None


def test_accepts_realistic_textile_inventory_liquidation_hit() -> None:
    decision = sen_sen_gate_decision(_textile_hit())
    assert decision.accepted is True
    assert decision.event_id == "1113"
    assert decision.reason == "specific Sen & Sen clothing-inventory liquidation lead"


def test_accepts_run190_exact_object_inventory_page_as_lead() -> None:
    decision = sen_sen_gate_decision(_run190_object_hit())
    assert decision.accepted is True
    assert decision.event_id == "o7580"
    assert decision.canonical_url.startswith("https://sen-sen.de/php/o7580-")
    assert decision.reason == "specific Sen & Sen clothing-inventory liquidation lead"


def test_object_page_still_requires_clothing_evidence() -> None:
    hit = SearchHit(
        title="Sen & Sen: 1 Warenbestand",
        url="https://www.sen-sen.de/php/o3475-1_Warenbestand",
        description="Warenbestand aus Insolvenz. Komplett-Verkauf bevorzugt.",
    )
    decision = sen_sen_gate_decision(hit)
    assert decision.accepted is False
    assert decision.event_id == "o3475"
    assert decision.reason == "specific title lacks clothing evidence"


def test_rejects_generic_list_page_even_if_snippet_mentions_clothing() -> None:
    hit = SearchHit(
        title="Sen & Sen - Online-Auktionen und Insolvenzverkäufe",
        url="https://www.sen-sen.de/php/dilib.php?showfolder=term&snumber=108",
        description="Textil-Warenbestand, Freizeit- und Arbeitskleidung Verkauf gegen Gebot",
    )
    decision = sen_sen_gate_decision(hit)
    assert decision.accepted is False
    assert "not one specific public sale page" in decision.reason


def test_rejects_non_clothing_liquidation_detail() -> None:
    hit = SearchHit(
        title="Komplettverkauf Metallbetrieb",
        url="https://www.sen-sen.de/php/t999-Komplettverkauf_Metallbetrieb",
        description="Insolvenzverkauf Maschinen, Werkbank und Lagereinrichtung",
    )
    decision = sen_sen_gate_decision(hit)
    assert decision.accepted is False
    assert decision.reason == "non-clothing liquidation result"


def test_explicit_ended_result_suppresses_same_event_across_query_pack() -> None:
    queries = build_sen_sen_clothing_queries(2)
    live = _textile_hit()
    ended = _textile_hit("Liquidationsverkauf aus Insolvenz. Warenbestand verkauft.")
    fake = FakeProvider({
        queries[0].query: (live,),
        queries[1].query: (ended,),
    })
    provider = SenSenPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=2,
    )

    assert provider.search(queries[0].query, count=10) == ()
    assert provider.search(queries[1].query, count=10) == ()
    diagnostics = provider.diagnostics()
    assert diagnostics["requests_made"] == 2
    assert diagnostics["raw_hits"] == 2
    assert diagnostics["accepted_hits"] == 0
    assert diagnostics["historical_event_ids"] == ["1113"]


def test_run190_object_page_deduplicates_across_queries() -> None:
    queries = build_sen_sen_clothing_queries(3)
    hit = _run190_object_hit()
    fake = FakeProvider({query.query: (hit,) for query in queries})
    provider = SenSenPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=3,
    )

    first = provider.search(queries[0].query, count=10)
    assert len(first) == 1
    assert provider.search(queries[1].query, count=10) == ()
    assert provider.search(queries[2].query, count=10) == ()
    diagnostics = provider.diagnostics()
    assert diagnostics["accepted_hits"] == 1
    assert diagnostics["accepted_event_ids"] == ["o7580"]
    assert diagnostics["accepted_urls"] == [first[0].url]


def test_query_pack_deduplicates_one_exact_sale_across_multiple_queries() -> None:
    queries = build_sen_sen_clothing_queries(2)
    hit = _textile_hit()
    fake = FakeProvider({query.query: (hit,) for query in queries})
    provider = SenSenPrefetchedSearchProvider(
        fake,
        queries=queries,
        request_budget=2,
    )

    first = provider.search(queries[0].query, count=10)
    second = provider.search(queries[1].query, count=10)
    assert len(first) == 1
    assert second == ()
    diagnostics = provider.diagnostics()
    assert diagnostics["accepted_hits"] == 1
    assert diagnostics["accepted_event_ids"] == ["1113"]
    assert diagnostics["accepted_urls"] == [first[0].url]


def test_german_aliases_recognize_liquidation_offer_vocabulary() -> None:
    aliases = german_aliases(
        "Textil-Warenbestand Arbeitskleidung. Liquidationsverkauf aus Insolvenz. "
        "Verkauf gegen Gebot!"
    )
    assert "varelager" in aliases
    assert "arbeidstøy" in aliases
    assert "likvidasjon til salgs" in aliases
    assert "til salgs budrunde" in aliases
    assert "konkurs" in aliases


def test_source_policy_never_changes_transaction_scope() -> None:
    queries = build_sen_sen_clothing_queries(1)
    provider = SenSenPrefetchedSearchProvider(
        FakeProvider({queries[0].query: (_textile_hit(),)}),
        queries=queries,
        request_budget=1,
    )
    provider.search(queries[0].query, count=10)
    diagnostics = provider.diagnostics()
    assert SEN_SEN_HOST == "sen-sen.de"
    assert diagnostics["automatic_contact"] is False
    assert diagnostics["automatic_offer"] is False
    assert diagnostics["automatic_purchase"] is False
    assert diagnostics["automatic_payment"] is False
