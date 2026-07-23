from types import SimpleNamespace

from opportunity_engine.external_execution_audit import TracingSearchProvider, diagnose_candidate


class FakeProvider:
    def __init__(self):
        self.request_count = 0
        self.cache_hits = 0

    def search(self, query, **kwargs):
        self.request_count += 1
        return [
            {"title": "Used machine", "url": "https://example.test/item", "snippet": "No explicit price"},
            {"title": "Priced machine", "url": "https://example.test/price", "price_nok": 1200},
        ]


def test_tracing_provider_records_live_result_shape():
    tracing = TracingSearchProvider(FakeProvider())
    rows = tracing.search("machine")

    assert len(rows) == 2
    trace = tracing.traces[0]
    assert trace.request_count_before == 0
    assert trace.request_count_after == 1
    assert trace.response_count == 2
    assert trace.https_result_count == 2
    assert trace.explicit_price_result_count == 1
    assert trace.error is None


def test_diagnosis_explains_results_without_accepted_evidence():
    tracing = TracingSearchProvider(FakeProvider())
    tracing.search("machine")
    result = SimpleNamespace(
        comparables_found=0,
        buyers_found=0,
        evidence_created=0,
        errors=(),
    )

    diagnosis = diagnose_candidate(result=result, traces=tuple(tracing.traces))

    assert "brave_search_called" in diagnosis
    assert "brave_results_returned" in diagnosis
    assert "no_market_comparables_accepted" in diagnosis
    assert "no_buyer_candidates_accepted" in diagnosis
    assert "no_external_evidence_created" in diagnosis
