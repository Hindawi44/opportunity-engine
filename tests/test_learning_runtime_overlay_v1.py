from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.adaptive_keyword_learning import KeywordEvaluationResult
from opportunity_engine.discovery.brave_market_signal_continuity import (
    collect_manifest_brave_market_signals,
    learned_radar_overlay,
)
from opportunity_engine.discovery.brave_market_signal_radar import (
    MARKET_QUERIES,
    MarketRadarQuery,
    market_signal_from_brave_hit,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.learned_query_overlay import (
    augment_market_query,
    build_learned_query_overlay,
    learned_terms_for_market,
    save_learned_query_overlay,
)
from opportunity_engine.market_intelligence import MarketSignalType


def evaluation(term: str, status: str, precision: float = 0.5):
    return KeywordEvaluationResult(
        term=term,
        market_code="NO",
        status=status,
        recovered_case_ids=("MISS-1",),
        raw_hit_count=2,
        verified_relevant_count=1,
        precision=precision,
        min_recovered_cases=1,
        min_precision=0.2,
        automatic_activation=False,
    )


def test_overlay_contains_only_proven_terms() -> None:
    overlay = build_learned_query_overlay(
        [
            evaluation("sluttlager", "PROVEN", 0.5),
            evaluation("billig", "REJECTED_NOISY", 0.05),
        ]
    )

    terms = learned_terms_for_market(overlay, "NO")
    assert set(terms) == {"sluttlager"}
    assert terms["sluttlager"] == MarketSignalType.WAREHOUSE_SURPLUS
    assert overlay["automatic_query_activation"] is False
    assert overlay["automatic_financial_action"] is False


def test_overlay_is_bounded_per_market() -> None:
    overlay = build_learned_query_overlay(
        [evaluation(f"restlager-{index}", "PROVEN", 0.9 - index * 0.01) for index in range(8)],
        max_terms_per_market=3,
    )

    assert len(overlay["markets"]["NO"]) == 3


def test_query_augmentation_expands_existing_or_group_without_extra_query() -> None:
    base = MARKET_QUERIES["NO"][0]
    augmented = augment_market_query(base, ["sluttlager", "butikkstenging"])

    assert isinstance(augmented, MarketRadarQuery)
    assert augmented.query_id == base.query_id
    assert '"sluttlager"' in augmented.query
    assert '"butikkstenging"' in augmented.query
    assert augmented.query.count(")") == base.query.count(")")


def test_learned_term_classifies_only_while_overlay_is_active() -> None:
    hit = SearchHit(
        title="Sluttlager med arbeidsklær",
        url="https://example.no/sluttlager",
        description="Hele beholdningen av arbeidsklær selges denne uken.",
        provider="Brave Search",
    )
    original_query = MARKET_QUERIES["NO"][1]

    before = market_signal_from_brave_hit(
        hit,
        market_code="NO",
        query=original_query,
        rank=1,
        observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )
    assert before is None

    overlay = build_learned_query_overlay([evaluation("sluttlager", "PROVEN")])
    with learned_radar_overlay(overlay):
        runtime_query = MARKET_QUERIES["NO"][1]
        assert '"sluttlager"' in runtime_query.query
        signal = market_signal_from_brave_hit(
            hit,
            market_code="NO",
            query=runtime_query,
            rank=1,
            observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        )

    assert signal is not None
    assert signal.signal_type == MarketSignalType.WAREHOUSE_SURPLUS
    assert "sluttlager" in signal.metadata["event_terms"]
    assert MARKET_QUERIES["NO"][1] == original_query


def test_runtime_overlay_adds_zero_search_requests(tmp_path: Path) -> None:
    overlay_path = tmp_path / "learning" / "active-keyword-overlay.json"
    save_learned_query_overlay(
        overlay_path,
        build_learned_query_overlay([evaluation("sluttlager", "PROVEN")]),
    )
    manifest = {
        "sources": [
            {"market_code": "NO", "artifact_dir": "no"},
            {"market_code": "SE", "artifact_dir": "se"},
            {"market_code": "DE", "artifact_dir": "de"},
        ]
    }
    calls: list[tuple[str, str]] = []

    class Provider:
        name = "Fake Brave"

        def __init__(self, market: str):
            self.market = market

        def search(self, query: str, *, count: int = 10):
            calls.append((self.market, query))
            if self.market == "NO" and "sluttlager" in query.casefold():
                return [
                    SearchHit(
                        title="Sluttlager med arbeidsklær",
                        url="https://example.no/sluttlager",
                        description="Hele beholdningen av arbeidsklær selges.",
                        provider="Fake Brave",
                    )
                ]
            return []

    report = collect_manifest_brave_market_signals(
        manifest,
        root=tmp_path,
        observed_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
        environment={
            "GITHUB_EVENT_NAME": "schedule",
            "BRAVE_SEARCH_API_KEY": "test-key",
            "OPPORTUNITY_LEARNED_QUERY_OVERLAY_PATH": str(overlay_path),
        },
        provider_factory=lambda market, api_key, freshness: Provider(market),
        queries_per_market=2,
        results_per_query=10,
    )

    assert report["requests_made"] == 6
    assert len(calls) == 6
    assert report["learned_query_overlay"]["extra_search_requests"] == 0
    assert report["learned_query_overlay"]["query_budget_unchanged"] is True
    assert report["learned_query_overlay"]["active_terms_by_market"] == {
        "NO": ["sluttlager"]
    }
    no_source = next(
        item for item in report["sources"] if item["source_country"] == "NO"
    )
    assert no_source["accepted_signal_count"] == 1
    signal = no_source["signals"][0]
    assert signal["metadata"]["learned_term_match"] is True
    assert signal["metadata"]["learned_terms"] == ["sluttlager"]


def test_no_overlay_keeps_original_query_unchanged() -> None:
    base = MARKET_QUERIES["NO"][0]
    assert augment_market_query(base, []) == base
