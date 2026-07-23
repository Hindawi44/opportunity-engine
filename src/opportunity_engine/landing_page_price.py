"""Guarded landing-page enrichment for explicit NOK prices.

The fetcher follows only public HTTPS pages, limits redirects/body size/time, and accepts a
price only when it is explicitly associated with NOK/kr or exposed as structured product
price metadata on a Norwegian page. It never guesses from bare numbers.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from html import unescape
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

_MAX_BODY_BYTES = 1_000_000
_DEFAULT_TIMEOUT_SECONDS = 6.0
_DEFAULT_MAX_PAGES = 4
_MAX_REDIRECTS = 3

_NOK_TEXT_PRICE = re.compile(
    r"(?ix)(?:"
    r"\b(?:kr|nok)\s*[:\-]?\s*(?P<prefix>\d{1,3}(?:[ .\u00a0]\d{3})+|\d{2,8})(?:[,.]\d{2})?"
    r"|\b(?P<suffix>\d{1,3}(?:[ .\u00a0]\d{3})+|\d{2,8})(?:[,.]\d{2})?\s*(?:kr|nok)\b"
    r")"
)
_META_PRICE = re.compile(
    r"(?is)<meta\b[^>]*(?:property|itemprop|name)\s*=\s*['\"](?:product:price:amount|price|og:price:amount)['\"][^>]*content\s*=\s*['\"](?P<value>[^'\"]+)['\"][^>]*>"
    r"|<meta\b[^>]*content\s*=\s*['\"](?P<value2>[^'\"]+)['\"][^>]*(?:property|itemprop|name)\s*=\s*['\"](?:product:price:amount|price|og:price:amount)['\"][^>]*>"
)
_JSON_LD = re.compile(r"(?is)<script\b[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script>")
_TAGS = re.compile(r"(?is)<script\b.*?</script>|<style\b.*?</style>|<[^>]+>")


def _parse_amount(raw: str) -> float | None:
    value = unescape(str(raw)).strip()
    value = re.sub(r"(?i)\b(?:nok|kr)\b", "", value)
    value = value.replace("\u00a0", " ").strip(" :,-")
    if not value:
        return None
    # Norwegian thousands separators are spaces/dots; comma is normally decimal.
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+(?:,\d{1,2})?", value):
        value = value.replace(" ", "").replace(".", "").replace(",", ".")
    else:
        value = value.replace(" ", "").replace(",", ".")
    try:
        amount = float(value)
    except ValueError:
        return None
    if 10 <= amount <= 100_000_000:
        return amount
    return None


def extract_nok_price_from_html(html: str) -> tuple[float | None, str | None]:
    """Return the first conservative explicit NOK price found in HTML."""
    for match in _META_PRICE.finditer(html):
        raw = match.group("value") or match.group("value2") or ""
        amount = _parse_amount(raw)
        if amount is not None:
            # Structured price metadata is accepted only when page text signals NOK/kr.
            nearby = html[max(0, match.start() - 1000): match.end() + 1000]
            if re.search(r"(?i)\b(?:nok|kr)\b", nearby):
                return amount, "structured_meta"

    for block in _JSON_LD.findall(html):
        try:
            payload = json.loads(unescape(block).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                currency = str(node.get("priceCurrency") or node.get("currency") or "").upper()
                raw_price = node.get("price") or node.get("lowPrice")
                if currency == "NOK" and raw_price is not None:
                    amount = _parse_amount(str(raw_price))
                    if amount is not None:
                        return amount, "json_ld"
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)

    visible = unescape(_TAGS.sub(" ", html))
    visible = re.sub(r"\s+", " ", visible)
    for match in _NOK_TEXT_PRICE.finditer(visible):
        raw = match.group("prefix") or match.group("suffix") or ""
        amount = _parse_amount(raw)
        if amount is not None:
            return amount, "visible_text"
    return None, None


def _is_public_https_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not address.is_global:
            return False
    return bool(infos)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.redirects = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        self.redirects += 1
        target = urljoin(req.full_url, newurl)
        if self.redirects > _MAX_REDIRECTS or not _is_public_https_url(target):
            raise HTTPError(target, code, "unsafe or excessive redirect", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, target)


def fetch_landing_page_price(url: str, *, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS) -> tuple[float | None, str | None, str | None]:
    """Fetch one public HTTPS page and return ``(price, source, error)``."""
    if not _is_public_https_url(url):
        return None, None, "unsafe_or_non_https_url"
    request = Request(
        url,
        headers={
            "User-Agent": "OpportunityEngine/2.7 (+price-evidence; contact repository owner)",
            "Accept": "text/html,application/xhtml+xml;q=0.9",
        },
        method="GET",
    )
    opener = build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            if not _is_public_https_url(final_url):
                return None, None, "unsafe_final_url"
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return None, None, "unsupported_content_type"
            raw = response.read(_MAX_BODY_BYTES + 1)
            if len(raw) > _MAX_BODY_BYTES:
                return None, None, "body_too_large"
            charset = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
    except HTTPError as exc:
        return None, None, f"http_{exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return None, None, f"fetch_error:{type(exc).__name__}"

    price, source = extract_nok_price_from_html(html)
    if price is None:
        return None, None, "price_not_found"
    return price, source, None


def enrich_results_with_landing_page_prices(
    rows: Iterable[dict[str, Any]],
    *,
    max_pages: int | None = None,
) -> tuple[dict[str, Any], ...]:
    """Enrich a limited number of result rows that lack ``price_nok``."""
    limit = max_pages if max_pages is not None else int(os.getenv("LANDING_PRICE_MAX_PAGES_PER_SEARCH", str(_DEFAULT_MAX_PAGES)))
    limit = max(0, min(limit, 10))
    fetched = 0
    enriched: list[dict[str, Any]] = []
    for original in rows:
        item = original
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("price_nok"), (int, float)):
            enriched.append(item)
            continue
        if fetched >= limit:
            enriched.append(item)
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            enriched.append(item)
            continue
        fetched += 1
        price, source, error = fetch_landing_page_price(url)
        item["landing_page_fetch_attempted"] = True
        item["landing_page_price_error"] = error
        if price is not None:
            item["price_nok"] = price
            item["price_currency"] = "NOK"
            item["price_extraction_source"] = f"landing_page:{source}"
        enriched.append(item)
    return tuple(enriched)
