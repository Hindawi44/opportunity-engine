"""Bounded live-source probe for the public ny.auksjonen.no application.

This diagnostic opens one public category page, records a capped set of public
JSON/XHR responses without request headers or credentials, extracts candidate
auction objects from those responses, and writes operator-readable evidence.
It never logs in, contacts a seller, bids, buys, reserves, or pays.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

DEFAULT_ENTRY_URL = "https://ny.auksjonen.no/auksjoner/overskudd_klaer"
APPROVED_HOSTS = frozenset({"auksjonen.no", "ny.auksjonen.no"})
APPROVED_PATH = "/auksjoner/overskudd_klaer"
MAX_RESPONSES = 60
MAX_CANDIDATES = 30
MAX_DOM_LINKS = 100
MAX_BODY_CHARS = 250_000
MAX_TOTAL_CAPTURE_CHARS = 1_500_000
MIN_DELAY_SECONDS = 2.0
_SENSITIVE_QUERY_KEYS = frozenset({
    "access_token", "api_key", "apikey", "auth", "authorization", "key",
    "password", "secret", "session", "signature", "sig", "token",
})
_TITLE_KEYS = (
    "title", "name", "heading", "auctionTitle", "auction_title",
    "objectTitle", "object_title", "productName", "product_name",
)
_ID_KEYS = (
    "id", "auctionId", "auction_id", "objectId", "object_id",
    "listingId", "listing_id", "itemId", "item_id",
)
_URL_KEYS = (
    "url", "href", "link", "publicUrl", "public_url", "auctionUrl",
    "auction_url", "canonicalUrl", "canonical_url",
)
_STATUS_KEYS = ("status", "state", "auctionStatus", "auction_status")
_PRICE_KEYS = (
    "price", "currentBid", "current_bid", "highestBid", "highest_bid",
    "amount", "bidAmount", "bid_amount",
)
_LOCATION_KEYS = ("location", "city", "place", "municipality", "address")
_END_KEYS = (
    "endDate", "end_date", "endsAt", "ends_at", "endTime", "end_time",
    "closingTime", "closing_time", "deadline",
)


def _compact(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)[:1000]
        except TypeError:
            return str(value)[:1000]
    return " ".join(str(value).split())[:1000]


def is_approved_entry_url(url: str) -> bool:
    """Allow only the old/new public clothing category route."""
    parsed = urlparse(str(url or "").strip())
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold() in APPROVED_HOSTS
        and parsed.path.rstrip("/").casefold() == APPROVED_PATH
        and not parsed.fragment
    )


def redact_url(url: str) -> str:
    """Remove values of credential-like query parameters from diagnostics."""
    parsed = urlparse(url)
    redacted = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_KEYS:
            redacted.append((key, "<redacted>"))
        else:
            redacted.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(redacted, doseq=True)))


def should_capture_response(
    url: str,
    *,
    content_type: str = "",
    resource_type: str = "",
) -> bool:
    """Select public JSON/API responses while rejecting static assets."""
    lowered_type = content_type.casefold()
    lowered_url = url.casefold()
    lowered_resource = resource_type.casefold()
    if "json" in lowered_type or "graphql" in lowered_type:
        return True
    return (
        lowered_resource in {"fetch", "xhr"}
        and any(marker in lowered_url for marker in ("/api/", "graphql", "/search", "/auction"))
    )


def _first(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", [], {}):
            return mapping[key]
    return None


def _candidate_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any] | None:
    title = _compact(_first(mapping, _TITLE_KEYS))
    item_id = _compact(_first(mapping, _ID_KEYS))
    url = _compact(_first(mapping, _URL_KEYS))
    if not title or not (item_id or url):
        return None
    return {
        "title": title,
        "id": item_id or None,
        "url": redact_url(url) if url else None,
        "status": _compact(_first(mapping, _STATUS_KEYS)) or None,
        "price": _compact(_first(mapping, _PRICE_KEYS)) or None,
        "location": _compact(_first(mapping, _LOCATION_KEYS)) or None,
        "ends_at": _compact(_first(mapping, _END_KEYS)) or None,
        "available_keys": sorted(str(key) for key in mapping.keys())[:80],
    }


def extract_candidate_objects(payload: Any, *, limit: int = MAX_CANDIDATES) -> list[dict[str, Any]]:
    """Recursively find auction-like objects without assuming one API schema."""
    if limit < 1:
        return []
    found: dict[str, dict[str, Any]] = {}
    stack: list[Any] = [payload]
    visited = 0
    while stack and len(found) < limit and visited < 20_000:
        value = stack.pop()
        visited += 1
        if isinstance(value, Mapping):
            candidate = _candidate_from_mapping(value)
            if candidate:
                identity = str(candidate.get("url") or candidate.get("id") or candidate["title"])
                found.setdefault(identity, candidate)
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
    return list(found.values())[:limit]


def json_shape(payload: Any) -> dict[str, Any]:
    """Return a compact schema hint for one decoded response."""
    if isinstance(payload, Mapping):
        return {
            "type": "object",
            "keys": sorted(str(key) for key in payload.keys())[:100],
        }
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {
            "type": "array",
            "length": len(payload),
            "first_item_type": type(first).__name__ if first is not None else None,
            "first_item_keys": (
                sorted(str(key) for key in first.keys())[:100]
                if isinstance(first, Mapping)
                else []
            ),
        }
    return {"type": type(payload).__name__}


@dataclass(frozen=True, slots=True)
class AuksjonenLiveProbeConfig:
    entry_url: str = DEFAULT_ENTRY_URL
    delay_seconds: float = 7.0
    navigation_timeout_seconds: float = 30.0
    max_responses: int = MAX_RESPONSES
    headless: bool = True

    def __post_init__(self) -> None:
        if not is_approved_entry_url(self.entry_url):
            raise ValueError("entry_url must be the approved Auksjonen clothing category")
        if self.delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(f"delay_seconds must be at least {MIN_DELAY_SECONDS:g}")
        if self.navigation_timeout_seconds <= 0:
            raise ValueError("navigation_timeout_seconds must be positive")
        if not 1 <= self.max_responses <= MAX_RESPONSES:
            raise ValueError(f"max_responses must be between 1 and {MAX_RESPONSES}")


@dataclass(frozen=True, slots=True)
class AuksjonenLiveProbeResult:
    captured_at: str
    entry_url: str
    final_url: str | None
    pages_visited: int
    network_responses: tuple[dict[str, Any], ...]
    candidate_objects: tuple[dict[str, Any], ...]
    dom_links: tuple[dict[str, str], ...]
    errors: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "auksjonen-live-source-probe-1.0",
            "captured_at": self.captured_at,
            "entry_url": self.entry_url,
            "final_url": self.final_url,
            "pages_visited": self.pages_visited,
            "network_response_count": len(self.network_responses),
            "candidate_object_count": len(self.candidate_objects),
            "dom_link_count": len(self.dom_links),
            "network_responses": list(self.network_responses),
            "candidate_objects": list(self.candidate_objects),
            "dom_links": list(self.dom_links),
            "errors": list(self.errors),
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
            "paid_search_used": False,
            "openai_api_used": False,
        }


class AuksjonenLiveSourceProbe:
    """Capture one bounded public browser/network session."""

    def __init__(self, config: AuksjonenLiveProbeConfig | None = None) -> None:
        self.config = config or AuksjonenLiveProbeConfig()

    def run(self) -> AuksjonenLiveProbeResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "Playwright is not installed; run `python -m pip install -r "
                "requirements-playwright.txt` and `python -m playwright install chromium`"
            ) from exc

        captured_at = datetime.now(timezone.utc).isoformat()
        records: list[dict[str, Any]] = []
        candidates: dict[str, dict[str, Any]] = {}
        errors: list[dict[str, str]] = []
        final_url: str | None = None
        pages_visited = 0
        total_captured_chars = 0

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            context = browser.new_context(
                user_agent="OpportunityEngine/Auksjonen-Live-Source-Probe-1.0"
            )
            page = context.new_page()
            page.set_default_navigation_timeout(
                self.config.navigation_timeout_seconds * 1000
            )

            def on_response(response: Any) -> None:
                nonlocal total_captured_chars
                if len(records) >= self.config.max_responses:
                    return
                try:
                    content_type = str(response.headers.get("content-type", ""))
                    resource_type = str(response.request.resource_type or "")
                    if not should_capture_response(
                        response.url,
                        content_type=content_type,
                        resource_type=resource_type,
                    ):
                        return
                    raw = response.body()
                    text = raw.decode("utf-8", errors="replace")
                    remaining = max(0, MAX_TOTAL_CAPTURE_CHARS - total_captured_chars)
                    excerpt_limit = min(MAX_BODY_CHARS, remaining)
                    excerpt = text[:excerpt_limit]
                    total_captured_chars += len(excerpt)
                    parsed: Any = None
                    parse_error: str | None = None
                    try:
                        parsed = json.loads(text)
                    except Exception as exc:
                        parse_error = str(exc)
                    extracted = extract_candidate_objects(parsed) if parsed is not None else []
                    for candidate in extracted:
                        identity = str(candidate.get("url") or candidate.get("id") or candidate["title"])
                        candidates.setdefault(identity, candidate)
                    records.append({
                        "url": redact_url(response.url),
                        "status": int(response.status),
                        "method": str(response.request.method),
                        "resource_type": resource_type,
                        "content_type": content_type,
                        "body_sha256": hashlib.sha256(raw).hexdigest(),
                        "body_chars": len(text),
                        "body_excerpt": excerpt,
                        "body_truncated": len(excerpt) < len(text),
                        "json_shape": json_shape(parsed) if parsed is not None else None,
                        "json_parse_error": parse_error,
                        "candidate_count": len(extracted),
                    })
                except Exception as exc:
                    errors.append({
                        "stage": "response_capture",
                        "url": redact_url(getattr(response, "url", "")),
                        "error": str(exc),
                    })

            page.on("response", on_response)
            try:
                page.goto(self.config.entry_url, wait_until="domcontentloaded")
                pages_visited = 1
                page.wait_for_timeout(self.config.delay_seconds * 1000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                final_url = page.url
                rows = page.locator("a[href]").evaluate_all(
                    """anchors => anchors.map(a => ({
                      url: a.href || '',
                      title: (a.innerText || a.getAttribute('aria-label') || '').trim()
                    })).filter(x => x.url && (x.url.includes('auksjon') || x.url.includes('auction')))"""
                )
                dom_links = tuple(
                    {"url": redact_url(_compact(row.get("url"))), "title": _compact(row.get("title"))}
                    for row in rows[:MAX_DOM_LINKS]
                    if _compact(row.get("url"))
                )
            except Exception as exc:
                errors.append({
                    "stage": "page_navigation",
                    "url": self.config.entry_url,
                    "error": str(exc),
                })
                dom_links = ()
                final_url = page.url or final_url
            finally:
                context.close()
                browser.close()

        return AuksjonenLiveProbeResult(
            captured_at=captured_at,
            entry_url=self.config.entry_url,
            final_url=final_url,
            pages_visited=pages_visited,
            network_responses=tuple(records),
            candidate_objects=tuple(candidates.values())[:MAX_CANDIDATES],
            dom_links=tuple(dom_links),
            errors=tuple(errors),
        )


def write_probe_artifacts(
    result: AuksjonenLiveProbeResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write JSON evidence and a short operator summary."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "auksjonen-live-source-probe.json"
    summary_path = target / "operator-summary.txt"
    report = result.to_dict()
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    endpoints = [record["url"] for record in result.network_responses]
    summary = [
        "Auksjonen live-source probe",
        f"Entry URL: {result.entry_url}",
        f"Final URL: {result.final_url or 'NONE'}",
        f"Pages visited: {result.pages_visited}",
        f"Captured JSON/API responses: {len(result.network_responses)}",
        f"Candidate objects found: {len(result.candidate_objects)}",
        f"DOM auction links found: {len(result.dom_links)}",
        f"Errors: {len(result.errors)}",
        "Paid Brave/OpenAI calls: 0",
        "",
        "Captured endpoints:",
        *(f"- {endpoint}" for endpoint in endpoints[:20]),
    ]
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    return {"report": report_path, "summary": summary_path}
