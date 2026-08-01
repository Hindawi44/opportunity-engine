from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_klaravik import (
    KlaravikPrefetchedSearchProvider,
    build_klaravik_clothing_queries,
    klaravik_gate_decision,
)


def _hit(title: str, url: str, description: str) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        description=description,
        provider="Brave Search",
    )


def test_gate_rejects_clothing_alarm_equipment_as_non_inventory() -> None:
    decision = klaravik_gate_decision(
        _hit(
            "Butikslarm för kläder etc",
            "https://www.klaravik.se/auktion/produkt/butikslarm-for-klader-etc/",
            "125 larmtaggar och avlarmningsenhet från sportbutik i konkurs.",
        )
    )

    assert decision.accepted is False
    assert decision.reason == "clothing-related equipment is not clothing inventory"


class _Provider:
    name = "fake"

    def __init__(self, query: str, hit: SearchHit) -> None:
        self.query = query
        self.hit = hit

    def search(self, query: str, *, count: int = 10):
        return (self.hit,) if query == self.query else ()


def test_accepted_source_hit_gets_conservative_classifier_aliases() -> None:
    query = build_klaravik_clothing_queries(1)[0]
    hit = _hit(
        "Herraccessoarer, helt varulager med nya produkter",
        "https://www.klaravik.se/auktion/produkt/herraccessoarer-helt-varulager-med-nya-produkter-se-listor/",
        "Helt varulager med nya accessoarer och produkter.",
    )
    provider = KlaravikPrefetchedSearchProvider(
        _Provider(query.query, hit),
        queries=(query,),
        request_budget=1,
    )

    results = provider.search(query.query, count=10)

    assert len(results) == 1
    assert "source policy aliases: klær vareparti auksjon" in results[0].description
