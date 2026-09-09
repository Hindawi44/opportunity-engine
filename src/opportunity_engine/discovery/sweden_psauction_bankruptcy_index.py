"""Bounded native discovery from PS Auction's public bankruptcy index.

The current PS Auction site exposes auction groups at
``/auction/<id>/<slug>`` from one public ``/auctions?bankruptcy=1`` page. This
adapter reads that approved index, renders the same page once when AWS WAF
returns its empty JavaScript challenge response, keeps only exact
clothing-inventory auction pages, and injects them ahead of the existing
bounded Brave fallback. It never logs in, contacts a seller, bids, or performs
a purchase action.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import shutil
import subprocess
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from opportunity_engine.discovery.clothing_inventory_search import (
    normalize_public_url,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_psauction import (
    PSAUCTION_AUCTION_PATH,
    canonicalize_psauction_listing_url,
    psauction_gate_decision,
)

PSAUCTION_BANKRUPTCY_INDEX_POLICY = "PSAUCTION_BANKRUPTCY_INDEX_V1"
PSAUCTION_BANKRUPTCY_INDEX_URL = "https://psauction.se/auctions?bankruptcy=1"
MAX_INDEX_AUCTIONS = 50
MIN_RENDER_DELAY_SECONDS = 4.0
MAX_RENDER_DELAY_SECONDS = 15.0
_SYSTEM_CHROMIUM_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


def _normalized_host(value: str | None) -> str:
    host = (value or "").casefold()
    return host[4:] if host.startswith("www.") else host


def is_approved_psauction_bankruptcy_index_url(url: str) -> bool:
    """Allow only the single public bankruptcy-auction index route."""
    canonical = normalize_public_url(url)
    if not canonical:
        return False
    parsed = urlparse(canonical)
    query = parse_qs(parsed.query, keep_blank_values=True)
    return (
        _normalized_host(parsed.hostname) == "psauction.se"
        and parsed.path.rstrip("/").casefold() == "/auctions"
        and query == {"bankruptcy": ["1"]}
    )


def _compact(value: str) -> str:
    return " ".join((value or "").split())


class _AuctionAnchorParser(HTMLParser):
    """Collect bounded text from exact current PS Auction auction anchors."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._text: list[str] = []
        self._heading_text: list[str] = []
        self._heading_depth = 0
        self.anchors: list[tuple[str, str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.casefold()
        if self._href is not None:
            if normalized_tag in _HEADING_TAGS:
                self._heading_depth += 1
            return
        if normalized_tag != "a":
            return
        href = next(
            (value for key, value in attrs if key.casefold() == "href"),
            None,
        )
        if not href or "/auction/" not in href.casefold():
            return
        self._href = href
        self._text = []
        self._heading_text = []
        self._heading_depth = 0

    def handle_data(self, data: str) -> None:
        if self._href is None:
            return
        self._text.append(data)
        if self._heading_depth:
            self._heading_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._href is None:
            return
        normalized_tag = tag.casefold()
        if normalized_tag in _HEADING_TAGS and self._heading_depth:
            self._heading_depth -= 1
            return
        if normalized_tag != "a":
            return

        text_parts = [_compact(value) for value in self._text if _compact(value)]
        heading = _compact(" ".join(self._heading_text))
        if not heading:
            heading = next(
                (
                    part
                    for part in text_parts
                    if len(part) >= 4 and any(character.isalpha() for character in part)
                ),
                "",
            )
        self.anchors.append((self._href, heading, _compact(" ".join(text_parts))))
        self._href = None
        self._text = []
        self._heading_text = []
        self._heading_depth = 0


@dataclass(frozen=True, slots=True)
class BankruptcyIndexFetch:
    final_url: str
    html: str
    status_code: int = 200
    waf_action: str | None = None
    transport: str = "HTTP"


@dataclass(frozen=True, slots=True)
class PSAuctionBankruptcyIndexConfig:
    index_url: str = PSAUCTION_BANKRUPTCY_INDEX_URL
    max_auctions: int = MAX_INDEX_AUCTIONS
    timeout_seconds: float = 20.0
    render_delay_seconds: float = 8.0
    render_timeout_seconds: float = 45.0

    def __post_init__(self) -> None:
        if not is_approved_psauction_bankruptcy_index_url(self.index_url):
            raise ValueError("index_url must be the approved PS Auction bankruptcy index")
        if not 1 <= self.max_auctions <= MAX_INDEX_AUCTIONS:
            raise ValueError(
                f"max_auctions must be between 1 and {MAX_INDEX_AUCTIONS}"
            )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not MIN_RENDER_DELAY_SECONDS <= self.render_delay_seconds <= MAX_RENDER_DELAY_SECONDS:
            raise ValueError(
                "render_delay_seconds must be between "
                f"{MIN_RENDER_DELAY_SECONDS:g} and {MAX_RENDER_DELAY_SECONDS:g}"
            )
        if self.render_timeout_seconds <= self.render_delay_seconds:
            raise ValueError(
                "render_timeout_seconds must exceed render_delay_seconds"
            )


@dataclass(frozen=True, slots=True)
class PSAuctionBankruptcyIndexCollection:
    captured_at: str
    index_url: str
    final_url: str | None
    hits: tuple[SearchHit, ...]
    index_requests: int
    rows_seen: int
    rejected_hits: int
    rejection_reasons: dict[str, int]
    rejected_samples: tuple[dict[str, str | None], ...]
    http_status: int | None = None
    waf_action: str | None = None
    rendered_requests: int = 0
    rendered_succeeded: bool = False
    selected_transport: str | None = None
    errors: tuple[dict[str, str], ...] = ()

    def diagnostics(self) -> dict[str, object]:
        return {
            "policy": PSAUCTION_BANKRUPTCY_INDEX_POLICY,
            "source": "PS_AUCTION",
            "source_mode": "NATIVE_BANKRUPTCY_INDEX",
            "index_url": self.index_url,
            "final_url": self.final_url,
            "captured_at": self.captured_at,
            "index_requests": self.index_requests,
            "http_status": self.http_status,
            "waf_action": self.waf_action,
            "rendered_requests": self.rendered_requests,
            "rendered_succeeded": self.rendered_succeeded,
            "selected_transport": self.selected_transport,
            "brave_requests": 0,
            "paid_search_used": False,
            "rows_seen": self.rows_seen,
            "accepted_hits": len(self.hits),
            "accepted_urls": [hit.url for hit in self.hits],
            "rejected_hits": self.rejected_hits,
            "rejection_reasons": dict(self.rejection_reasons),
            "rejected_samples": list(self.rejected_samples),
            "errors": list(self.errors),
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


FetchIndex = Callable[[str, float], BankruptcyIndexFetch]
RenderIndex = Callable[[str, float, float], BankruptcyIndexFetch]


def _fetch_index(url: str, timeout: float) -> BankruptcyIndexFetch:
    response = requests.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={"User-Agent": "OpportunityEngine-PSAuction-Index/1.0"},
    )
    return BankruptcyIndexFetch(
        final_url=response.url,
        html=response.text,
        status_code=response.status_code,
        waf_action=response.headers.get("x-amzn-waf-action"),
    )


def _render_index(
    url: str,
    delay_seconds: float,
    timeout_seconds: float,
) -> BankruptcyIndexFetch:
    """Render only the approved public index with a bounded system browser."""
    if not is_approved_psauction_bankruptcy_index_url(url):
        raise ValueError("render URL must be the approved PS Auction bankruptcy index")
    executable = next(
        (
            path
            for candidate in _SYSTEM_CHROMIUM_CANDIDATES
            if (path := shutil.which(candidate)) is not None
        ),
        None,
    )
    if executable is None:
        raise RuntimeError("no system Chrome/Chromium executable found")

    command = [
        executable,
        "--headless=new",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--lang=sv-SE",
        f"--virtual-time-budget={int(delay_seconds * 1000)}",
        "--dump-dom",
        url,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
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
        raise RuntimeError("system Chromium returned insufficient index content")
    return BankruptcyIndexFetch(
        final_url=url,
        html=rendered_html,
        status_code=200,
        transport="SYSTEM_CHROMIUM",
    )


def parse_psauction_bankruptcy_index(
    html_text: str,
    *,
    base_url: str,
) -> tuple[SearchHit, ...]:
    """Return deduplicated exact current-route auction cards from public HTML."""
    parser = _AuctionAnchorParser()
    parser.feed(html_text)

    best_by_url: dict[str, SearchHit] = {}
    for href, heading, anchor_text in parser.anchors:
        absolute = urljoin(base_url, href)
        identity = canonicalize_psauction_listing_url(absolute)
        if identity is None:
            continue
        canonical, _ = identity
        if PSAUCTION_AUCTION_PATH.fullmatch(urlparse(canonical).path or "/") is None:
            continue
        title = heading or anchor_text
        if not title:
            continue
        description = anchor_text[:6000]
        hit = SearchHit(
            title=title,
            url=canonical,
            description=description,
            provider=PSAUCTION_BANKRUPTCY_INDEX_POLICY,
        )
        previous = best_by_url.get(canonical)
        if previous is None or len(hit.description) > len(previous.description):
            best_by_url[canonical] = hit
    return tuple(best_by_url.values())


class PSAuctionBankruptcyIndexCollector:
    """Read and locally filter one approved PS Auction bankruptcy index page."""

    def __init__(
        self,
        config: PSAuctionBankruptcyIndexConfig | None = None,
        *,
        fetch_index: FetchIndex | None = None,
        render_index: RenderIndex | None = None,
    ) -> None:
        self.config = config or PSAuctionBankruptcyIndexConfig()
        self._fetch_index = fetch_index or _fetch_index
        self._render_index = render_index or _render_index

    def collect(self) -> PSAuctionBankruptcyIndexCollection:
        captured_at = datetime.now(timezone.utc).isoformat()
        final_url: str | None = None
        index_requests = 0
        http_status: int | None = None
        waf_action: str | None = None
        rendered_requests = 0
        rendered_succeeded = False
        selected_transport: str | None = None
        rows_seen = 0
        rejected = 0
        reasons: Counter[str] = Counter()
        rejected_samples: list[dict[str, str | None]] = []
        errors: list[dict[str, str]] = []
        accepted: list[SearchHit] = []

        try:
            index_requests += 1
            fallback_reason: str | None = None
            try:
                fetched = self._fetch_index(
                    self.config.index_url,
                    self.config.timeout_seconds,
                )
                http_status = fetched.status_code
                waf_action = fetched.waf_action
                final_url = fetched.final_url
                if str(fetched.waf_action or "").casefold() == "challenge":
                    fallback_reason = "HTTP bankruptcy index returned an AWS WAF challenge"
                elif fetched.status_code != 200:
                    fallback_reason = (
                        "HTTP bankruptcy index returned "
                        f"status {fetched.status_code}"
                    )
                elif len(fetched.html.strip()) < 80:
                    fallback_reason = "HTTP bankruptcy index returned insufficient content"
            except Exception as exc:
                fallback_reason = f"HTTP bankruptcy index fetch failed: {exc}"
                fetched = BankruptcyIndexFetch(
                    final_url=self.config.index_url,
                    html="",
                    status_code=0,
                )

            if fallback_reason is not None:
                rendered_requests += 1
                try:
                    fetched = self._render_index(
                        self.config.index_url,
                        self.config.render_delay_seconds,
                        self.config.render_timeout_seconds,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"{fallback_reason}; rendered index fallback failed: {exc}"
                    ) from exc
                if fetched.status_code != 200 or len(fetched.html.strip()) < 80:
                    raise RuntimeError(
                        f"{fallback_reason}; rendered index fallback returned "
                        "insufficient content"
                    )
                rendered_succeeded = True

            final_url = fetched.final_url
            selected_transport = fetched.transport
            if not is_approved_psauction_bankruptcy_index_url(final_url):
                raise RuntimeError(
                    "bankruptcy index redirected outside the approved PS Auction route"
                )
            raw_hits = parse_psauction_bankruptcy_index(
                fetched.html,
                base_url=final_url,
            )
            rows_seen = len(raw_hits)
            for hit in raw_hits:
                decision = psauction_gate_decision(hit)
                if not decision.accepted:
                    rejected += 1
                    reasons[decision.reason] += 1
                    if len(rejected_samples) < 30:
                        rejected_samples.append(
                            {
                                "title": hit.title,
                                "url": hit.url,
                                "item_id": decision.item_id,
                                "reason": decision.reason,
                            }
                        )
                    continue
                accepted.append(
                    SearchHit(
                        title=hit.title,
                        url=decision.canonical_url,
                        description=hit.description,
                        provider=hit.provider,
                    )
                )
                if len(accepted) >= self.config.max_auctions:
                    break
        except Exception as exc:
            errors.append(
                {
                    "url": self.config.index_url,
                    "final_url": final_url or "",
                    "error": str(exc),
                }
            )

        return PSAuctionBankruptcyIndexCollection(
            captured_at=captured_at,
            index_url=self.config.index_url,
            final_url=final_url,
            hits=tuple(accepted),
            index_requests=index_requests,
            rows_seen=rows_seen,
            rejected_hits=rejected,
            rejection_reasons=dict(sorted(reasons.items())),
            rejected_samples=tuple(rejected_samples),
            http_status=http_status,
            waf_action=waf_action,
            rendered_requests=rendered_requests,
            rendered_succeeded=rendered_succeeded,
            selected_transport=selected_transport,
            errors=tuple(errors),
        )


class PSAuctionBankruptcyIndexAugmentedProvider:
    """Prioritize native index hits across the current-window query lanes."""

    def __init__(
        self,
        provider: SearchProvider,
        *,
        target_queries: Sequence[str],
        current_hits: Sequence[SearchHit],
    ) -> None:
        queries = tuple(dict.fromkeys(query for query in target_queries if query.strip()))
        if not queries:
            raise ValueError("target_queries must not be empty")
        self._provider = provider
        self._target_queries = queries
        self._query_positions = {query: index for index, query in enumerate(queries)}
        self._current_hits = tuple(current_hits)
        self.name = (
            f"{getattr(provider, 'name', provider.__class__.__name__)} + "
            "PS Auction Bankruptcy Index"
        )

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        base_hits = tuple(self._provider.search(query, count=count))
        position = self._query_positions.get(query)
        if position is None:
            return base_hits

        native_hits = self._current_hits[position :: len(self._target_queries)]
        merged: dict[str, SearchHit] = {}
        for hit in (*native_hits, *base_hits):
            canonical = normalize_public_url(hit.url)
            if not canonical:
                continue
            merged.setdefault(canonical, hit)
            if len(merged) >= count:
                break
        return tuple(merged.values())
