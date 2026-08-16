from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from opportunity_engine.discovery.netherlands_case_memory_adapter import (
    build_netherlands_case_memory_adapter,
)
from opportunity_engine.discovery.netherlands_entity_identity_resolution import (
    ENGINE_VERSION,
    resolve_netherlands_entity_identities,
)
from opportunity_engine.discovery.netherlands_market_discovery import (
    NETHERLANDS_DISCOVERY_QUERIES,
    netherlands_signal_from_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit


NOW = datetime(2026, 8, 16, 14, 0, tzinfo=timezone.utc)


def _early_signal() -> dict:
    query = next(
        item
        for item in NETHERLANDS_DISCOVERY_QUERIES
        if item.intent == "INSOLVENCY_LIQUIDATION"
    )
    signal = netherlands_signal_from_hit(
        SearchHit(
            title=(
                "Deze week failliet: winkel in Mall of the Netherlands "
                "failliet verklaard - Omroep West"
            ),
            url=(
                "https://www.omroepwest.nl/economie/5132174/"
                "deze-week-failliet-winkel-in-mall-of-the-netherlands-failliet-verklaard"
            ),
            description=(
                "Deze week is het doek gevallen voor een kledingwinkel in Westfield Mall "
                "of the Netherlands in Leidschendam. Volgens de curator is de omzet te laag."
            ),
            provider="Fake Brave",
        ),
        query=query,
        rank=10,
        observed_at=NOW,
    )
    assert signal is not None
    payload = signal.model_dump(mode="json")
    assert payload["company_name"] is None
    return payload


class FakeProvider:
    def __init__(self, *, official: bool = True, same_domain_only: bool = False) -> None:
        self.official = official
        self.same_domain_only = same_domain_only
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        if "bedrijfsnaam" in query:
            return [
                SearchHit(
                    title="Deze week failliet: winkel in Mall of the Netherlands failliet verklaard",
                    url="https://zuidholland.headliner.nl/item/mall-failliet",
                    description=(
                        "In Leidschendam is de kledingwinkel van MD Fashion Netherlands "
                        "failliet gegaan. Ook Levolt Fysio B.V. ging failliet."
                    ),
                    provider="Fake Brave",
                )
            ]

        if "md fashion netherlands" in query.casefold():
            if self.same_domain_only:
                return [
                    SearchHit(
                        title="MD FASHION NETHERLANDS B.V. failliet",
                        url="https://zuidholland.headliner.nl/item/md-fashion",
                        description="Faillissement MD Fashion Netherlands B.V.",
                        provider="Fake Brave",
                    )
                ]
            hits = [
                SearchHit(
                    title="Faillissement MD FASHION NETHERLANDS B.V.",
                    url="https://www.claimsagent.nl/nl/Insolvencies/Details/35980",
                    description=(
                        "MD FASHION NETHERLANDS B.V. te Leidschendam. "
                        "KvK-nummer 93290497. Insolventienummer F.09/26/268."
                    ),
                    provider="Fake Brave",
                ),
                SearchHit(
                    title="Md Fashion Netherlands B.V. - faillissement",
                    url="https://www.faillissementsdossier.nl/nl/faillissement/12345",
                    description=(
                        "Md Fashion Netherlands B.V. failliet verklaard. KvK 93290497."
                    ),
                    provider="Fake Brave",
                ),
            ]
            if self.official:
                hits.append(
                    SearchHit(
                        title="MD FASHION NETHERLANDS B.V. - Centraal Insolventieregister",
                        url="https://insolventies.rechtspraak.nl/#!/details/09.26.268",
                        description=(
                            "Faillissement MD FASHION NETHERLANDS B.V. "
                            "KvK 93290497 F.09/26/268."
                        ),
                        provider="Fake Brave",
                    )
                )
            return hits

        return []


def test_resolves_live_shape_to_officially_confirmed_company_identity() -> None:
    provider = FakeProvider(official=True)
    report = resolve_netherlands_entity_identities(
        [_early_signal()],
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key: provider,
        observed_at=NOW,
        max_signals=1,
    )

    assert report["status"] == "SUCCESS"
    assert report["resolved_identity_count"] == 1
    assert report["officially_confirmed_identity_count"] == 1
    assert report["search_request_count"] >= 2

    enriched = report["enriched_signals"][0]
    assert enriched["company_name"].casefold().startswith("md fashion netherlands")
    metadata = enriched["metadata"]
    assert metadata["netherlands_entity_identity_resolution"] == ENGINE_VERSION
    assert metadata["entity_identity_resolution_status"] == "RESOLVED_OFFICIAL_REGISTER"
    assert metadata["identity_official_rechtspraak_confirmed"] is True
    assert metadata["identity_kvk_numbers"] == ["93290497"]
    assert metadata["identity_insolvency_ids"] == ["F.09/26/268"]
    assert metadata["promotion_to_opportunity_allowed"] is False
    assert metadata["automatic_purchase"] is False


def test_two_independent_public_domains_can_resolve_without_official_result() -> None:
    provider = FakeProvider(official=False)
    report = resolve_netherlands_entity_identities(
        [_early_signal()],
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key: provider,
        observed_at=NOW,
        max_signals=1,
    )

    assert report["resolved_identity_count"] == 1
    assert report["officially_confirmed_identity_count"] == 0
    assert report["corroborated_public_identity_count"] == 1
    resolution = report["resolutions"][0]
    assert resolution["status"] == "RESOLVED_CORROBORATED_PUBLIC"
    assert resolution["independent_domain_count"] >= 2


def test_one_domain_is_not_enough_and_company_name_stays_empty() -> None:
    provider = FakeProvider(official=False, same_domain_only=True)
    report = resolve_netherlands_entity_identities(
        [_early_signal()],
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key: provider,
        observed_at=NOW,
        max_signals=1,
    )

    assert report["resolved_identity_count"] == 0
    assert report["status"] == "VALID_ZERO_NO_IDENTITIES_RESOLVED"
    assert report["enriched_signals"][0]["company_name"] is None
    assert report["resolutions"][0]["status"] == "UNRESOLVED_INSUFFICIENT_CORROBORATION"


def test_resolved_identity_can_seed_existing_memory_adapter_without_parallel_case_engine() -> None:
    provider = FakeProvider(official=True)
    identity = resolve_netherlands_entity_identities(
        [_early_signal()],
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key: provider,
        observed_at=NOW,
        max_signals=1,
    )
    adapter = build_netherlands_case_memory_adapter(
        identity["enriched_signals"],
        observed_at=NOW,
    )

    assert adapter["persistent_case_count"] == 1
    case = adapter["cases"][0]
    assert case["entity_key"] == "md fashion netherlands"
    assert case["case_title"].casefold().startswith("md fashion netherlands")
    assert adapter["promotion_to_opportunity_allowed"] is False


def test_existing_explicit_company_identity_is_not_researched() -> None:
    signal = _early_signal()
    signal["company_name"] = "Known Retail B.V."
    provider = FakeProvider()
    report = resolve_netherlands_entity_identities(
        [signal],
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda market, key: provider,
        observed_at=NOW,
    )
    assert provider.calls == []
    assert report["resolutions"][0]["status"] == "SKIPPED_ALREADY_IDENTIFIED"
    assert report["enriched_signals"][0]["company_name"] == "Known Retail B.V."


def test_missing_api_key_is_safe_and_never_invents_identity() -> None:
    report = resolve_netherlands_entity_identities(
        [_early_signal()],
        environment={},
        observed_at=NOW,
    )
    assert report["status"] == "SKIPPED_NO_API_KEY"
    assert report["resolved_identity_count"] == 0
    assert report["enriched_signals"][0]["company_name"] is None
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False
