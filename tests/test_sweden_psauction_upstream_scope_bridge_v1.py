from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    UNRESOLVED_SOURCE,
    PageVerification,
)
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_psauction_playwright import (
    PSAuctionPlaywrightConfig,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_sweden_clothing_inventory_discovery_search.py"
ITEM = "https://psauction.se/item/view/1560018/parti-med-klader"
OTHER_ITEM = "https://psauction.se/item/view/1560019/annat-parti"
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("sweden_discovery_runner_bridge_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeIndexedSearch:
    name = "fake-indexed-search"

    def __init__(self, hits):
        self.hits = list(hits)
        self.queries = []

    def search(self, query: str, *, count: int = 10):
        self.queries.append((query, count))
        return self.hits[:count]


def _unresolved(url: str) -> PageVerification:
    return PageVerification(
        url=url,
        page_role=UNRESOLVED_SOURCE,
        verified=False,
        error="insufficient public listing content",
    )


def _shell(url: str):
    return url, "<html><body>Enable JavaScript</body></html>"


def test_upstream_scope_bridge_uses_exact_index_hit_for_status_only():
    module = _load_runner_module()
    search = FakeIndexedSearch(
        [
            SearchHit(
                # Deliberately generic: Run #177 showed the exact status query
                # can omit clothing/bulk wording even though strict discovery
                # already proved that scope for this item ID.
                title="PS Auction objekt 1560018",
                url=ITEM,
                description="Auktionen avslutas Måndag, 2026-08-17 18:00.",
                provider="Brave Search",
            )
        ]
    )
    verifier = module._PSAuctionUpstreamScopeVerifier(
        lambda url: _unresolved(url),
        config=PSAuctionPlaywrightConfig(max_pages=6, delay_seconds=2.0),
        rendered_page_loader=_shell,
        indexed_search_provider=search,
        clock=lambda: NOW,
    )

    result = verifier(ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is True
    assert result.listing_status == ACTIVE
    assert result.identity_stable is True
    assert result.opportunity_identity == "url-id:1560018"
    assert result.clothing_inventory_evidence is True
    assert result.sale_evidence is True
    assert search.queries == [('site:psauction.se/item/view "1560018"', 5)]
    assert diagnostics["indexed_resolved_active"] == 1
    assert diagnostics["upstream_scope_bridge"] == "PSAUCTION_PREFETCH_STRICT_GATE"


def test_upstream_scope_bridge_still_rejects_wrong_item_id():
    module = _load_runner_module()
    search = FakeIndexedSearch(
        [
            SearchHit(
                title="PS Auction objekt 1560019",
                url=OTHER_ITEM,
                description="Auktionen avslutas Måndag, 2026-08-17 18:00.",
                provider="Brave Search",
            )
        ]
    )
    verifier = module._PSAuctionUpstreamScopeVerifier(
        lambda url: _unresolved(url),
        rendered_page_loader=_shell,
        indexed_search_provider=search,
        clock=lambda: NOW,
    )

    result = verifier(ITEM)
    diagnostics = verifier.diagnostics()

    assert result.verified is False
    assert result.listing_status != ACTIVE
    assert diagnostics["indexed_unresolved"] == 1


def test_daily_runner_uses_scope_bridge_only_on_psauction_fallback_path():
    text = RUNNER.read_text(encoding="utf-8")

    assert "class _PSAuctionUpstreamScopeVerifier" in text
    assert "PSAUCTION_PREFETCH_STRICT_GATE" in text
    assert "browser_verifier = _PSAuctionUpstreamScopeVerifier(" in text
    assert 'args.source == "psauction" and args.verify_pages' in text
