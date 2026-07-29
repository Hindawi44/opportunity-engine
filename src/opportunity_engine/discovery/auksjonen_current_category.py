"""Bounded current-listing discovery from Auksjonen's public clothing category.

Brave remains the primary search provider. This adapter supplements one approved
Auksjonen query with links rendered from one public category page. It never logs
in, bypasses access controls, contacts a seller, places a bid, or performs a
commercial action. Every collected item still passes through the existing page
verification, source-channel guard, and post-verification Hard Gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from opportunity_engine.discovery.auksjonen_playwright_fallback import (
    is_specific_auksjonen_item_url,
)
from opportunity_engine.discovery.clothing_inventory_search import (
    DiscoveryQuery,
    normalize_public_url,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.source_targeted_retrieval import (
    source_gate_decision,
)

DEFAULT_AUKSJONEN_CLOTHING_CATEGORY_URL = (
    "https://auksjonen.no/auksjoner/overskudd_klaer"
)
MAX_CURRENT_LISTINGS = 10
MIN_DELAY_SECONDS = 2.0

CategoryPageLoader = Callable[[str], tuple[str, Sequence[Mapping[str, Any]]]]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def is_approved_auksjonen_clothing_category_url(url: str) -> bool:
    """Allow only the one public Auksjonen clothing/workwear category page."""
    canonical = normalize_public_url(url)
    if not canonical:
        return False
    parsed = urlparse(canonical)
    return (
        parsed.hostname == "auksjonen.no"
        and parsed.path.rstrip("/").casefold() == "/auksjoner/overskudd_klaer"
        and not parsed.query
        and not parsed.fragment
    )


@dataclass(frozen=True, slots=True)
class AuksjonenCurrentCategoryConfig:
    """Safety and volume limits for one manually initiated category read."""

    category_url: str = DEFAULT_AUKSJONEN_CLOTHING_CATEGORY_URL
    max_listings: int = MAX_CURRENT_LISTINGS
    delay_seconds: float = 2.5
    navigation_timeout_seconds: float = 30.0
    headless: bool = True

    def __post_init__(self) -> None:
        if not is_approved_auksjonen_clothing_category_url(self.category_url):
            raise ValueError("category_url must be the approved Auksjonen clothing category")
        if not 1 <= self.max_listings <= MAX_CURRENT_LISTINGS:
            raise ValueError(
                f"max_listings must be between 1 and {MAX_CURRENT_LISTINGS}"
            )
        if self.delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(
                f"delay_seconds must be at least {MIN_DELAY_SECONDS:g}"
            )
        if self.navigation_timeout_seconds <= 0:
            raise ValueError("navigation_timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class AuksjonenCurrentCategoryCollection:
    """One bounded set of specific public item links from the category page."""

    captured_at: str
    category_url: str
    final_url: str | None
    hits: tuple[SearchHit, ...]
    pages_visited: int
    rows_seen: int
    errors: tuple[dict[str, str], ...] = ()

    def diagnostics(self) -> dict[str, object]:
        return {
            "enabled": True,
            "scope": "one_approved_auksjonen_clothing_category",
            "category_url": self.category_url,
            "final_url": self.final_url,
            "captured_at": self.captured_at,
            "pages_visited": self.pages_visited,
            "rows_seen": self.rows_seen,
            "specific_item_hits": len(self.hits),
            "item_urls": [hit.url for hit in self.hits],
            "errors": list(self.errors),
            "used": self.pages_visited > 0,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def normalize_category_cards(
    rows: Sequence[Mapping[str, Any]],
    *,
    query: DiscoveryQuery,
) -> tuple[SearchHit, ...]:
    """Normalize, gate, and deduplicate rendered category cards."""
    accepted: dict[str, SearchHit] = {}
    for row in rows:
        title = _compact(row.get("title"))
        context = _compact(row.get("description"))
        canonical = normalize_public_url(str(row.get("url") or ""))
        if not title or not canonical or not is_specific_auksjonen_item_url(canonical):
            continue

        # The approved page itself is explicitly the Klær/Arbeidsklær category.
        # Add that source context without inventing any item-specific attributes.
        description = _compact(
            f"Klær/Arbeidsklær. Auksjon. {context or title}"
        )[:4000]
        hit = SearchHit(
            title=title,
            url=canonical,
            description=description,
            provider="Auksjonen Current Category",
        )
        decision = source_gate_decision(hit, query)
        if not decision.accepted:
            continue
        accepted.setdefault(
            decision.canonical_url,
            SearchHit(
                title=title,
                url=decision.canonical_url,
                description=description,
                provider="Auksjonen Current Category",
            ),
        )
    return tuple(accepted.values())


class AuksjonenCurrentCategoryCollector:
    """Read one approved public category page in a bounded Chromium session."""

    def __init__(
        self,
        config: AuksjonenCurrentCategoryConfig | None = None,
        *,
        category_page_loader: CategoryPageLoader | None = None,
    ) -> None:
        self.config = config or AuksjonenCurrentCategoryConfig()
        self._injected_loader = category_page_loader

    def _load_with_playwright(
        self,
        url: str,
    ) -> tuple[str, Sequence[Mapping[str, Any]]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "Playwright is not installed; run "
                "`python -m pip install -r requirements-playwright.txt` and "
                "`python -m playwright install chromium`"
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            context = browser.new_context(
                user_agent="OpportunityEngine/Auksjonen-Current-Category-1.0"
            )
            page = context.new_page()
            page.set_default_navigation_timeout(
                self.config.navigation_timeout_seconds * 1000
            )
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(self.config.delay_seconds * 1000)
                rows = page.locator('a[href*="/auksjon/"]').evaluate_all(
                    """anchors => anchors.map(anchor => {
                      const card = anchor.closest(
                        'article, li, [data-testid*="result"], [data-testid*="auction"], [class*="card"]'
                      ) || anchor.parentElement;
                      const heading = anchor.querySelector('h1,h2,h3,h4')
                        || card?.querySelector('h1,h2,h3,h4');
                      return {
                        url: anchor.href,
                        title: (heading?.innerText || anchor.getAttribute('aria-label')
                          || anchor.innerText || '').trim(),
                        description: (card?.innerText || anchor.innerText || '').trim(),
                      };
                    })"""
                )
                return page.url, rows
            finally:
                context.close()
                browser.close()

    def collect(self, *, query: DiscoveryQuery) -> AuksjonenCurrentCategoryCollection:
        captured_at = datetime.now(timezone.utc).isoformat()
        errors: list[dict[str, str]] = []
        final_url: str | None = None
        rows: Sequence[Mapping[str, Any]] = ()
        pages_visited = 0
        try:
            loader = self._injected_loader or self._load_with_playwright
            final_url, rows = loader(self.config.category_url)
            pages_visited = 1
            if not is_approved_auksjonen_clothing_category_url(final_url):
                raise RuntimeError(
                    "category page redirected outside the approved Auksjonen clothing category"
                )
            hits = normalize_category_cards(rows, query=query)[: self.config.max_listings]
        except Exception as exc:
            errors.append({
                "url": self.config.category_url,
                "final_url": final_url or "",
                "error": str(exc),
            })
            hits = ()

        return AuksjonenCurrentCategoryCollection(
            captured_at=captured_at,
            category_url=self.config.category_url,
            final_url=final_url,
            hits=tuple(hits),
            pages_visited=pages_visited,
            rows_seen=len(rows),
            errors=tuple(errors),
        )


class AuksjonenCurrentCategoryAugmentedProvider:
    """Prioritize current category hits for the approved Auksjonen query only."""

    def __init__(
        self,
        provider: SearchProvider,
        *,
        target_query: str,
        current_hits: Sequence[SearchHit],
    ) -> None:
        if not target_query.strip():
            raise ValueError("target_query must not be empty")
        self._provider = provider
        self._target_query = target_query
        self._current_hits = tuple(current_hits)
        self.name = f"{getattr(provider, 'name', provider.__class__.__name__)} + Auksjonen Current Category"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        base_hits = tuple(self._provider.search(query, count=count))
        if query != self._target_query:
            return base_hits

        merged: dict[str, SearchHit] = {}
        # Direct source links are current-source candidates, so evaluate them before
        # stale search-index results while preserving the same total result budget.
        for hit in (*self._current_hits, *base_hits):
            canonical = normalize_public_url(hit.url)
            if not canonical:
                continue
            merged.setdefault(canonical, hit)
            if len(merged) >= count:
                break
        return tuple(merged.values())
