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


class FailingProvider:
    name = "Failing Search"

    def search(self, query, *, count=10):
        raise RuntimeError("provider failure")


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
        "AXL Sport Og Fritid Kolvereid site:norskavvikling.no",
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
        "vareparti klær site:finn.no",
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
    query = _query("sale-03", "vareparti klær site:auksjonen.no")
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
        "TOMMELITEN BARNEKLÆR AS site:virksomhet.brreg.no",
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
        "AXL Sport Og Fritid Kolvereid site:norskavvikling.no",
    )
    fiona = _query(
        "reference-by-fiona",
        "ANNA J AS Namsos site:forvalt.no",
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
    assert diagnostics["zero_raw_hits"] is False
    assert diagnostics["reference_cases_recovered"] == [
        "axl-sport-og-fritid",
        "by-fiona",
    ]
    assert diagnostics["query_diagnostics"] == [
        {
            "query_id": "reference-axl",
            "query": axl.query,
            "raw_hits": 2,
            "accepted_hits": 1,
            "rejected_hits": 1,
            "error": None,
        },
        {
            "query_id": "reference-by-fiona",
            "query": fiona.query,
            "raw_hits": 1,
            "accepted_hits": 1,
            "rejected_hits": 0,
            "error": None,
        },
    ]
    with pytest.raises(RuntimeError, match="budget exhausted"):
        wrapped.search(axl.query)


def test_wrapper_distinguishes_zero_provider_hits_from_gate_rejections():
    query = _query("sale-03", "vareparti klær site:auksjonen.no")
    wrapped = SourceTargetedSearchProvider(
        StubProvider({}),
        queries=(query,),
        request_budget=1,
    )

    assert wrapped.search(query.query) == []
    diagnostics = wrapped.diagnostics()

    assert diagnostics["zero_raw_hits"] is True
    assert diagnostics["raw_hits"] == 0
    assert diagnostics["rejected_hits"] == 0
    assert diagnostics["rejection_reasons"] == {}
    assert diagnostics["query_diagnostics"][0]["raw_hits"] == 0


def test_wrapper_records_provider_error_by_query_before_reraising():
    query = _query("sale-03", "vareparti klær site:auksjonen.no")
    wrapped = SourceTargetedSearchProvider(
        FailingProvider(),
        queries=(query,),
        request_budget=1,
    )

    with pytest.raises(RuntimeError, match="provider failure"):
        wrapped.search(query.query)

    diagnostics = wrapped.diagnostics()
    assert diagnostics["query_diagnostics"][0]["error"] == "provider failure"


def test_wrapper_rejects_unregistered_query():
    query = _query("sale-03", "vareparti klær site:auksjonen.no")
    wrapped = SourceTargetedSearchProvider(
        StubProvider({}),
        queries=(query,),
        request_budget=1,
    )

    with pytest.raises(ValueError, match="not registered"):
        wrapped.search("klær site:example.com")
