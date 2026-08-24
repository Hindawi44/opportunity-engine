from __future__ import annotations

from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.search_provider import SearchHit
from scripts.run_nl_fabric_query_family_shadow import run_query_family_shadow


class FakeProvider:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def search(self, query: str, *, count: int = 10):
        self.calls.append((query, count))
        return list(self.responses.get(query, ()))[:count]


def _hit(domain: str, slug: str) -> SearchHit:
    return SearchHit(
        title=f"{domain} {slug}",
        url=f"https://{domain}/{slug}",
        description="fabric supplier",
        provider="exa",
    )


def _page(url: str, *, ok: bool = True, text: str = "") -> PageFetchResult:
    return PageFetchResult(
        requested_url=url,
        final_url=url,
        ok=ok,
        status_code=200 if ok else None,
        title="Stoffen groothandel" if ok else "",
        text=text,
        error=None if ok else "timeout",
    )


def test_shadow_ranks_supplier_yield_and_noise_without_promoting():
    family = (
        ("good", "Nederland restpartijen stoffen groothandel"),
        ("noisy", "Nederland deadstock stoffen B2B groothandel"),
    )
    good_query = family[0][1]
    noisy_query = family[1][1]
    responses = {
        good_query: [
            _hit("a.nl", "fabric-a"),
            _hit("b.nl", "fabric-b"),
            _hit("c.nl", "fabric-c"),
        ],
        noisy_query: [
            _hit("d.nl", "fabric-d"),
            _hit("broken.nl", "timeout"),
            _hit("noise.nl", "clothing"),
        ],
    }
    provider = FakeProvider(responses)

    def fetcher(url: str) -> PageFetchResult:
        if "broken.nl" in url:
            return _page(url, ok=False)
        if "noise.nl" in url:
            return PageFetchResult(
                requested_url=url,
                final_url=url,
                ok=True,
                status_code=200,
                title="Kleding voorraad",
                text="jassen broeken jurken partij kleding groothandel prijs",
                error=None,
            )
        return _page(
            url,
            text="restpartijen stoffen voorraad stofrollen groothandel per meter prijs",
        )

    report = run_query_family_shadow(
        exa_api_key="test-key",
        results_per_query=3,
        query_family=family,
        provider_factory=lambda _key: provider,
        page_fetcher=fetcher,
    )

    assert report["status"] == "SUCCESS"
    assert report["shadow_only"] is True
    assert report["automatic_query_activation"] is False
    assert report["automatic_query_promotion"] is False
    assert report["production_query_mutation"] is False
    assert report["production_mutation"] is False
    assert report["query_count"] == 2
    assert report["nominal_hit_budget"] == 6
    assert provider.calls == [(good_query, 3), (noisy_query, 3)]

    assert report["ranking"][0]["query_id"] == "good"
    assert report["ranking"][0]["accepted_domain_count"] == 3
    noisy = next(row for row in report["query_results"] if row["query_id"] == "noisy")
    assert noisy["accepted_domain_count"] == 1
    assert noisy["fetch_failed_count"] == 1
    assert noisy["semantic_noise_count"] == 1
    assert noisy["rejection_reason_counts"] == {
        "FETCH_FAILED": 1,
        "OUT_OF_PROJECT_DOMAIN": 1,
    }


def test_shadow_deduplicates_domains_in_query_metrics():
    query = "Nederland textielgroothandel voorraad stoffen"
    provider = FakeProvider({
        query: [
            _hit("same.nl", "one"),
            _hit("same.nl", "two"),
            _hit("other.nl", "three"),
        ]
    })

    report = run_query_family_shadow(
        exa_api_key="test-key",
        results_per_query=3,
        query_family=(("stock", query),),
        provider_factory=lambda _key: provider,
        page_fetcher=lambda url: _page(
            url,
            text="stoffen voorraad stofrollen groothandel per meter prijs",
        ),
    )

    row = report["query_results"][0]
    assert row["hit_count"] == 3
    assert row["unique_result_domain_count"] == 2
    assert row["duplicate_domain_count"] == 1
    assert row["accepted_url_count"] == 3
    assert row["accepted_domain_count"] == 2
    assert report["union_accepted_domain_count"] == 2


def test_shadow_rejects_query_that_escapes_market_or_domain():
    provider = FakeProvider({})

    try:
        run_query_family_shadow(
            exa_api_key="test-key",
            query_family=(("bad-market", "Germany stoffen groothandel"),),
            provider_factory=lambda _key: provider,
            page_fetcher=lambda url: _page(url),
        )
    except ValueError as exc:
        assert "NL-anchored" in str(exc)
    else:
        raise AssertionError("expected market validation failure")

    try:
        run_query_family_shadow(
            exa_api_key="test-key",
            query_family=(("bad-domain", "Nederland kleding voorraad groothandel"),),
            provider_factory=lambda _key: provider,
            page_fetcher=lambda url: _page(url),
        )
    except ValueError as exc:
        assert "FABRIC_PROCUREMENT" in str(exc)
    else:
        raise AssertionError("expected domain validation failure")


def test_shadow_requires_bounded_results_per_query():
    provider = FakeProvider({})
    for value in (0, 6):
        try:
            run_query_family_shadow(
                exa_api_key="test-key",
                results_per_query=value,
                provider_factory=lambda _key: provider,
            )
        except ValueError as exc:
            assert "between 1 and 5" in str(exc)
        else:
            raise AssertionError("expected results-per-query validation failure")
