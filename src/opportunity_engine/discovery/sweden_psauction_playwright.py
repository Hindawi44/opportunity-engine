"""Bounded browser and indexed-search verification for public PS Auction item pages.

The lightweight verifier remains primary. A rendered browser is used only when
one exact PS Auction item page returns HTTP 403 or insufficient public content.
If the rendered page still cannot prove the listing state, a bounded exact-item
public search corroboration is attempted using the configured Brave API key.

Indexed corroboration is deliberately conservative: it can confirm ENDED from
explicit ended/sold evidence or an auction end timestamp already in the past,
and it can confirm ACTIVE only when the exact item has clothing/bulk evidence
and an explicit auction end timestamp in the future. Search-index absence or
ambiguous snippets remain unresolved.

The fallback never logs in, bypasses access controls, contacts a seller, places
a bid, or performs any commercial action.
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    PageVerification,
    UNKNOWN,
    verify_public_html,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_clothing_inventory import (
    enrich_sweden_page_verification,
)
from opportunity_engine.discovery.sweden_psauction import (
    canonicalize_psauction_item_url,
    psauction_gate_decision,
)

MAX_RENDERED_PAGES = 6
MIN_DELAY_SECONDS = 2.0
_INDEXED_RESULTS_PER_QUERY = 5
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
_SYSTEM_CHROMIUM_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
_PSAUCTION_ENDED_REASON = "specific PS Auction item is ended or sold"
_STOCKHOLM_TZ = ZoneInfo("Europe/Stockholm")
_STRONG_INDEXED_ENDED_PATTERNS = (
    re.compile(r"\bauktionen\s+(?:är\s+)?avslutad\b", re.I),
    re.compile(r"(?:^|\|\s*|·\s*)avslutad(?:\s*·|\s*\||$)", re.I),
    re.compile(r"(?:^|\|\s*|·\s*)såld(?:\s*·|\s*\||$)", re.I),
)
_AUCTION_END_PATTERN = re.compile(
    r"(?:auktionen\s+(?:avslutas|slutar)|slutar)\s*[:,-]?\s*"
    r"(?:[A-Za-zÅÄÖåäö]+,?\s*)?"
    r"(?P<date>20\d{2}-\d{2}-\d{2})"
    r"(?:[ T](?P<time>\d{1,2}:\d{2}))?",
    re.I,
)
_INVENTORY_TYPE_TERMS = (
    "arbetskläder",
    "damkläder",
    "herrkläder",
    "sportkläder",
    "secondhand kläder",
    "kläder",
    "skor",
    "textil",
    "bälten",
    "accessoarer",
)

PrimaryVerifier = Callable[[str], PageVerification]
RenderedPageLoader = Callable[[str], tuple[str, str]]
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class PSAuctionPlaywrightConfig:
    """Safety and volume limits for one bounded PS Auction source run."""

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


def _clean_indexed_text(value: str) -> str:
    return " ".join(
        html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split()
    )


def _indexed_status(text: str, now: datetime) -> tuple[str, str | None]:
    """Resolve ACTIVE/ENDED only from explicit strong indexed evidence."""
    cleaned = _clean_indexed_text(text)
    if any(pattern.search(cleaned) for pattern in _STRONG_INDEXED_ENDED_PATTERNS):
        return ENDED, "explicit indexed ended/sold marker"

    local_now = now.astimezone(_STOCKHOLM_TZ)
    future_deadlines: list[datetime] = []
    past_deadlines: list[datetime] = []
    same_day_without_time = False

    for match in _AUCTION_END_PATTERN.finditer(cleaned):
        end_date = date.fromisoformat(match.group("date"))
        time_text = match.group("time")
        if time_text:
            hour, minute = (int(part) for part in time_text.split(":"))
            deadline = datetime(
                end_date.year,
                end_date.month,
                end_date.day,
                hour,
                minute,
                tzinfo=_STOCKHOLM_TZ,
            )
            if deadline > local_now:
                future_deadlines.append(deadline)
            else:
                past_deadlines.append(deadline)
        elif end_date > local_now.date():
            future_deadlines.append(
                datetime(
                    end_date.year,
                    end_date.month,
                    end_date.day,
                    23,
                    59,
                    tzinfo=_STOCKHOLM_TZ,
                )
            )
        elif end_date < local_now.date():
            past_deadlines.append(
                datetime(
                    end_date.year,
                    end_date.month,
                    end_date.day,
                    0,
                    0,
                    tzinfo=_STOCKHOLM_TZ,
                )
            )
        else:
            same_day_without_time = True

    if future_deadlines and not past_deadlines:
        return ACTIVE, min(future_deadlines).isoformat()
    if past_deadlines and not future_deadlines:
        return ENDED, max(past_deadlines).isoformat()
    if same_day_without_time or future_deadlines or past_deadlines:
        return UNKNOWN, "conflicting or incomplete indexed auction deadline"
    return UNKNOWN, None


class PSAuctionPlaywrightFallbackVerifier:
    """Render one exact PS Auction item, then corroborate by exact indexed search."""

    def __init__(
        self,
        primary_verifier: PrimaryVerifier,
        *,
        config: PSAuctionPlaywrightConfig | None = None,
        rendered_page_loader: RenderedPageLoader | None = None,
        indexed_search_provider: SearchProvider | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.primary_verifier = primary_verifier
        self.config = config or PSAuctionPlaywrightConfig()
        self._injected_loader = rendered_page_loader
        self._injected_indexed_search_provider = indexed_search_provider
        self._indexed_search_provider: SearchProvider | None = None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._attempted_urls: list[str] = []
        self._successful_urls: list[str] = []
        self._failed_urls: list[str] = []
        self._errors: list[dict[str, str]] = []
        self._budget_exhausted = 0
        self._playwright_render_count = 0
        self._system_chromium_render_count = 0
        self._system_chromium_executable: str | None = None
        self._indexed_attempted_urls: list[str] = []
        self._indexed_active_urls: list[str] = []
        self._indexed_ended_urls: list[str] = []
        self._indexed_unresolved_urls: list[str] = []
        self._indexed_errors: list[dict[str, str]] = []
        self._indexed_budget_exhausted = 0
        self._indexed_cache: dict[str, PageVerification] = {}

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
            raise RuntimeError("Playwright is not installed") from exc

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(
                headless=self.config.headless
            )
        except Exception:
            self._browser = self._playwright.chromium.launch(
                channel="chrome",
                headless=self.config.headless,
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

    def _find_system_chromium(self) -> str | None:
        for candidate in _SYSTEM_CHROMIUM_CANDIDATES:
            executable = shutil.which(candidate)
            if executable:
                return executable
        return None

    def _load_with_system_chromium(self, url: str) -> tuple[str, str]:
        executable = self._find_system_chromium()
        if not executable:
            raise RuntimeError("no system Chrome/Chromium executable found")
        self._system_chromium_executable = executable
        virtual_time_ms = max(2000, int(self.config.delay_seconds * 1000))
        command = [
            executable,
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--lang=sv-SE",
            f"--virtual-time-budget={virtual_time_ms}",
            "--dump-dom",
            url,
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.config.navigation_timeout_seconds + 10.0,
            check=False,
        )
        if completed.returncode != 0:
            detail = " ".join((completed.stderr or "").split())[:500]
            raise RuntimeError(
                f"system Chromium exited {completed.returncode}"
                + (f": {detail}" if detail else "")
            )
        rendered_html = completed.stdout or ""
        if len(rendered_html.strip()) < 80:
            raise RuntimeError("system Chromium returned insufficient DOM content")
        self._system_chromium_render_count += 1
        return url, rendered_html

    def _load_rendered_page(self, url: str) -> tuple[str, str]:
        if self._injected_loader is not None:
            return self._injected_loader(url)

        playwright_error: Exception | None = None
        try:
            self._ensure_browser()
            response = self._page.goto(url, wait_until="domcontentloaded")
            self._page.wait_for_timeout(self.config.delay_seconds * 1000)
            if self._dismiss_cookie_consent():
                self._page.wait_for_timeout(self.config.delay_seconds * 1000)
            status = response.status if response is not None else None
            if status is not None and status >= 400:
                raise RuntimeError(f"rendered page returned HTTP {status}")
            self._playwright_render_count += 1
            return self._page.url, self._page.content()
        except Exception as exc:
            playwright_error = exc

        try:
            return self._load_with_system_chromium(url)
        except Exception as chromium_exc:
            raise RuntimeError(
                f"Playwright renderer failed: {playwright_error}; "
                f"system Chromium renderer failed: {chromium_exc}"
            ) from chromium_exc

    def _get_indexed_search_provider(self) -> SearchProvider | None:
        if self._injected_indexed_search_provider is not None:
            return self._injected_indexed_search_provider
        if self._indexed_search_provider is not None:
            return self._indexed_search_provider
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
        if not api_key:
            return None
        self._indexed_search_provider = BraveSearchProvider(
            api_key,
            country="SE",
            freshness="pm",
            extra_snippets=True,
            operators=True,
            max_retries=1,
        )
        return self._indexed_search_provider

    @staticmethod
    def _same_item_hits(item_id: str, hits: list[SearchHit]) -> list[SearchHit]:
        exact: list[SearchHit] = []
        for hit in hits:
            pair = canonicalize_psauction_item_url(hit.url)
            if pair is not None and pair[1] == item_id:
                exact.append(hit)
        return exact

    @staticmethod
    def _scope_is_proven(hits: list[SearchHit]) -> bool:
        for hit in hits:
            decision = psauction_gate_decision(hit)
            if decision.accepted or decision.reason == _PSAUCTION_ENDED_REASON:
                return True
        return False

    @staticmethod
    def _scenario_from_index_text(text: str) -> str:
        normalized = _clean_indexed_text(text).casefold()
        if re.search(r"\bkonkursbo\b|\bi konkurs\b", normalized):
            return "COMPANY_BANKRUPTCY"
        return "AUCTION"

    @staticmethod
    def _inventory_type_from_index_text(text: str) -> str | None:
        normalized = _clean_indexed_text(text).casefold()
        return next((term for term in _INVENTORY_TYPE_TERMS if term in normalized), None)

    def _corroborate_with_indexed_search(
        self,
        url: str,
        unresolved: PageVerification,
    ) -> PageVerification:
        pair = canonicalize_psauction_item_url(url)
        if pair is None:
            return unresolved
        canonical, item_id = pair
        cached = self._indexed_cache.get(canonical)
        if cached is not None:
            return cached
        if len(self._indexed_attempted_urls) >= self.config.max_pages:
            self._indexed_budget_exhausted += 1
            return unresolved

        provider = self._get_indexed_search_provider()
        if provider is None:
            return unresolved

        self._indexed_attempted_urls.append(canonical)
        query = f'site:psauction.se/item/view "{item_id}"'
        try:
            raw_hits = list(provider.search(query, count=_INDEXED_RESULTS_PER_QUERY))
        except Exception as exc:
            self._indexed_errors.append({"url": canonical, "error": str(exc)})
            result = replace(
                unresolved,
                error=(
                    f"{unresolved.error or 'source-page verification unresolved'}; "
                    f"indexed corroboration failed: {exc}"
                ),
            )
            self._indexed_cache[canonical] = result
            return result

        exact_hits = self._same_item_hits(item_id, raw_hits)
        if not exact_hits or not self._scope_is_proven(exact_hits):
            self._indexed_unresolved_urls.append(canonical)
            result = replace(
                unresolved,
                error=(
                    f"{unresolved.error or 'source-page verification unresolved'}; "
                    "indexed corroboration lacked exact clothing/bulk evidence"
                ),
            )
            self._indexed_cache[canonical] = result
            return result

        best = max(exact_hits, key=lambda hit: len(hit.description))
        evidence = " | ".join(
            _clean_indexed_text(f"{hit.title} | {hit.description}")
            for hit in exact_hits
        )[:6000]
        status, status_detail = _indexed_status(evidence, self._clock())
        if status == UNKNOWN:
            self._indexed_unresolved_urls.append(canonical)
            result = replace(
                unresolved,
                title=unresolved.title or best.title,
                text=evidence[:2000] or unresolved.text,
                bounded_context=evidence[:4000] or unresolved.bounded_context,
                page_role=ITEM_LISTING,
                opportunity_identity=f"url-id:{item_id}",
                identity_stable=True,
                clothing_inventory_evidence=True,
                error=(
                    f"{unresolved.error or 'source-page verification unresolved'}; "
                    "indexed corroboration did not prove a current or ended auction state"
                ),
            )
            self._indexed_cache[canonical] = result
            return result

        result = PageVerification(
            url=canonical,
            title=best.title,
            text=evidence[:2000] or None,
            inventory_type=self._inventory_type_from_index_text(evidence),
            listing_status=status,
            page_role=ITEM_LISTING,
            opportunity_identity=f"url-id:{item_id}",
            identity_stable=True,
            clothing_inventory_evidence=True,
            sale_evidence=status == ACTIVE,
            event_scenario=self._scenario_from_index_text(evidence),
            bounded_context=evidence[:4000] or None,
            verified=True,
            error=None,
        )
        self._indexed_cache[canonical] = result
        if status == ACTIVE:
            self._indexed_active_urls.append(canonical)
        else:
            self._indexed_ended_urls.append(canonical)
        if status_detail:
            self._indexed_errors.append(
                {
                    "url": canonical,
                    "status_evidence": status_detail,
                }
            )
        return result

    def __call__(self, url: str) -> PageVerification:
        primary_result = self.primary_verifier(url)
        if not self._should_fallback(url, primary_result):
            return primary_result
        if len(self._attempted_urls) >= self.config.max_pages:
            self._budget_exhausted += 1
            return self._corroborate_with_indexed_search(url, primary_result)

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
                return rendered_result

            self._failed_urls.append(canonical)
            self._errors.append(
                {
                    "url": canonical,
                    "error": rendered_result.error
                    or "rendered page remained unresolved",
                }
            )
            return self._corroborate_with_indexed_search(
                canonical,
                rendered_result,
            )
        except Exception as exc:
            self._failed_urls.append(canonical)
            self._errors.append({"url": canonical, "error": str(exc)})
            original_error = primary_result.error or "primary verification failed"
            browser_failed = replace(
                primary_result,
                error=f"{original_error}; Chromium fallback failed: {exc}",
            )
            return self._corroborate_with_indexed_search(
                canonical,
                browser_failed,
            )

    def diagnostics(self) -> dict[str, object]:
        indexed_enabled = bool(
            self._injected_indexed_search_provider is not None
            or os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
        )
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
            "playwright_render_count": self._playwright_render_count,
            "system_chromium_render_count": self._system_chromium_render_count,
            "system_chromium_executable": self._system_chromium_executable,
            "indexed_corroboration_enabled": indexed_enabled,
            "indexed_query_budget": self.config.max_pages,
            "indexed_attempted": len(self._indexed_attempted_urls),
            "indexed_attempted_urls": list(self._indexed_attempted_urls),
            "indexed_resolved_active": len(self._indexed_active_urls),
            "indexed_active_urls": list(self._indexed_active_urls),
            "indexed_resolved_ended": len(self._indexed_ended_urls),
            "indexed_ended_urls": list(self._indexed_ended_urls),
            "indexed_unresolved": len(self._indexed_unresolved_urls),
            "indexed_unresolved_urls": list(self._indexed_unresolved_urls),
            "indexed_budget_exhausted": self._indexed_budget_exhausted,
            "indexed_evidence": list(self._indexed_errors),
            "overall_resolved": (
                len(self._successful_urls)
                + len(self._indexed_active_urls)
                + len(self._indexed_ended_urls)
            ),
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
