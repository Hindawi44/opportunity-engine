"""Bounded Chromium fallback for specific public Auksjonen item pages.

The normal verifier remains the primary path. Chromium is used only when one
specific Auksjonen item page returns insufficient public listing content through
the lightweight HTTP verifier. The fallback never logs in, bypasses access
controls, contacts a seller, places a bid, or performs a commercial action.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable
from urllib.parse import urlparse, urlunparse

from opportunity_engine.discovery.clothing_inventory_search import (
    PageVerification,
    normalize_public_url,
    verify_public_html,
)
from opportunity_engine.discovery.source_channel_guard import (
    enforce_source_channel_identity,
)

MAX_RENDERED_PAGES = 3
MIN_DELAY_SECONDS = 2.0
_AUKSJONEN_ITEM_PATH = re.compile(r"^/auksjon(?:/[^/]+)+/\d+/?$", re.I)
_APPROVED_AUKSJONEN_HOSTS = frozenset({"auksjonen.no", "ny.auksjonen.no"})
_FALLBACK_ERRORS = frozenset({"insufficient public listing content"})

PrimaryVerifier = Callable[[str], PageVerification]
RenderedPageLoader = Callable[[str], tuple[str, str]]


def canonicalize_auksjonen_item_url(url: str) -> str | None:
    """Return a canonical approved item URL for either public frontend host."""
    canonical = normalize_public_url(url)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    if (
        parsed.hostname not in _APPROVED_AUKSJONEN_HOSTS
        or _AUKSJONEN_ITEM_PATH.fullmatch(parsed.path or "") is None
    ):
        return None
    return urlunparse(parsed._replace(netloc="auksjonen.no"))


@dataclass(frozen=True, slots=True)
class AuksjonenPlaywrightFallbackConfig:
    """Safety and volume limits for one manually initiated Discovery run."""

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


def is_specific_auksjonen_item_url(url: str) -> bool:
    """Return True only for a stable public item URL on an approved host."""
    return canonicalize_auksjonen_item_url(url) is not None


class AuksjonenPlaywrightFallbackVerifier:
    """Use one shared Chromium page after the normal verifier fails closed."""

    def __init__(
        self,
        primary_verifier: PrimaryVerifier,
        *,
        config: AuksjonenPlaywrightFallbackConfig | None = None,
        rendered_page_loader: RenderedPageLoader | None = None,
    ) -> None:
        self.primary_verifier = primary_verifier
        self.config = config or AuksjonenPlaywrightFallbackConfig()
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
        return (
            is_specific_auksjonen_item_url(url)
            and result.verified is not True
            and str(result.error or "").strip().casefold() in _FALLBACK_ERRORS
        )

    def _ensure_browser(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "Playwright is not installed; run "
                "`python -m pip install -r requirements-playwright.txt` and "
                "`python -m playwright install chromium`"
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.config.headless
        )
        self._context = self._browser.new_context(
            user_agent="OpportunityEngine/Auksjonen-Verification-Fallback-1.0"
        )
        self._page = self._context.new_page()
        self._page.set_default_navigation_timeout(
            self.config.navigation_timeout_seconds * 1000
        )

    def _load_rendered_page(self, url: str) -> tuple[str, str]:
        if self._injected_loader is not None:
            return self._injected_loader(url)
        self._ensure_browser()
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_timeout(self.config.delay_seconds * 1000)
        return self._page.url, self._page.content()

    def __call__(self, url: str) -> PageVerification:
        primary_result = self.primary_verifier(url)
        if not self._should_fallback(url, primary_result):
            return primary_result
        if len(self._attempted_urls) >= self.config.max_pages:
            self._budget_exhausted += 1
            return primary_result

        canonical = canonicalize_auksjonen_item_url(url) or url
        self._attempted_urls.append(canonical)
        try:
            final_url, rendered_html = self._load_rendered_page(canonical)
            canonical_final_url = canonicalize_auksjonen_item_url(final_url)
            if canonical_final_url is None:
                raise RuntimeError(
                    "rendered page redirected outside one specific Auksjonen item"
                )
            rendered_result = enforce_source_channel_identity(
                verify_public_html(canonical_final_url, rendered_html)
            )
            if rendered_result.verified is True:
                self._successful_urls.append(canonical)
            else:
                self._failed_urls.append(canonical)
                self._errors.append({
                    "url": canonical,
                    "error": rendered_result.error or "rendered page remained unresolved",
                })
            return rendered_result
        except Exception as exc:
            self._failed_urls.append(canonical)
            self._errors.append({"url": canonical, "error": str(exc)})
            original_error = primary_result.error or "primary verification failed"
            return replace(
                primary_result,
                error=f"{original_error}; Playwright fallback failed: {exc}",
            )

    def diagnostics(self) -> dict[str, object]:
        """Return bounded browser diagnostics for the operator report."""
        return {
            "enabled": True,
            "scope": "specific_auksjonen_item_pages_only",
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
        """Close optional browser resources without masking the Discovery result."""
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
