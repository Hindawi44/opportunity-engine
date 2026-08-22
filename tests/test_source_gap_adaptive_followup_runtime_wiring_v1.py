from __future__ import annotations

from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.source_gap_adaptive_followup import _DomainBoundProvider


class Provider:
    name = "test"

    def search(self, query: str, *, count: int = 10):
        return [
            SearchHit(
                title="correct",
                url="https://ny.auksjonen.no/auksjon/correct/1",
                description="varelager",
                provider="test",
            ),
            SearchHit(
                title="wrong domain",
                url="https://example.com/auksjon/wrong/2",
                description="varelager",
                provider="test",
            ),
        ]


def test_source_gap_provider_rejects_off_domain_search_results() -> None:
    provider = _DomainBoundProvider(Provider())

    hits = provider.search(
        'site:ny.auksjonen.no "Example AS" (varelager OR auksjon)',
        count=10,
    )

    assert [hit.url for hit in hits] == [
        "https://ny.auksjonen.no/auksjon/correct/1"
    ]


def test_daily_hook_uses_safe_source_gap_wrapper_before_source_verification() -> None:
    hook = Path(
        "src/opportunity_engine/discovery/unified_market_intelligence_river_cli_hook.py"
    ).read_text(encoding="utf-8")

    assert "write_safe_source_gap_adaptive_followup_with_continuity" in hook
    assert "write_source_gap_adaptive_followup_with_continuity" not in hook
    assert hook.index(
        "write_safe_source_gap_adaptive_followup_with_continuity("
    ) < hook.index("write_signal_follow_up_source_verification(")
