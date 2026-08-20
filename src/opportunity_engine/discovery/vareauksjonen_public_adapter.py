"""Bounded public Vareauksjonen adapter for active clothing inventory lots.

The adapter reads robots.txt, respects the published crawl delay, and scans only
three public pages: all active listings plus the Clothing and Inventory/
Bankruptcy categories. It opens a maximum of ten candidate detail pages and
promotes only active clothing listings with explicit lot/quantity evidence.

It performs no login, contact, bid, purchase, reservation, or payment and uses no
paid search or AI API.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.vareauksjonen.no"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
PUBLIC_PAGE_SPECS = (
    (f"{BASE_URL}/Browse", "ALL_ACTIVE"),
    (f"{BASE_URL}/Browse/C161443/Kl%C3%A6r", "CLOTHING_CATEGORY"),
    (
        f"{BASE_URL}/Browse/C161461/Varelager-og-konkursbo",
        "INVENTORY_BANKRUPTCY_CATEGORY",
    ),
)
MAX_CANDIDATE_DETAILS = 10
MAX_CRAWL_DELAY_SECONDS = 30.0
_ACTION_LABELS = frozenset(
    {
        "kjøp nå",
        "kjop na",
        "send bud",
        "legg inn bud",
        "vis detaljer",
        "vis objekt",
    }
)
_CLOTHING_PATTERN = re.compile(
    r"\b(klær|klaer|klesbutikk|jakke|jakker|bukse|bukser|sko|skotøy|skotoy|"
    r"kjole|kjoler|skjorte|skjorter|genser|gensere|frakk|frakker|dress|dresser|"
    r"vest|vester|tøy|toy|arbeidsklær|arbeidsklaer|arbeidstøy|arbeidstoy|"
    r"tekstil|tekstiler|veske|vesker|belte|belter|overall|kjeledress|uniform|"
    r"undertøy|undertoy|badetøy|badetoy|herreklær|herreklaer|dameklær|dameklaer)\b",
    re.I,
)
_LOT_PATTERN = re.compile(
    r"\b(vareparti|restlager|konkursbo|lagerbeholdning|varelager|parti|bulk|"
    r"pall|paller|kolli|esker|samlet|flere\s+(?:stk|plagg|varer|jakker|kjoler)|"
    r"\d{2,}\s*(?:stk|plagg|varer|jakker|kjoler|bukser|skjorter|gensere|par))\b",
    re.I,
)
_PRICE_PATTERNS = (
    re.compile(r"\bPris\s*[:\-]?\s*([\d][\d\s.,]*)\s*(?:kr|NOK)\b", re.I),
    re.compile(
        r"\b(?:Nåværende\s+bud|Navaerende\s+bud|Høyeste\s+bud|Hoyeste\s+bud)"
        r"\s*[:\-]?\s*([\d][\d\s.,]*)\s*(?:kr|NOK)\b",
        re.I,
    ),
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: object) -> float | None:
    text = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(".", "") if text.count(".") > 1 else text
    try:
        return float(text)
    except ValueError:
        return None


def _request_url(url: str) -> str:
    """Return an ASCII-safe request URL without changing source identity."""
    parsed = urlparse(str(url or "").strip())
    encoded_path = quote(parsed.path, safe="/%:@")
    return parsed._replace(path=encoded_path).geturl()


def is_approved_public_page(url: str) -> bool:
    normalized = str(url or "").strip()
    return normalized in {item[0] for item in PUBLIC_PAGE_SPECS}


def is_approved_listing_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"vareauksjonen.no", "www.vareauksjonen.no"}
        and bool(
            re.fullmatch(
                r"/Listing/Details/\d+(?:/[^?#]*)?",
                parsed.path,
                flags=re.I,
            )
        )
    )


def _listing_id(url: str) -> int:
    match = re.search(r"/Listing/Details/(\d+)(?:/|$)", url, flags=re.I)
    if not match:
        raise ValueError("Vareauksjonen URL lacks a stable listing ID")
    return int(match.group(1))


class _BrowseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        values = {key.casefold(): value or "" for key, value in attrs}
        if values.get("href"):
            self._href = values["href"]
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.anchors.append((self._href, _compact("".join(self._parts))))
            self._href = None
            self._parts = []


@dataclass(frozen=True, slots=True)
class VareauksjonenBrowseCandidate:
    listing_id: int
    title: str
    url: str
    source_pages: tuple[str, ...]
    source_roles: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "title": self.title,
            "url": self.url,
            "source_pages": list(self.source_pages),
            "source_roles": list(self.source_roles),
        }


def parse_browse_candidates(
    html_text: str,
    *,
    page_url: str,
    page_role: str,
) -> tuple[VareauksjonenBrowseCandidate, ...]:
    parser = _BrowseParser()
    parser.feed(html_text)
    grouped: dict[str, list[str]] = {}
    for href, text in parser.anchors:
        absolute = urljoin(BASE_URL, href)
        if not is_approved_listing_url(absolute):
            continue
        grouped.setdefault(absolute, [])
        normalized = text.casefold()
        if text and normalized not in _ACTION_LABELS and text not in grouped[absolute]:
            grouped[absolute].append(text)

    results: list[VareauksjonenBrowseCandidate] = []
    for url, texts in grouped.items():
        title = max(texts, key=len) if texts else ""
        if not title:
            title = url.rstrip("/").split("/")[-1].replace("-", " ")
        if page_role == "ALL_ACTIVE" and not _CLOTHING_PATTERN.search(title):
            continue
        if page_role == "INVENTORY_BANKRUPTCY_CATEGORY" and not (
            _CLOTHING_PATTERN.search(title) or _LOT_PATTERN.search(title)
        ):
            continue
        results.append(
            VareauksjonenBrowseCandidate(
                listing_id=_listing_id(url),
                title=title,
                url=url,
                source_pages=(page_url,),
                source_roles=(page_role,),
            )
        )
    return tuple(results)


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.inputs: list[dict[str, str]] = []
        self.buttons: list[str] = []
        self.headings: list[str] = []
        self.visible_parts: list[str] = []
        self._skip_depth = 0
        self._button_depth = 0
        self._button_parts: list[str] = []
        self._heading_depth = 0
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        if lowered in {"script", "style"}:
            self._skip_depth += 1
            return
        if lowered == "meta":
            key = values.get("name") or values.get("property")
            if key and values.get("content"):
                self.meta[key.casefold()] = values["content"]
        elif lowered == "input":
            self.inputs.append(
                {
                    "name": values.get("name", ""),
                    "id": values.get("id", ""),
                    "type": values.get("type", "text"),
                    "value": values.get("value", ""),
                }
            )
        elif lowered in {"button"}:
            self._button_depth += 1
            self._button_parts = []
        elif lowered in {"h1", "h2", "h3"}:
            self._heading_depth += 1
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.visible_parts.append(data)
        if self._button_depth:
            self._button_parts.append(data)
        if self._heading_depth:
            self._heading_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        elif lowered == "button" and self._button_depth:
            text = _compact("".join(self._button_parts))
            if text:
                self.buttons.append(text)
            self._button_depth -= 1
            self._button_parts = []
        elif lowered in {"h1", "h2", "h3"} and self._heading_depth:
            text = _compact("".join(self._heading_parts))
            if text:
                self.headings.append(text)
            self._heading_depth -= 1
            self._heading_parts = []

    @property
    def visible_text(self) -> str:
        return _compact("\n".join(self.visible_parts))


def _input_value(inputs: Sequence[dict[str, str]], name: str) -> str | None:
    for item in inputs:
        if item.get("name").casefold() == name.casefold():
            value = _compact(item.get("value"))
            return value or None
    return None


def _price(text: str) -> float | None:
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = _number(match.group(1))
            if value is not None:
                return value
    return None


def _location(text: str) -> str | None:
    for match in re.finditer(r"\b([A-ZÆØÅ][A-Za-zÆØÅæøå\- ]{1,60}),\s*NO\b", text):
        value = _compact(match.group(1))
        if value:
            return value
    return None


@dataclass(frozen=True, slots=True)
class VareauksjonenLiveClothingListing:
    listing_id: int
    title: str
    url: str
    listing_status: str
    listing_type: str | None
    price_nok: float | None
    quantity: int | None
    location: str | None
    description: str
    image_url: str | None
    clothing_signal: bool
    inventory_lot_signal: bool
    source_pages: tuple[str, ...]
    source: str = "Vareauksjonen Public Pages"

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "title": self.title,
            "url": self.url,
            "listing_status": self.listing_status,
            "listing_type": self.listing_type,
            "price_nok": self.price_nok,
            "quantity": self.quantity,
            "location": self.location,
            "description": self.description,
            "image_url": self.image_url,
            "clothing_signal": self.clothing_signal,
            "inventory_lot_signal": self.inventory_lot_signal,
            "source_pages": list(self.source_pages),
            "source": self.source,
            "top5_eligible": (
                self.listing_status == "ACTIVE"
                and self.clothing_signal
                and self.inventory_lot_signal
            ),
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def parse_listing_detail(
    html_text: str,
    candidate: VareauksjonenBrowseCandidate,
) -> VareauksjonenLiveClothingListing:
    parser = _DetailParser()
    parser.feed(html_text)
    text = parser.visible_text
    lowered = text.casefold()
    title = _compact(parser.meta.get("og:title"))
    if not title and parser.headings:
        title = parser.headings[0]
    title = re.sub(r"\s+Vis\s+overvåkningsliste\s*$", "", title, flags=re.I)
    title = title or candidate.title
    description = _compact(
        parser.meta.get("og:description") or parser.meta.get("description")
    )
    listing_type = _input_value(parser.inputs, "ListingType")
    quantity_text = _input_value(parser.inputs, "Quantity")
    try:
        quantity = int(quantity_text) if quantity_text is not None else None
    except ValueError:
        quantity = None
    action_labels = {
        _compact(item.get("value")).casefold()
        for item in parser.inputs
        if item.get("type").casefold() in {"submit", "button"}
    }
    action_labels.update(_compact(item).casefold() for item in parser.buttons)
    has_live_action = any(
        term in label
        for label in action_labels
        for term in ("kjøp nå", "kjop na", "send bud", "legg inn bud", "by nå")
    )
    ended = any(term in lowered for term in ("avsluttet", "fullført", "solgt", "ikke aktivt"))
    active = bool(re.search(r"(?:^|\s)Aktiv(?:\s|$)", text, flags=re.I)) and has_live_action and not ended
    combined = " ".join((title, description, _compact(parser.meta.get("keywords"))))
    clothing = bool(_CLOTHING_PATTERN.search(combined))
    lot = bool(_LOT_PATTERN.search(combined)) or bool(quantity and quantity > 1)
    return VareauksjonenLiveClothingListing(
        listing_id=candidate.listing_id,
        title=title,
        url=candidate.url,
        listing_status="ACTIVE" if active else "NOT_ACTIVE_OR_UNVERIFIED",
        listing_type=listing_type,
        price_nok=_price(text),
        quantity=quantity,
        location=_location(text),
        description=description[:4000],
        image_url=_compact(parser.meta.get("og:image")) or None,
        clothing_signal=clothing,
        inventory_lot_signal=lot,
        source_pages=candidate.source_pages,
    )


@dataclass(frozen=True, slots=True)
class VareauksjonenCollection:
    captured_at: str
    crawl_delay_seconds: float
    page_diagnostics: tuple[dict[str, Any], ...]
    candidates: tuple[VareauksjonenBrowseCandidate, ...]
    listings: tuple[VareauksjonenLiveClothingListing, ...]
    scan_complete: bool
    errors: tuple[dict[str, str], ...] = ()

    @property
    def inventory_opportunities(self) -> tuple[VareauksjonenLiveClothingListing, ...]:
        return tuple(
            item
            for item in self.listings
            if item.listing_status == "ACTIVE"
            and item.clothing_signal
            and item.inventory_lot_signal
        )

    @property
    def individual_clothing_items(self) -> tuple[VareauksjonenLiveClothingListing, ...]:
        return tuple(
            item
            for item in self.listings
            if item.listing_status == "ACTIVE"
            and item.clothing_signal
            and not item.inventory_lot_signal
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "vareauksjonen-live-clothing-1.0",
            "captured_at": self.captured_at,
            "crawl_delay_seconds": self.crawl_delay_seconds,
            "page_diagnostics": list(self.page_diagnostics),
            "candidate_count": len(self.candidates),
            "detail_pages_requested": len(self.listings),
            "active_clothing_listings": len(
                [item for item in self.listings if item.listing_status == "ACTIVE" and item.clothing_signal]
            ),
            "inventory_opportunity_count": len(self.inventory_opportunities),
            "individual_clothing_count": len(self.individual_clothing_items),
            "commercial_top5_count": min(5, len(self.inventory_opportunities)),
            "scan_complete": self.scan_complete,
            "candidates": [item.to_dict() for item in self.candidates],
            "listings": [item.to_dict() for item in self.listings],
            "errors": list(self.errors),
            "paid_search_used": False,
            "openai_api_used": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def _robots_configuration(text: str) -> tuple[float, bool, bool]:
    delay_match = re.search(r"(?im)^\s*Crawl-delay:\s*([\d.]+)\s*$", text)
    delay = float(delay_match.group(1)) if delay_match else 10.0
    rules = [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.strip().casefold().startswith("disallow:") and ":" in line
    ]
    category_blocked = any(
        value.casefold() in {"/browse", "/browse/", "/browse/*", "/browse/*/"}
        for value in rules
    )
    listing_blocked = any(
        re.match(r"(?i)^/Listing(?:/|$)", value) for value in rules
    )
    return delay, category_blocked, listing_blocked


class VareauksjonenPublicCollector:
    def __init__(
        self,
        *,
        max_candidate_details: int = MAX_CANDIDATE_DETAILS,
        timeout_seconds: float = 30.0,
        fetch_text: Callable[[str], str] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_candidate_details <= MAX_CANDIDATE_DETAILS:
            raise ValueError(
                f"max_candidate_details must be between 1 and {MAX_CANDIDATE_DETAILS}"
            )
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.max_candidate_details = max_candidate_details
        self.timeout_seconds = timeout_seconds
        self.fetch_text = fetch_text or self._fetch_text
        self.sleep_fn = sleep_fn

    def _fetch_text(self, url: str) -> str:
        if url != ROBOTS_URL and not (
            is_approved_public_page(url) or is_approved_listing_url(url)
        ):
            raise ValueError("URL is outside the approved Vareauksjonen scope")
        request = Request(
            _request_url(url),
            headers={
                "Accept": "text/plain,*/*;q=0.1" if url == ROBOTS_URL else "text/html,application/xhtml+xml",
                "User-Agent": "OpportunityEngine/Vareauksjonen-Clothing-Adapter-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Vareauksjonen returned HTTP {response.status}")
            return response.read().decode("utf-8", errors="replace")

    def collect(self) -> VareauksjonenCollection:
        captured_at = datetime.now(timezone.utc).isoformat()
        diagnostics: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        try:
            robots = self.fetch_text(ROBOTS_URL)
            delay, category_blocked, listing_blocked = _robots_configuration(robots)
            if delay <= 0 or delay > MAX_CRAWL_DELAY_SECONDS:
                raise RuntimeError("published crawl delay is outside the safe supported range")
            if category_blocked or listing_blocked:
                raise RuntimeError("robots.txt disallows required browse or listing pages")
        except Exception as exc:
            return VareauksjonenCollection(
                captured_at=captured_at,
                crawl_delay_seconds=0,
                page_diagnostics=(),
                candidates=(),
                listings=(),
                scan_complete=False,
                errors=({"url": ROBOTS_URL, "stage": "robots", "error": str(exc)},),
            )

        merged: dict[int, VareauksjonenBrowseCandidate] = {}
        for page_url, page_role in PUBLIC_PAGE_SPECS:
            self.sleep_fn(delay)
            try:
                page_html = self.fetch_text(page_url)
                page_candidates = parse_browse_candidates(
                    page_html,
                    page_url=page_url,
                    page_role=page_role,
                )
                diagnostics.append(
                    {
                        "url": page_url,
                        "role": page_role,
                        "candidate_count": len(page_candidates),
                        "status": "READ",
                    }
                )
                for candidate in page_candidates:
                    existing = merged.get(candidate.listing_id)
                    if existing is None:
                        merged[candidate.listing_id] = candidate
                    else:
                        merged[candidate.listing_id] = VareauksjonenBrowseCandidate(
                            listing_id=existing.listing_id,
                            title=existing.title if len(existing.title) >= len(candidate.title) else candidate.title,
                            url=existing.url,
                            source_pages=tuple(dict.fromkeys((*existing.source_pages, *candidate.source_pages))),
                            source_roles=tuple(dict.fromkeys((*existing.source_roles, *candidate.source_roles))),
                        )
            except Exception as exc:
                errors.append({"url": page_url, "stage": "browse", "error": str(exc)})
                diagnostics.append(
                    {"url": page_url, "role": page_role, "candidate_count": 0, "status": "ERROR"}
                )

        candidates = tuple(sorted(merged.values(), key=lambda item: item.listing_id, reverse=True))[
            : self.max_candidate_details
        ]
        listings: list[VareauksjonenLiveClothingListing] = []
        for candidate in candidates:
            self.sleep_fn(delay)
            try:
                detail_html = self.fetch_text(candidate.url)
                listings.append(parse_listing_detail(detail_html, candidate))
            except Exception as exc:
                errors.append({"url": candidate.url, "stage": "detail", "error": str(exc)})

        return VareauksjonenCollection(
            captured_at=captured_at,
            crawl_delay_seconds=delay,
            page_diagnostics=tuple(diagnostics),
            candidates=candidates,
            listings=tuple(listings),
            scan_complete=not errors and len(diagnostics) == len(PUBLIC_PAGE_SPECS),
            errors=tuple(errors),
        )


def write_vareauksjonen_artifacts(
    collection: VareauksjonenCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "vareauksjonen-live-clothing-listings.json"
    individuals_path = target / "active-individual-clothing-items.json"
    top5_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    report_path.write_text(
        json.dumps(collection.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    individuals_path.write_text(
        json.dumps(
            [item.to_dict() for item in collection.individual_clothing_items],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    top5_path.write_text(
        json.dumps(
            [item.to_dict() for item in collection.inventory_opportunities[:5]],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "Vareauksjonen live clothing inventory adapter",
        f"Public pages read: {len(collection.page_diagnostics)}",
        f"Crawl delay respected: {collection.crawl_delay_seconds:g} seconds",
        f"Candidate detail pages read: {len(collection.listings)}",
        f"Valid inventory opportunities: {len(collection.inventory_opportunities)}",
        f"Individual clothing items excluded: {len(collection.individual_clothing_items)}",
        f"Commercial Top 5 count: {min(5, len(collection.inventory_opportunities))}",
        f"Scan complete: {collection.scan_complete}",
        f"Errors: {len(collection.errors)}",
        "Paid Brave/OpenAI calls: 0",
        "Automatic contact/bid/purchase/payment: false",
    ]
    if collection.inventory_opportunities:
        lines.extend(("", "Verified active clothing inventory lots:"))
        for item in collection.inventory_opportunities[:5]:
            lines.append(f"- {item.title} | {item.location or 'unknown'} | {item.url}")
    else:
        lines.extend(("", "No active clothing inventory lot was found."))
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "individuals": individuals_path,
        "commercial_top5": top5_path,
        "summary": summary_path,
    }