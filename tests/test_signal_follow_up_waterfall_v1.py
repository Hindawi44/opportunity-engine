from __future__ import annotations

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.signal_follow_up_continuity import _run_memory_plan


def _plan(*, linked_ids=()):
    return [
        {
            "case_id": "entity-case-1",
            "country": "NO",
            "query": '"Example AS" (varelager OR lagersalg OR auksjon)',
            "explicit_linked_commercial_case_ids": list(linked_ids),
            "_source_case": {
                "case_id": "entity-case-1",
                "_follow_up_market": "NO",
                "_follow_up_target": "Example AS",
                "source_urls": ["https://example.no/original"],
            },
        }
    ]


class FakeProvider:
    name = "Fake Brave"

    def __init__(self, hits=None, error: Exception | None = None):
        self.hits = list(hits or [])
        self.error = error
        self.calls = 0

    def search(self, query: str, *, count: int = 10):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.hits[:count]


def _good_hit():
    return SearchHit(
        title="Example AS lagersalg av varelager",
        url="https://example.no/konkurssalg",
        description="Example AS selger varelager og vareparti etter avvikling.",
        provider="Fake Brave",
    )


def test_linked_commercial_case_satisfies_waterfall_without_brave_request() -> None:
    provider = FakeProvider([_good_hit()])

    report = _run_memory_plan(
        _plan(linked_ids=("commercial-case-42",)),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key: provider,
        results_per_case=5,
    )

    assert provider.calls == 0
    assert report["search_request_count"] == 0
    row = report["cases"][0]
    assert row["search_status"] == "SATISFIED_LINKED_EVIDENCE"
    assert row["follow_up_state"] == "EXPLICIT_COMMERCIAL_CASE_LINK_EXISTS"
    assert row["waterfall"]["stopped_after"] == "linked-commercial-case-memory"
    assert [step["source"] for step in row["waterfall"]["attempts"]] == [
        "linked-commercial-case-memory"
    ]


def test_brave_is_used_only_when_linked_evidence_is_insufficient() -> None:
    provider = FakeProvider([_good_hit()])

    report = _run_memory_plan(
        _plan(),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key: provider,
        results_per_case=5,
    )

    assert provider.calls == 1
    assert report["search_request_count"] == 1
    assert report["commercial_lead_count"] == 1
    row = report["cases"][0]
    assert row["search_status"] == "SUCCESS"
    assert row["waterfall"]["stopped_after"] == "brave-web-search"
    assert [step["source"] for step in row["waterfall"]["attempts"]] == [
        "linked-commercial-case-memory",
        "brave-web-search",
    ]
    assert row["leads"][0]["source_url"] == "https://example.no/konkurssalg"


def test_no_api_key_exhausts_zero_cost_memory_step_without_search() -> None:
    provider = FakeProvider([_good_hit()])

    report = _run_memory_plan(
        _plan(),
        environment={},
        provider_factory=lambda market, api_key: provider,
        results_per_case=5,
    )

    assert provider.calls == 0
    assert report["search_request_count"] == 0
    row = report["cases"][0]
    assert row["search_status"] == "SKIPPED_NO_API_KEY"
    assert row["waterfall"]["status"] == "EXHAUSTED"
    assert row["waterfall"]["total_cost_units"] == 0


def test_brave_provider_failure_is_isolated_in_waterfall_diagnostics() -> None:
    provider = FakeProvider(error=RuntimeError("provider down"))

    report = _run_memory_plan(
        _plan(),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key: provider,
        results_per_case=5,
    )

    assert provider.calls == 1
    assert report["search_request_count"] == 1
    assert report["search_error_count"] == 1
    row = report["cases"][0]
    assert row["search_status"] == "FAILED"
    assert row["waterfall"]["attempts"][-1]["status"] == "ERROR"
    assert "provider down" in row["waterfall"]["attempts"][-1]["error"]


def test_waterfall_keeps_financial_actions_disabled() -> None:
    report = _run_memory_plan(
        _plan(linked_ids=("commercial-case-42",)),
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, api_key: FakeProvider(),
        results_per_case=5,
    )

    row = report["cases"][0]
    assert row["promotion_to_opportunity_allowed"] is False
    assert row["automatic_contact"] is False
    assert row["automatic_bid"] is False
    assert row["automatic_purchase"] is False
    assert row["automatic_payment"] is False
