from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery.market_comparables_benchmark import (
    FEED_FAMILY,
    MAX_COMPARABLES_PER_TARGET,
    MAX_TARGETS,
    OUTPUT_FILENAME,
    RESULTS_PER_QUERY,
    build_comparable_queries,
    build_market_comparables_benchmark,
    comparable_from_hit,
    select_benchmark_targets,
    write_market_comparables_benchmark,
)
from opportunity_engine.discovery.search_provider import SearchHit

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/opportunity_engine/discovery/__init__.py"
HOOK_FILE = ROOT / "src/opportunity_engine/discovery/market_comparables_benchmark_cli_hook.py"


def _item(
    item_id: str = "opportunity:1",
    title: str = "10 stk GSA multinorm workwear",
    *,
    source_url: str = "https://auction.example/lots/1",
    score: float = 82,
) -> dict:
    return {
        "intelligence_id": item_id,
        "record_kind": "CANONICAL_OPPORTUNITY",
        "title": title,
        "source_name": "Auction House",
        "source_country": "NO",
        "source_url": source_url,
        "score": score,
        "details": {
            "quantity": 10,
            "quantity_unit": "items",
            "price": 100,
            "currency": "NOK",
            "brands": ["GSA"],
        },
    }


def _river() -> tuple[dict, dict, dict]:
    item = _item()
    secondary = _item(
        "stock:2",
        "Brand B Grade A jackets",
        source_url="https://stock.example/products/b",
        score=70,
    )
    secondary["record_kind"] = "B2B_STOCK_OFFER"
    secondary["details"].update({"quantity": 20, "price": 4000, "brands": ["Brand B"]})
    brief = {
        "actionable_now": [
            {
                "case_id": "case:1",
                "headline": item["title"],
                "actionability_score": 95,
                "priority_class": "ACTIVE_DIRECT_OPPORTUNITY",
            },
            {
                "case_id": "case:2",
                "headline": "Stock seller — B2B inventory",
                "actionability_score": 82,
                "priority_class": "B2B_OFFER_REQUIRES_VERIFICATION",
            },
        ]
    }
    cases = {
        "cases": [
            {"case_id": "case:1", "item_ids": [item["intelligence_id"]]},
            {"case_id": "case:2", "item_ids": [secondary["intelligence_id"]]},
        ]
    }
    items = {"items": [item, secondary]}
    return brief, cases, items


def _wholesale_hits() -> list[SearchHit]:
    return [
        SearchHit(
            title=f"GSA multinorm workwear wholesale lot {index}",
            url=f"https://wholesale-{index}.example/gsa-workwear",
            description=f"10 stk GSA multinorm workwear {2400 + index * 100} NOK wholesale",
            provider="Fake Brave",
        )
        for index in range(1, 6)
    ]


def _retail_hits() -> list[SearchHit]:
    return [
        SearchHit(
            title=f"GSA multinorm workwear jacket {index}",
            url=f"https://retail-{index}.example/gsa-workwear",
            description=f"GSA workwear jacket {850 + index * 25} NOK",
            provider="Fake Brave",
        )
        for index in range(1, 6)
    ]


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        self.calls.append((query, count))
        return _wholesale_hits() if any(term in query.casefold() for term in ("engros", "wholesale", "grossist")) else _retail_hits()


def test_selects_specific_items_from_top_actionable_cases() -> None:
    brief, cases, items = _river()
    targets = select_benchmark_targets(brief, cases, items)
    assert len(targets) == 2
    assert targets[0]["intelligence_id"] == "opportunity:1"
    assert targets[0]["title"] == "10 stk GSA multinorm workwear"
    assert targets[1]["intelligence_id"] == "stock:2"
    assert MAX_TARGETS == 3


def test_queries_keep_wholesale_and_retail_separate() -> None:
    target = select_benchmark_targets(*_river())[0]
    queries = build_comparable_queries(target)
    assert [query["lane"] for query in queries] == ["WHOLESALE", "RETAIL"]
    assert all("GSA" in query["query"] for query in queries)
    assert all("-site:auction.example" in query["query"] for query in queries)


def test_benchmark_is_bounded_and_finds_offer_below_market() -> None:
    brief, cases, items = _river()
    providers: list[FakeProvider] = []

    def factory(country: str, api_key: str, freshness: str | None) -> FakeProvider:
        assert country == "NO"
        assert api_key == "secret"
        assert freshness == "pm"
        provider = FakeProvider()
        providers.append(provider)
        return provider

    report = build_market_comparables_benchmark(
        brief=brief,
        cases_report=cases,
        items_report=items,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=factory,
        generated_at=NOW,
        max_targets=1,
        results_per_query=RESULTS_PER_QUERY,
    )
    assert report["feed_family"] == FEED_FAMILY
    assert report["status"] == "SUCCESS"
    assert report["requests_made"] == 2
    assert report["hits_received"] == 10
    assert report["accepted_comparable_count"] <= MAX_COMPARABLES_PER_TARGET
    assert len(providers) == 1
    assert len(providers[0].calls) == 2
    benchmark = report["target_benchmarks"][0]
    assert benchmark["target_price"]["amount"] == 10
    assert benchmark["target_price"]["basis"] == "PER_ITEM"
    assert benchmark["wholesale_range"]["count"] == 5
    assert benchmark["retail_range"]["count"] == 5
    assert benchmark["benchmark_classification"] == "CLEARLY_BELOW_MARKET"
    assert benchmark["recommended_next_action"] == "CHECK_SHIPPING_FEES_CONDITION_AND_FINAL_PRICE"
    assert report["shipping_included"] is False
    assert report["automatic_purchase"] is False


def test_unit_mismatch_is_not_used_as_a_comparable() -> None:
    target = select_benchmark_targets(*_river())[0]
    hit = SearchHit(
        title="GSA multinorm workwear wholesale",
        url="https://wholesale.example/by-weight",
        description="GSA workwear 25 EUR per kg",
        provider="Fake Brave",
    )
    comparable, reason = comparable_from_hit(
        target=target,
        hit=hit,
        lane="WHOLESALE",
        fx_rates_to_nok={"NOK": 1.0, "EUR": 12.0},
    )
    assert comparable is None
    assert reason == "COMPARISON_UNIT_MISMATCH"


def test_foreign_currency_is_not_silently_converted() -> None:
    target = select_benchmark_targets(*_river())[0]
    hit = SearchHit(
        title="GSA multinorm workwear jacket",
        url="https://retail.example/gsa",
        description="GSA workwear jacket 90 EUR",
        provider="Fake Brave",
    )
    comparable, reason = comparable_from_hit(
        target=target,
        hit=hit,
        lane="RETAIL",
        fx_rates_to_nok={"NOK": 1.0},
    )
    assert reason is None
    assert comparable is not None
    assert comparable["unit_price_nok"] is None
    assert comparable["fx_conversion_status"] == "FX_RATE_MISSING"


def test_missing_key_is_explicit_and_makes_no_request() -> None:
    brief, cases, items = _river()

    def forbidden_factory(*args, **kwargs):
        raise AssertionError("provider must not be initialized")

    report = build_market_comparables_benchmark(
        brief=brief,
        cases_report=cases,
        items_report=items,
        environment={},
        provider_factory=forbidden_factory,
        generated_at=NOW,
    )
    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["requests_made"] == 0
    assert report["block_reason"] == "BRAVE_SEARCH_API_KEY_MISSING"


def test_writer_creates_output_and_attaches_summary(tmp_path: Path) -> None:
    brief, cases, items = _river()
    (tmp_path / "unified-daily-decision-brief.json").write_text(json.dumps(brief), encoding="utf-8")
    (tmp_path / "unified-market-cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (tmp_path / "unified-intelligence-items.json").write_text(json.dumps(items), encoding="utf-8")
    (tmp_path / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"unified_market_intelligence_river": {"status": "SUCCESS"}}), encoding="utf-8"
    )
    (tmp_path / "domain-market-intelligence-brief.txt").write_text("BASE\n", encoding="utf-8")

    report = write_market_comparables_benchmark(
        tmp_path,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda *_: FakeProvider(),
    )
    assert report["status"] == "SUCCESS"
    assert (tmp_path / OUTPUT_FILENAME).exists()
    updated = json.loads((tmp_path / "unified-daily-decision-brief.json").read_text(encoding="utf-8"))
    assert updated["market_comparables_benchmark"]["shipping_included"] is False
    domain = json.loads((tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8"))
    assert domain["unified_market_intelligence_river"]["market_comparables_benchmark"]["output_file"] == OUTPUT_FILENAME
    rendered = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert "MARKET COMPARABLES BENCHMARK" in rendered


def test_hook_runs_after_river_by_reverse_atexit_order() -> None:
    init_text = INIT_FILE.read_text(encoding="utf-8")
    hook_text = HOOK_FILE.read_text(encoding="utf-8")
    assert init_text.index("install_market_comparables_benchmark_cli_hook()") < init_text.index(
        "install_unified_market_intelligence_river_cli_hook()"
    )
    assert "atexit.register" in hook_text
    assert "write_market_comparables_benchmark(output_dir)" in hook_text
