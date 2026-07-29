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
    query = _query("sale-02", "vareparti klær site:finn.no")
    item = source_gate_decision(
        SearchHit(
            "Stort klesparti",
            "https://www.finn.no/recommerce/forsale/item/468298756?utm_source=test",
            "Klær, sko og vesker selges samlet.",
        ),
        query,
    )
    legacy_item = source_gate_decision(
        SearchHit(
            "Varelager med klær",
            "https://www.finn.no/bap/forsale/ad.html?finnkode=468298756",
            "Vareparti klær selges.",
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
    assert legacy_item.accepted is True
    assert search_page.accepted is False


def test_gate_accepts_only_specific_auction_and_clearance_item_paths():
    auction_query = _query("sale-03", "vareparti klær site:auksjonen.no")
    auction_item = source_gate_decision(
        SearchHit(
            "Vareparti med arbeidstøy og diverse konkursbo",
            "https://auksjonen.no/auksjon/vareparti_med_arbeidstoy/185420",
            "Auksjon av klær og arbeidstøy fra konkursbo.",
        ),
        auction_query,
    )
    auction_index = source_gate_decision(
        SearchHit(
            "Varelager",
            "https://auksjonen.no/auksjoner/varelager",
            "Alle auksjoner med varelager.",
        ),
        auction_query,
    )

    clearance_query = _query("sale-04", "restlager klær site:stadssalg.no")
    clearance_item = source_gate_decision(
        SearchHit(
            "Restlager med klær",
            "https://stadssalg.no/items/52548",
            "Klær og sko selges som vareparti.",
        ),
        clearance_query,
    )
    clearance_index = source_gate_decision(
        SearchHit(
            "Alle varer",
            "https://stadssalg.no/items",
            "Oversikt over varer.",
        ),
        clearance_query,
    )

    assert auction_item.accepted is True
    assert auction_index.accepted is False
    assert auction_index.reason == "Auksjonen URL is not one specific auction item page"
    assert clearance_item.accepted is True
    assert clearance_index.accepted is False
    assert clearance_index.reason == "Stadssalg URL is not one specific item page"


def test_gate_rejects_unrelated_liquidation_products():
    query = _query("sale-05", "konkursbo klær site:norskavvikling.no")
    vehicle = source_gate_decision(
        SearchHit(
            "Volkswagen Caddy 2.0 4Motion",
            "https://norskavvikling.no/produkt/volkswagen-caddy-2-0-4motion",
            "Bil til salgs fra konkursbo.",
        ),
        query,
    )
    clothing = source_gate_decision(
        SearchHit(
            "Vareparti med sportsklær",
            "https://norskavvikling.no/produkt/vareparti-sportsklaer",
            "Konkurssalg av klær og sko.",
        ),
        query,
    )

    assert vehicle.accepted is False
    assert vehicle.reason == "liquidation product page lacks clothing sale evidence"
    assert clothing.accepted is True


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


def test_gate_accepts_specific_registry_pages_with_clothing_event_evidence():
    brreg_query = _query(
        "reference-tommeliten",
        "TOMMELITEN BARNEKLÆR AS site:virksomhet.brreg.no",
        "EVENT_LEAD",
    )
    brreg = source_gate_decision(
        SearchHit(
            "TOMMELITEN BARNEKLÆR AS",
            "https://virksomhet.brreg.no/nb/oppslag/enheter/932113309",
            "Status Konkurs. Detaljhandel med klær.",
        ),
        brreg_query,
    )

    forvalt_query = _query(
        "reference-by-fiona",
        "989324217 site:forvalt.no",
        "EVENT_LEAD",
    )
    forvalt = source_gate_decision(
        SearchHit(
            "ANNA J AS",
            "https://forvalt.no/Konkurs/Firmadetaljer/989324217/657362",
            "Namsos. Detaljhandel med klær. Konkursåpning.",
        ),
        forvalt_query,
    )
    forvalt_index = source_gate_decision(
        SearchHit(
            "Konkurser",
            "https://forvalt.no/Konkurs/Konkurser",
            "Liste over konkurser i Norge.",
        ),
        forvalt_query,
    )

    konkurs_query = _query(
        "lead-03",
        "klesbutikk konkurs site:konkurs.app",
        "EVENT_LEAD",
    )
    konkurs_bo = source_gate_decision(
        SearchHit(
            "Klesbutikk AS konkursbo",
            "https://konkurs.app/konkursbo/937550006",
            "Konkursåpning for detaljhandel med klær.",
        ),
        konkurs_query,
    )
    konkurs_trends = source_gate_decision(
        SearchHit(
            "Konkurstrender",
            "https://konkurs.app/trender",
            "Trender for konkurser.",
        ),
        konkurs_query,
    )

    assert brreg.accepted is True
    assert brreg.source_class == "EVENT_REGISTRY_SOURCE"
    assert forvalt.accepted is True
    assert forvalt_index.accepted is False
    assert konkurs_bo.accepted is True
    assert konkurs_trends.accepted is False


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
                "https://forvalt.no/Konkurs/Firmadetaljer/989324217/657362",
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
