from __future__ import annotations

from opportunity_engine.discovery.adaptive_waterfall import (
    AdaptiveWaterfallPolicy,
    AdaptiveWaterfallStep,
    run_adaptive_search_waterfall,
)
from opportunity_engine.discovery.search_provider import SearchHit


class FakeProvider:
    def __init__(self, name: str, hits=None, error: Exception | None = None):
        self.name = name
        self.hits = list(hits or [])
        self.error = error
        self.calls = 0

    def search(self, query: str, *, count: int = 10):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.hits[:count]


def hit(url: str, title: str = "Opportunity", description: str = "liquidation stock"):
    return SearchHit(title=title, url=url, description=description, provider="fake")


def test_waterfall_stops_when_primary_source_is_sufficient() -> None:
    primary = FakeProvider("primary", [hit("https://example.com/a")])
    fallback = FakeProvider("fallback", [hit("https://example.com/b")])

    result = run_adaptive_search_waterfall(
        "liquidation stock",
        [
            AdaptiveWaterfallStep("primary", primary, cost_units=0),
            AdaptiveWaterfallStep("fallback", fallback, cost_units=2),
        ],
        policy=AdaptiveWaterfallPolicy(min_accepted_hits=1, max_total_cost_units=10),
    )

    assert result.status == "SATISFIED"
    assert [item.url for item in result.hits] == ["https://example.com/a"]
    assert primary.calls == 1
    assert fallback.calls == 0
    assert result.stopped_after == "primary"


def test_waterfall_falls_through_when_primary_has_no_accepted_hits() -> None:
    primary = FakeProvider("primary", [hit("https://example.com/noise", title="Recipe")])
    fallback = FakeProvider("fallback", [hit("https://example.com/good", title="Warehouse liquidation")])

    result = run_adaptive_search_waterfall(
        "warehouse liquidation",
        [
            AdaptiveWaterfallStep("primary", primary, cost_units=0),
            AdaptiveWaterfallStep("fallback", fallback, cost_units=2),
        ],
        accept_hit=lambda item: "liquidation" in item.title.lower(),
        policy=AdaptiveWaterfallPolicy(min_accepted_hits=1, max_total_cost_units=10),
    )

    assert result.status == "SATISFIED"
    assert [item.url for item in result.hits] == ["https://example.com/good"]
    assert primary.calls == 1
    assert fallback.calls == 1
    assert [attempt.status for attempt in result.attempts] == ["INSUFFICIENT", "SATISFIED"]


def test_waterfall_deduplicates_urls_across_sources() -> None:
    primary = FakeProvider("primary", [hit("https://example.com/same")])
    fallback = FakeProvider(
        "fallback",
        [hit("https://example.com/same"), hit("https://example.com/new")],
    )

    result = run_adaptive_search_waterfall(
        "stock",
        [
            AdaptiveWaterfallStep("primary", primary, cost_units=0),
            AdaptiveWaterfallStep("fallback", fallback, cost_units=1),
        ],
        policy=AdaptiveWaterfallPolicy(min_accepted_hits=2, max_total_cost_units=10),
    )

    assert [item.url for item in result.hits] == [
        "https://example.com/same",
        "https://example.com/new",
    ]
    assert result.attempts[1].duplicate_count == 1


def test_waterfall_continues_after_provider_error() -> None:
    broken = FakeProvider("broken", error=RuntimeError("boom"))
    fallback = FakeProvider("fallback", [hit("https://example.com/recovered")])

    result = run_adaptive_search_waterfall(
        "stock",
        [
            AdaptiveWaterfallStep("broken", broken, cost_units=0),
            AdaptiveWaterfallStep("fallback", fallback, cost_units=1),
        ],
        policy=AdaptiveWaterfallPolicy(min_accepted_hits=1, max_total_cost_units=10),
    )

    assert result.status == "SATISFIED"
    assert result.attempts[0].status == "ERROR"
    assert result.attempts[0].error == "RuntimeError: boom"
    assert fallback.calls == 1


def test_waterfall_skips_step_that_exceeds_cost_budget() -> None:
    free = FakeProvider("free", [])
    expensive = FakeProvider("expensive", [hit("https://example.com/expensive")])
    cheap = FakeProvider("cheap", [hit("https://example.com/cheap")])

    result = run_adaptive_search_waterfall(
        "stock",
        [
            AdaptiveWaterfallStep("free", free, cost_units=0),
            AdaptiveWaterfallStep("expensive", expensive, cost_units=5),
            AdaptiveWaterfallStep("cheap", cheap, cost_units=1),
        ],
        policy=AdaptiveWaterfallPolicy(min_accepted_hits=1, max_total_cost_units=1),
    )

    assert expensive.calls == 0
    assert cheap.calls == 1
    assert result.total_cost_units == 1
    assert [attempt.status for attempt in result.attempts] == [
        "INSUFFICIENT",
        "SKIPPED_COST_GUARD",
        "SATISFIED",
    ]


def test_waterfall_exhausted_when_no_source_can_satisfy() -> None:
    first = FakeProvider("first", [])
    second = FakeProvider("second", [])

    result = run_adaptive_search_waterfall(
        "stock",
        [
            AdaptiveWaterfallStep("first", first),
            AdaptiveWaterfallStep("second", second),
        ],
        policy=AdaptiveWaterfallPolicy(min_accepted_hits=1),
    )

    assert result.status == "EXHAUSTED"
    assert result.hits == ()
    assert result.stopped_after is None
