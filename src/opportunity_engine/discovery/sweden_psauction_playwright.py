"""Bounded Chromium fallback for specific public PS Auction item pages.

The lightweight verifier remains primary. Chromium is used only when one exact
PS Auction item page returns HTTP 403 or insufficient public content. The
fallback never logs in, bypasses access controls, contacts a seller, places a
bid, or performs any commercial action.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from opportunity_engine.discovery.clothing_inventory_search import (
    PageVerification,
    verify_public_html,
)
from opportunity_engine.discovery.sweden_clothing_inventory import (
    enrich_sweden_page_verification,
)
from opportunity_engine.discovery.sweden_psauction import (
    canonicalize_psauction_item_url,
)

MAX_RENDERED_PAGES = 3
MIN_DELAY_SECONDS = 2.0
_COOKIE_ACCEPT_LABELS = (
    "Godkänn alla",
    "Acceptera alla",
    "Tillåt alla",
    "Accept all",
)
_FALLBACK_ERROR_PARTS = (
    "403",
    "forbidden",
    "insufficient public listing content",
)

PrimaryVerifier = Callable[[str], PageVerification]
RenderedPageLoader = Callable[[str], tuple[str, str]]


@dataclass(frozen=True, slots=True)
class PSAuctionPlaywrightConfig:
    """Safety and volume limits for one manually initiated source run."""

    max_pages: int = MAX_RENDERED_PAGES
    delay_seconds: float = 2.5
    navigation_timeout_seconds: float = 30.0
    headless: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.max_pages <= MAX_RENDERED_PAGES:
            raise ValueError(
                f"max_pages must be between 1 and {MAX_RENDERED_PAGES}"
            )
        if self.delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(
                f"delay_seconds must be at least {MIN_DELAY_SECONDS:g}"
            )
        if self.navigation_timeout_seconds <= 0:
            raise ValueError("navigation_timeout_seconds must be positive")


class PSAuctionPlaywrightFallbackVerifier:
    """Use one shared Chromium page after the primary verifier fails closed."""

    def __init__(
        self,
        primary_verifier: PrimaryVerifier,
        *,
        config: PSAuctionPlaywrightConfig | None = None,
        rendered_page_loader: RenderedPageLoader | None = None,
    ) -> None:
        self.primary_verifier = primary_verifier
        self.config = config or PSAuctionPlaywrightConfig()
        self._injected_loader = rendered_page_loader
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._attempted_urls: list[str] = []
        self._successful_urls: list[str] = []
        self._failed_urls: list[str] = []
        self._errors: list[dict[str, str]] = []
        self._budget_exhausted = 0

    def _should_fallback(self, url: str, result: PageVerification) -> bool:
        error = str(result.error or "").strip().casefold()
        return (
            canonicalize_psauction_item_url(url) is not None
            and result.verified is not True
            and any(part in error for part in _FALLBACK_ERROR_PARTS)
        )

    def _ensure_browser(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "Playwright is not installed; install requirements-playwright.txt "
                "and Chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.config.headless
        )
        self._context = self._browser.new_context(locale="sv-SE")
        self._page = self._context.new_page()
        self._page.set_default_navigation_timeout(
            self.config.navigation_timeout_seconds * 1000
        )

    def _dismiss_cookie_consent(self) -> bool:
        if self._page is None:
            return False
        for label in _COOKIE_ACCEPT_LABELS:
            button = self._page.get_by_role(
                "button",
                name=re.compile(rf"^\s*{re.escape(label)}\s*$", re.I),
            )
            try:
                if button.count() < 1 or not button.first.is_visible():
                    continue
                button.first.click(timeout=3000)
                self._page.wait_for_timeout(500)
                return True
            except Exception:
                continue
        return False

    def _load_rendered_page(self, url: str) -> tuple[str, str]:
        if self._injected_loader is not None:
            return self._injected_loader(url)
        self._ensure_browser()
        response = self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_timeout(self.config.delay_seconds * 1000)
        if self._dismiss_cookie_consent():
            self._page.wait_for_timeout(self.config.delay_seconds * 1000)
        status = response.status if response is not None else None
        if status is not None and status >= 400:
            raise RuntimeError(f"rendered page returned HTTP {status}")
        return self._page.url, self._page.content()

    def __call__(self, url: str) -> PageVerification:
        primary_result = self.primary_verifier(url)
        if not self._should_fallback(url, primary_result):
            return primary_result
        if len(self._attempted_urls) >= self.config.max_pages:
            self._budget_exhausted += 1
            return primary_result

        canonical_pair = canonicalize_psauction_item_url(url)
        canonical = canonical_pair[0] if canonical_pair else url
        self._attempted_urls.append(canonical)
        try:
            final_url, rendered_html = self._load_rendered_page(canonical)
            final_pair = canonicalize_psauction_item_url(final_url)
            if final_pair is None:
                raise RuntimeError(
                    "rendered page redirected outside one specific PS Auction item"
                )
            rendered_result = enrich_sweden_page_verification(
                verify_public_html(final_pair[0], rendered_html)
            )
            if rendered_result.verified is True:
                self._successful_urls.append(canonical)
            else:
                self._failed_urls.append(canonical)
                self._errors.append(
                    {
                        "url": canonical,
                        "error": rendered_result.error
                        or "rendered page remained unresolved",
                    }
                )
            return rendered_result
        except Exception as exc:
            self._failed_urls.append(canonical)
            self._errors.append({"url": canonical, "error": str(exc)})
            original_error = primary_result.error or "primary verification failed"
            return replace(
                primary_result,
                error=f"{original_error}; Chromium fallback failed: {exc}",
            )

    def diagnostics(self) -> dict[str, object]:
        return {
            "enabled": True,
            "scope": "specific_psauction_item_pages_only",
            "max_pages": self.config.max_pages,
            "delay_seconds": self.config.delay_seconds,
            "navigation_timeout_seconds": self.config.navigation_timeout_seconds,
            "attempted": len(self._attempted_urls),
            "succeeded": len(self._successful_urls),
            "failed": len(self._failed_urls),
            "budget_exhausted": self._budget_exhausted,
            "attempted_urls": list(self._attempted_urls),
            "successful_urls": list(self._successful_urls),
            "failed_urls": list(self._failed_urls),
            "errors": list(self._errors),
            "used": bool(self._attempted_urls),
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }

    def close(self) -> None:
        """Close browser resources without masking the Discovery result."""
        for resource in (self._context, self._browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
