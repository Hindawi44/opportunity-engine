import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichment,
)
from opportunity_engine.discovery.pre_market_sale_channel_search import (
    build_sale_channel_queries,
    classify_search_hit,
    run_sale_channel_search,
    write_sale_channel_artifacts,
)
from opportunity_engine.discovery.search_provider import SearchHit


def enrichment() -> EstateManagerEnrichment:
    return EstateManagerEnrichment(
        captured_at="2026-07-30T10:00:00+00:00",
        estate_orgnr="938018014",
        estate_name="MENSWEAR NORGE AS KONKURSBO",
        debtor_orgnr="986425284",
        debtor_name="MENSWEAR NORGE AS",
        opened_date="2026-07-01",
        industry_code="46.420",
        industry_description="Engroshandel med klær og skotøy",
        municipality="OSLO",
        estate_manager_name="Adv. Example Manager",
        source_endpoint="https://konkurs.app/api/konkursbo/938018014",
    )


class FakeProvider:
    name = "fake"

    def __init__(self, hits_by_query):
        self.hits_by_query = hits_by_query
        self.calls = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        value = self.hits_by_query.get(query, [])
        if isinstance(value, Exception):
            raise value
        return value


def test_query_pack_is_bounded_and_uses_exact_company_identities():
    queries = build_sale_channel_queries(enrichment())

    assert len(queries) == 5
    assert all(
        '"MENSWEAR NORGE AS"' in query
        or '"MENSWEAR NORGE AS KONKURSBO"' in query
        or "986425284" in query
        or "938018014" in query
        for query in queries
    )
    assert any('"MENSWEAR NORGE AS KONKURSBO"' in query for query in queries)
    assert any('"938018014"' in query for query in queries)
    assert any("site:auksjonen.no" in query for query in queries)


def test_exact_orgnr_and_sale_wording_create_unverified_sale_candidate():
    hit = SearchHit(
        title="Varelager fra konkursbo selges",
        url="https://www.auksjoner.no/nb-NO/auctions/123",
        description="Org.nr 938 018 014. Bud på samlet kleslager.",
        provider="Brave Search",
    )

    candidate = classify_search_hit(
        hit,
        query="query",
        enrichment=enrichment(),
    )

    assert candidate is not None
    payload = candidate.to_dict()
    assert payload["identity_match_method"] == "EXACT_ORGANISATION_NUMBER"
    assert payload["candidate_state"] == "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
    assert payload["known_sale_channel_domain"] is True
    assert payload["page_verified"] is False
    assert payload["public_sale_found"] is False
    assert payload["inventory_sale_verified"] is False
    assert payload["top5_eligible"] is False


def test_liquidator_wording_creates_channel_candidate_without_sale_claim():
    hit = SearchHit(
        title="MENSWEAR NORGE AS",
        url="https://example-law.no/konkursbo/menswear-norge",
        description="Boet håndteres av bostyrer. Realiseres på vegne av boet.",
        provider="Brave Search",
    )

    candidate = classify_search_hit(
        hit,
        query="query",
        enrichment=enrichment(),
    )

    assert candidate is not None
    payload = candidate.to_dict()
    assert payload["candidate_state"] == "LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
    assert payload["liquidation_signal"] is True
    assert payload["liquidation_channel_verified"] is False


def test_finn_hit_is_retained_for_manual_review_and_never_opened():
    hit = SearchHit(
        title="MENSWEAR NORGE AS konkursbo - varelager",
        url="https://www.finn.no/recommerce/forsale/item/123",
        description="Vareparti klær selges.",
        provider="Brave Search",
    )

    candidate = classify_search_hit(
        hit,
        query="query",
        enrichment=enrichment(),
    )

    assert candidate is not None
    payload = candidate.to_dict()
    assert payload["manual_only_restricted_source"] is True
    assert payload["collection_mode"] == "MANUAL_REVIEW_ONLY"
    assert payload["automatic_page_open"] is False
    assert payload["public_sale_found"] is False


def test_unrelated_company_is_rejected():
    hit = SearchHit(
        title="Other Clothing AS konkursbo",
        url="https://www.auksjonen.no/auksjon/torget/example/123",
        description="Varelager selges på auksjon.",
        provider="Brave Search",
    )

    assert (
        classify_search_hit(hit, query="query", enrichment=enrichment()) is None
    )


def test_search_deduplicates_urls_and_keeps_stronger_candidate_state():
    queries = build_sale_channel_queries(enrichment())
    identity_only = SearchHit(
        title="MENSWEAR NORGE AS",
        url="https://example.no/menswear",
        description="Company information",
        provider="Brave Search",
    )
    sale = SearchHit(
        title="MENSWEAR NORGE AS varelager selges",
        url="https://example.no/menswear",
        description="Konkursbo og budrunde",
        provider="Brave Search",
    )
    provider = FakeProvider(
        {
            queries[0]: [identity_only],
            queries[1]: [sale],
            queries[2]: [],
            queries[3]: [],
            queries[4]: [],
        }
    )

    result = run_sale_channel_search(enrichment(), provider, results_per_query=5)

    assert result.scan_complete is True
    assert result.requests_made == 5
    assert len(provider.calls) == 5
    assert len(result.candidates) == 1
    assert result.candidates[0].candidate_state == "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION"


def test_provider_error_is_recorded_and_fails_closed():
    queries = build_sale_channel_queries(enrichment())
    provider = FakeProvider(
        {
            queries[0]: RuntimeError("provider unavailable"),
            queries[1]: [],
            queries[2]: [],
            queries[3]: [],
            queries[4]: [],
        }
    )

    result = run_sale_channel_search(enrichment(), provider)

    assert result.scan_complete is False
    assert result.requests_made == 4
    assert len(result.errors) == 1
    assert result.to_dict()["public_sale_found"] is False


def test_artifacts_separate_candidates_and_keep_commercial_top5_empty(tmp_path: Path):
    queries = build_sale_channel_queries(enrichment())
    provider = FakeProvider(
        {
            queries[0]: [
                SearchHit(
                    title="MENSWEAR NORGE AS varelager selges",
                    url="https://www.vareauksjonen.no/Listing/Details/1",
                    description="Org.nr 986425284. Vareparti klær.",
                    provider="Brave Search",
                )
            ],
            queries[1]: [],
            queries[2]: [],
            queries[3]: [],
            queries[4]: [],
        }
    )
    result = run_sale_channel_search(enrichment(), provider)

    paths = write_sale_channel_artifacts(result, tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    sale_candidates = json.loads(
        paths["sale_candidates"].read_text(encoding="utf-8")
    )
    commercial = json.loads(
        paths["commercial_top5"].read_text(encoding="utf-8")
    )
    summary = paths["summary"].read_text(encoding="utf-8")

    assert report["sale_listing_candidate_count"] == 1
    assert report["search_snippets_confirm_sale"] is False
    assert len(sale_candidates) == 1
    assert sale_candidates[0]["page_verified"] is False
    assert commercial == []
    assert "Public sale found: false" in summary
    assert "Commercial Top 5 count: 0" in summary


def test_results_per_query_is_bounded():
    provider = FakeProvider({})
    with pytest.raises(ValueError):
        run_sale_channel_search(enrichment(), provider, results_per_query=0)
    with pytest.raises(ValueError):
        run_sale_channel_search(enrichment(), provider, results_per_query=21)
