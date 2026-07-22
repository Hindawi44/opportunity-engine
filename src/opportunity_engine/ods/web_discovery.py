"""Web discovery normalization, classification, deduplication and priority scoring.

This module consumes search-result payloads supplied by an authorized search provider.
It does not scrape search engines, Facebook, FINN, or other sites directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import urlparse, urlunparse


CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "auction": ("auksjon", "auction"),
    "sale_listing": ("selges", "til salgs", "for sale"),
    "liquidation": ("avvikling", "lagerutsalg", "opphørssalg", "liquidation"),
    "bankruptcy": ("konkurs", "konkursbo", "bankruptcy"),
    "shop_equipment": ("butikkinnredning", "butikk inventar", "butikkutstyr", "butikk utstyr"),
    "inventory": ("varelager", "restparti", "overskuddslager", "konkurslager", "lager"),
    "office_furniture": ("kontormøbler", "kontorstol", "skrivebord", "arkivskap"),
    "restaurant_equipment": ("restaurant inventar", "kjøledisk", "kaffemaskin", "kassesystem"),
    "salon_equipment": ("frisør inventar", "frisørutstyr"),
    "estate_sale": ("dødsbo",),
}

TARGET_TERMS = tuple(sorted({term for terms in CATEGORY_TERMS.values() for term in terms}))
EXCLUDED_TERMS = (
    "bil til salgs",
    "bruktbil",
    "motorcycle",
    "motorsykkel",
    "båt til salgs",
    "bolig til salgs",
    "leilighet til salgs",
    "mobiltelefon",
    "iphone",
)


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str | None = None
    city: str | None = None
    published_at: str | None = None
    image_count: int | None = None
    price_nok: float | None = None


@dataclass(frozen=True)
class DiscoveryLead:
    lead_id: str
    title: str
    url: str
    canonical_url: str
    source: str
    snippet: str
    city: str | None
    published_at: str | None
    categories: tuple[str, ...]
    priority_score: int
    score_reasons: tuple[str, ...]
    image_count: int | None
    price_nok: float | None
    discovered_at: str


def build_discovery_leads(results: tuple[WebSearchResult, ...]) -> tuple[DiscoveryLead, ...]:
    """Normalize, filter, deduplicate and score externally supplied web results."""

    best_by_url: dict[str, DiscoveryLead] = {}
    for result in results:
        title = _clean(result.title)
        url = result.url.strip()
        if not title or not _is_http_url(url):
            continue
        text = _clean(f"{title} {result.snippet}").casefold()
        if any(term in text for term in EXCLUDED_TERMS):
            continue
        categories = _classify(text)
        if not categories:
            continue
        canonical = canonicalize_url(url)
        score, reasons = _priority_score(result, categories)
        source = _source_name(result.source, canonical)
        lead_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
        lead = DiscoveryLead(
            lead_id=f"web-{lead_id}",
            title=title,
            url=url,
            canonical_url=canonical,
            source=source,
            snippet=_clean(result.snippet),
            city=_clean_optional(result.city),
            published_at=_normalize_datetime(result.published_at),
            categories=categories,
            priority_score=score,
            score_reasons=reasons,
            image_count=result.image_count if result.image_count is None or result.image_count >= 0 else None,
            price_nok=result.price_nok if result.price_nok is None or result.price_nok >= 0 else None,
            discovered_at=datetime.now(timezone.utc).isoformat(),
        )
        existing = best_by_url.get(canonical)
        if existing is None or lead.priority_score > existing.priority_score:
            best_by_url[canonical] = lead

    leads = sorted(
        best_by_url.values(),
        key=lambda item: (-item.priority_score, item.source.casefold(), item.title.casefold()),
    )
    return tuple(leads)


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.casefold()
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    return urlunparse((parsed.scheme.casefold(), host, path, "", "", ""))


def _classify(text: str) -> tuple[str, ...]:
    matched = [category for category, terms in CATEGORY_TERMS.items() if any(term in text for term in terms)]
    return tuple(sorted(matched))


def _priority_score(result: WebSearchResult, categories: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
    score = 0
    reasons: list[str] = []
    category_points = {
        "shop_equipment": 22,
        "inventory": 22,
        "restaurant_equipment": 18,
        "office_furniture": 16,
        "salon_equipment": 16,
        "liquidation": 16,
        "auction": 12,
        "sale_listing": 10,
        "bankruptcy": 8,
        "estate_sale": 4,
    }
    for category in categories:
        points = category_points.get(category, 0)
        score += points
        if points:
            reasons.append(f"category:{category}+{points}")
    if _clean_optional(result.city):
        score += 6
        reasons.append("city_present+6")
    if result.price_nok is not None and result.price_nok >= 0:
        score += 8
        reasons.append("price_present+8")
    if result.image_count is not None and result.image_count > 0:
        score += min(8, result.image_count)
        reasons.append(f"images_present+{min(8, result.image_count)}")
    if _normalize_datetime(result.published_at):
        score += 6
        reasons.append("published_at_present+6")
    return min(score, 100), tuple(reasons)


def _source_name(explicit: str | None, url: str) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    host = urlparse(url).netloc.casefold()
    if "finn.no" in host:
        return "FINN.no"
    if "facebook.com" in host:
        return "Facebook"
    if "auksjonen.no" in host:
        return "Auksjonen.no"
    return host.removeprefix("www.") or "Web"


def _normalize_datetime(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_optional(value: str | None) -> str | None:
    cleaned = _clean(value or "")
    return cleaned or None


def _is_http_url(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://")
