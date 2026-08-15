from __future__ import annotations

from opportunity_engine.discovery.cross_source_scent_entity_gated_v1 import (
    collect_entity_gated_cross_source_scent_expansion_v2,
)
from opportunity_engine.discovery.entity_scent_quality_gate_v1 import (
    build_entity_scent_quality_gate,
)
from opportunity_engine.discovery.search_provider import SearchHit


def _candidate(*, title: str, url: str, score: int = 80, market: str = "DE") -> dict[str, object]:
    return {
        "market_code": market,
        "label": title,
        "score": score,
        "source_url": url,
        "source_title": title,
        "parent_query_id": "test-query",
    }


def test_single_explicit_company_shape_can_qualify() -> None:
    gate = build_entity_scent_quality_gate(
        [
            _candidate(
                title="Schümer Textil GmbH - Insolvenz und Warenbestand",
                url="https://news.example/schuemer",
                score=70,
            )
        ]
    )

    assert gate["qualified_entity_count"] == 1
    scent = gate["qualified_entity_scents"][0]
    assert scent["label"] == "Schümer Textil GmbH"
    assert scent["identity_qualification_reason"] == "EXPLICIT_COMPANY_SHAPE"
    assert scent["independent_source_count"] == 1


def test_single_headline_entity_is_demoted_even_with_high_score() -> None:
    gate = build_entity_scent_quality_gate(
        [
            _candidate(
                title="Nordlicht Fashion - Insolvenz und Warenbestand",
                url="https://one.example/nordlicht",
                score=95,
            )
        ]
    )

    assert gate["qualified_entity_count"] == 0
    assert gate["entity_cluster_count"] == 0
    assert gate["source_intelligence_count"] == 1
    item = gate["source_intelligence"][0]
    assert item["rejection_reason"] == "UNCORROBORATED_HEADLINE_ENTITY"
    assert item["observed_independent_source_count"] == 1
    assert item["required_independent_source_count"] == 2


def test_headline_entity_qualifies_after_two_independent_sources() -> None:
    gate = build_entity_scent_quality_gate(
        [
            _candidate(
                title="Nordlicht Fashion - Insolvenz und Warenbestand",
                url="https://one.example/nordlicht",
                score=65,
            ),
            _candidate(
                title="Nordlicht Fashion - Insolvenz eröffnet",
                url="https://two.example/nordlicht",
                score=60,
            ),
        ]
    )

    assert gate["qualified_entity_count"] == 1
    scent = gate["qualified_entity_scents"][0]
    assert scent["label"] == "Nordlicht Fashion"
    assert scent["identity_qualification_reason"] == "CORROBORATED_HEADLINE_ENTITY"
    assert scent["independent_source_count"] == 2
    assert scent["qualified_for_follow_up"] is True


def test_run150_generic_headlines_are_source_intelligence() -> None:
    gate = build_entity_scent_quality_gate(
        [
            _candidate(
                title="ware Ankauf - Restposten und Bekleidung",
                url="https://generic-one.example/ware-ankauf",
                score=90,
            ),
            _candidate(
                title="traditionsreicher Mode-Kette - Insolvenz und Warenbestand",
                url="https://generic-two.example/mode-kette",
                score=90,
            ),
        ]
    )

    assert gate["qualified_entity_count"] == 0
    assert gate["source_intelligence_count"] == 2
    assert all(
        item["rejection_reason"] == "GENERIC_SOURCE_INTELLIGENCE"
        for item in gate["source_intelligence"]
    )


def test_uncorroborated_headline_does_not_spend_follow_up_request() -> None:
    calls: list[tuple[str, str]] = []

    class FakeProvider:
        name = "Fake Brave"

        def __init__(self, market: str) -> None:
            self.market = market

        def search(self, query: str, *, count: int = 10):
            calls.append((self.market, query))
            if self.market == "DE" and len([call for call in calls if call[0] == "DE"]) == 1:
                return [
                    SearchHit(
                        title="Nordlicht Fashion - Insolvenz und Warenbestand",
                        url="https://only-source.example/nordlicht",
                        description="Mode Bekleidung Insolvenz Warenbestand wird verkauft.",
                        provider="Brave Search",
                    )
                ]
            return []

    report = collect_entity_gated_cross_source_scent_expansion_v2(
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key, freshness: FakeProvider(market),
        max_requests=12,
    )

    assert report["requests_made"] == 6
    assert report["follow_up_request_count"] == 0
    assert report["followed_scent_count"] == 0
    assert report["strong_scent_count"] == 0
    assert report["entity_scent_quality_gate"]["source_intelligence_count"] >= 1
