import pytest

from opportunity_engine.discovery.clothing_inventory_search import DiscoveryQuery
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.source_targeted_retrieval import (
    SourceTargetedSearchProvider,
    source_gate_decision,
)


class StubProvider:
    name = "Stub Search"

    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, *, count=10):
        self.calls.append((query, count))
        return self.results.get(query, ())


def _query(query_id, text, intent="SALE_INTENT"):
    return DiscoveryQuery(
        query_id,
        "COMPANY_BANKRUPTCY",
        intent,
        "CLOTHING_INVENTORY",
        text,
    )


def test_gate_accepts_axl_active_sale_channel_but_rejects_generic_homepage():
    query = _query(
        "reference-axl",
        'site:norskavvikling.no "AXL Sport Og Fritid" Kolvereid',
    )
    accepted = source_gate_decision(
        SearchHit(
            "AXL Sport Og Fritid Kolvereid",
            "https://norskavvikling.no/",
            "STATUS: AKTIV. KONKURSSALG PÅGÅR. Klær og sport og fritid.",
        ),
        query,
    )
    rejected = source_gate_decision(
        SearchHit(
            "Norsk Avvikling",
            "https://norskavvikling.no/",
            "Vi kjøper og selger konkursbo.",
        ),
        query,
    )

    assert accepted.accepted is True
    assert accepted.source_class == "SALE_CHANNEL_SOURCE"
    assert rejected.accepted is False


def test_gate_accepts_specific_finn_item_only():
    query = _query(
        "sale-02",
        'site:finn.no/recommerce/forsale/item "hele lageret" klær',
    )
    item = source_gate_decision(
        SearchHit(
            "Stort klesparti",
            "https://www.finn.no/recommerce/forsale/item/468298756?utm_source=test",
            "Klær, sko og vesker selges samlet.",
        ),
        query,
    )
    search_page = source_gate_decision(
        SearchHit(
            "Klær til salgs",
            "https://www.finn.no/recommerce/forsale/search?q=kl%C3%A6r",
            "Søkeresultater.",
        ),
        query,
    )

    assert item.accepted is True
    assert item.canonical_url == "https://finn.no/recommerce/forsale/item/468298756"
    assert search_page.accepted is False


def test_gate_rejects_editorial_auction_pages_before_classification():
    query = _query("sale-03", "site:auksjonen.no vareparti klær auksjon")
    decision = source_gate_decision(
        SearchHit(
            "Nyheter om konkurser",
            "https://auksjonen.no/nyheter/konkursmarkedet",
            "Artikkel om markedet.",
        ),
        query,
    )

    assert decision.accepted is False
    assert decision.reason == "editorial or generic path"


def test_gate_accepts_specific_registry_pages_as_event_sources():
    query = _query(
        "reference-tommeliten",
        'site:virksomhet.brreg.no "TOMMELITEN BARNEKLÆR AS" konkurs',
        "EVENT_LEAD",
    )
    decision = source_gate_decision(
        SearchHit(
            "TOMMELITEN BARNEKLÆR AS",
            "https://virksomhet.brreg.no/nb/oppslag/enheter/932113309",
            "Status Konkurs. Detaljhandel med klær.",
        ),
        query,
    )

    assert decision.accepted is True
    assert decision.source_class == "EVENT_REGISTRY_SOURCE"


def test_wrapper_enforces_budget_filters_noise_and_records_reference_recall():
    axl = _query(
        "reference-axl",
        'site:norskavvikling.no "AXL Sport Og Fritid" Kolvereid',
    )
    fiona = _query(
        "reference-by-fiona",
        'site:forvalt.no/Konkurs "ANNA J AS" Namsos',
        "EVENT_LEAD",
    )
    provider = StubProvider({
        axl.query: (
            SearchHit(
                "AXL Sport Og Fritid Kolvereid",
                "https://norskavvikling.no/",
                "STATUS: AKTIV. KONKURSSALG PÅGÅR. Klær og sport og fritid.",
            ),
            SearchHit(
                "Generisk nyhet",
                "https://norskavvikling.no/nyheter/test",
                "Artikkel.",
            ),
        ),
        fiona.query: (
            SearchHit(
                "ANNA J AS",
                "https://forvalt.no/Konkurs/Konkurser",
                "TRØNDELAG, Namsos. Detaljhandel med klær. Konkursåpning.",
            ),
        ),
    })
    wrapped = SourceTargetedSearchProvider(
        provider,
        queries=(axl, fiona),
        request_budget=2,
    )

    assert len(wrapped.search(axl.query, count=5)) == 1
    assert len(wrapped.search(fiona.query, count=5)) == 1
    diagnostics = wrapped.diagnostics()

    assert diagnostics["requests_made"] == 2
    assert diagnostics["raw_hits"] == 3
    assert diagnostics["accepted_hits"] == 2
    assert diagnostics["rejected_hits"] == 1
    assert diagnostics["reference_cases_recovered"] == [
        "axl-sport-og-fritid",
        "by-fiona",
    ]
    with pytest.raises(RuntimeError, match="budget exhausted"):
        wrapped.search(axl.query)


def test_wrapper_rejects_unregistered_query():
    query = _query("sale-03", "site:auksjonen.no vareparti klær auksjon")
    wrapped = SourceTargetedSearchProvider(
        StubProvider({}),
        queries=(query,),
        request_budget=1,
    )

    with pytest.raises(ValueError, match="not registered"):
        wrapped.search("site:example.com klær")
