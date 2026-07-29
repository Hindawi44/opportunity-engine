"""Bounded public Auksjoner.no adapter for active clothing inventory auctions.

Production reads only robots.txt and the current auction calendar. The past
auction page is never queried. Current auctions are extracted from the public
Next.js ``__NEXT_DATA__`` payload and promoted only when they are active, future
ending, clothing-related, and contain explicit inventory/lot evidence.

No paid search, AI API, login, contact, bid, purchase, reservation, or payment is
performed.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.auksjoner.no"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
CURRENT_AUCTIONS_URL = f"{BASE_URL}/nb-NO/auctions"
DEFAULT_DELAY_SECONDS = 2.0
MAX_DELAY_SECONDS = 30.0
MAX_AUCTIONS = 100
_ACTIVE_STATE_NAMES = frozenset(
    {
        "active",
        "open",
        "started",
        "published",
        "ongoing",
        "in progress",
        "inprogress",
    }
)
_CLOTHING_PATTERN = re.compile(
    r"\b(klær|klaer|klesbutikk|jakke|jakker|bukse|bukser|sko|skotøy|skotoy|"
    r"kjole|kjoler|skjorte|skjorter|genser|gensere|frakk|frakker|dress|dresser|"
    r"vest|vester|tøy|toy|arbeidsklær|arbeidsklaer|arbeidstøy|arbeidstoy|"
    r"tekstil|tekstiler|veske|vesker|belte|belter|overall|kjeledress|uniform|"
    r"undertøy|undertoy|badetøy|badetoy|herreklær|herreklaer|dameklær|dameklaer|"
    r"fjellreven|fjällräven|sportsbutikk|mote)\b",
    re.I,
)
_LOT_PATTERN = re.compile(
    r"\b(vareparti|restlager|konkursbo|lagerbeholdning|varelager|parti|bulk|"
    r"pall|paller|kolli|esker|samlet|tilslag|flere\s+(?:stk|plagg|varer|jakker|kjoler)|"
    r"(?:ca\.?\s*)?\d{2,}\s*(?:stk|plagg|varer|jakker|kjoler|bukser|skjorter|gensere|par))\b",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _parse_datetime(value: object) -> datetime | None:
    text = _compact(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_approved_current_url(url: str) -> bool:
    return str(url or "").strip() == CURRENT_AUCTIONS_URL


def build_auction_url(auction_id: int | str) -> str:
    text = _compact(auction_id)
    if not text.isdigit():
        raise ValueError("auction_id must be numeric")
    return f"{BASE_URL}/nb-NO/auctions/{text}"


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capturing = False
        self._parts: list[str] = []
        self.next_data_text: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "script":
            return
        values = {key.casefold(): value or "" for key, value in attrs}
        if values.get("id") == "__NEXT_DATA__":
            self._capturing = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._capturing:
            self.next_data_text = "".join(self._parts)
            self._capturing = False
            self._parts = []


def parse_current_auction_payload(html_text: str) -> tuple[Mapping[str, Any], ...]:
    parser = _NextDataParser()
    parser.feed(html_text)
    if not parser.next_data_text:
        raise RuntimeError("current auction page lacks __NEXT_DATA__")
    try:
        payload = json.loads(parser.next_data_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("current auction __NEXT_DATA__ is invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("current auction __NEXT_DATA__ is not an object")
    props = payload.get("props")
    page_props = props.get("pageProps") if isinstance(props, Mapping) else None
    auctions = page_props.get("auctions") if isinstance(page_props, Mapping) else None
    if not isinstance(auctions, Sequence) or isinstance(auctions, (str, bytes)):
        raise RuntimeError("current auction page lacks an auctions array")
    return tuple(item for item in auctions if isinstance(item, Mapping))


@dataclass(frozen=True, slots=True)
class AuksjonerNoLiveClothingAuction:
    auction_id: int
    title: str
    description: str
    url: str
    listing_status: str
    state_name: str | None
    starts_at: str | None
    ends_at: str | None
    buyers_premium_percent: float | None
    clothing_signal: bool
    inventory_lot_signal: bool
    source: str = "Auksjoner.no Current Auctions"

    def to_dict(self) -> dict[str, Any]:
        eligible = (
            self.listing_status == "ACTIVE"
            and self.clothing_signal
            and self.inventory_lot_signal
        )
        return {
            "auction_id": self.auction_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "listing_status": self.listing_status,
            "state_name": self.state_name,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "buyers_premium_percent": self.buyers_premium_percent,
            "price_nok": None,
            "quantity": None,
            "clothing_signal": self.clothing_signal,
            "inventory_lot_signal": self.inventory_lot_signal,
            "source": self.source,
            "top5_eligible": eligible,
            "analysis_eligible": eligible,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def normalize_current_auction(
    record: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> AuksjonerNoLiveClothingAuction | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        auction_id = int(record["auctionId"])
    except (KeyError, TypeError, ValueError):
        return None
    title = _compact(record.get("name"))
    description = _compact(record.get("description"))
    if not title:
        return None
    state = record.get("state")
    state_name = _compact(state.get("name")) if isinstance(state, Mapping) else ""
    starts = _parse_datetime(record.get("startDate"))
    ends = _parse_datetime(record.get("endDate"))
    hidden = bool(record.get("hidden"))
    active = (
        not hidden
        and state_name.casefold() in _ACTIVE_STATE_NAMES
        and ends is not None
        and ends > now
        and (starts is None or starts <= now)
    )
    combined = f"{title} {description}"
    clothing = bool(_CLOTHING_PATTERN.search(combined))
    lot = bool(_LOT_PATTERN.search(combined))
    premium: float | None = None
    try:
        if record.get("buyersPremium") not in (None, ""):
            premium = float(record["buyersPremium"])
    except (TypeError, ValueError):
        premium = None
    return AuksjonerNoLiveClothingAuction(
        auction_id=auction_id,
        title=title,
        description=description[:4000],
        url=build_auction_url(auction_id),
        listing_status="ACTIVE" if active else "NOT_ACTIVE_OR_UNVERIFIED",
        state_name=state_name or None,
        starts_at=starts.isoformat() if starts else None,
        ends_at=ends.isoformat() if ends else None,
        buyers_premium_percent=premium,
        clothing_signal=clothing,
        inventory_lot_signal=lot,
    )


def _robots_config(text: str) -> tuple[float, bool]:
    match = re.search(r"(?im)^\s*Crawl-delay:\s*([\d.]+)\s*$", text)
    delay = float(match.group(1)) if match else DEFAULT_DELAY_SECONDS
    rules = [
        line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if line.strip().casefold().startswith("disallow:") and ":" in line
    ]
    blocked = any(
        value.casefold() in {
            "/nb-no/auctions",
            "/nb-no/auctions/",
            "/nb-no/auctions/*",
            "/auctions",
            "/auctions/",
            "/auctions/*",
        }
        for value in rules
    )
    return delay, blocked


@dataclass(frozen=True, slots=True)
class AuksjonerNoCollection:
    captured_at: str
    endpoint: str
    crawl_delay_seconds: float
    items_received: int
    auctions: tuple[AuksjonerNoLiveClothingAuction, ...]
    scan_complete: bool
    errors: tuple[dict[str, str], ...] = ()

    @property
    def inventory_opportunities(self) -> tuple[AuksjonerNoLiveClothingAuction, ...]:
        return tuple(
            auction
            for auction in self.auctions
            if auction.listing_status == "ACTIVE"
            and auction.clothing_signal
            and auction.inventory_lot_signal
        )

    @property
    def clothing_non_lots(self) -> tuple[AuksjonerNoLiveClothingAuction, ...]:
        return tuple(
            auction
            for auction in self.auctions
            if auction.listing_status == "ACTIVE"
            and auction.clothing_signal
            and not auction.inventory_lot_signal
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "auksjoner-no-live-clothing-1.0",
            "captured_at": self.captured_at,
            "endpoint": self.endpoint,
            "crawl_delay_seconds": self.crawl_delay_seconds,
            "items_received": self.items_received,
            "active_clothing_auctions": len(
                [
                    item
                    for item in self.auctions
                    if item.listing_status == "ACTIVE" and item.clothing_signal
                ]
            ),
            "inventory_opportunity_count": len(self.inventory_opportunities),
            "clothing_non_lot_count": len(self.clothing_non_lots),
            "commercial_top5_count": min(5, len(self.inventory_opportunities)),
            "scan_complete": self.scan_complete,
            "auctions": [item.to_dict() for item in self.auctions],
            "errors": list(self.errors),
            "past_page_queried": False,
            "paid_search_used": False,
            "openai_api_used": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


class AuksjonerNoPublicCollector:
    def __init__(
        self,
        *,
        max_auctions: int = MAX_AUCTIONS,
        timeout_seconds: float = 30.0,
        fetch_text: Callable[[str], str] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        now: datetime | None = None,
    ) -> None:
        if not 1 <= max_auctions <= MAX_AUCTIONS:
            raise ValueError(f"max_auctions must be between 1 and {MAX_AUCTIONS}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.max_auctions = max_auctions
        self.timeout_seconds = timeout_seconds
        self.fetch_text = fetch_text or self._fetch_text
        self.sleep_fn = sleep_fn
        self.now = now

    def _fetch_text(self, url: str) -> str:
        if url not in {ROBOTS_URL, CURRENT_AUCTIONS_URL}:
            raise ValueError("URL is outside approved Auksjoner.no production scope")
        request = Request(
            url,
            headers={
                "Accept": (
                    "text/plain,*/*;q=0.1"
                    if url == ROBOTS_URL
                    else "text/html,application/xhtml+xml"
                ),
                "User-Agent": "OpportunityEngine/AuksjonerNo-Clothing-Adapter-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Auksjoner.no returned HTTP {response.status}")
            return response.read().decode("utf-8", errors="replace")

    def collect(self) -> AuksjonerNoCollection:
        captured_at = datetime.now(timezone.utc).isoformat()
        try:
            robots = self.fetch_text(ROBOTS_URL)
            delay, blocked = _robots_config(robots)
            if blocked:
                raise RuntimeError("robots.txt disallows current auction page")
            if delay <= 0 or delay > MAX_DELAY_SECONDS:
                raise RuntimeError("published crawl delay is outside safe range")
            self.sleep_fn(delay)
            current_html = self.fetch_text(CURRENT_AUCTIONS_URL)
            raw_auctions = parse_current_auction_payload(current_html)
            auctions = tuple(
                auction
                for record in raw_auctions[: self.max_auctions]
                if (auction := normalize_current_auction(record, now=self.now))
                is not None
            )
            return AuksjonerNoCollection(
                captured_at=captured_at,
                endpoint=CURRENT_AUCTIONS_URL,
                crawl_delay_seconds=delay,
                items_received=len(raw_auctions),
                auctions=auctions,
                scan_complete=True,
                errors=(),
            )
        except Exception as exc:
            return AuksjonerNoCollection(
                captured_at=captured_at,
                endpoint=CURRENT_AUCTIONS_URL,
                crawl_delay_seconds=0,
                items_received=0,
                auctions=(),
                scan_complete=False,
                errors=(
                    {
                        "url": CURRENT_AUCTIONS_URL,
                        "stage": "current_auctions",
                        "error": str(exc),
                    },
                ),
            )


def write_auksjoner_no_artifacts(
    collection: AuksjonerNoCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "auksjoner-no-live-clothing-auctions.json"
    non_lots_path = target / "active-clothing-non-lot-auctions.json"
    top5_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    report_path.write_text(
        json.dumps(collection.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    non_lots_path.write_text(
        json.dumps(
            [item.to_dict() for item in collection.clothing_non_lots],
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
        "Auksjoner.no current clothing inventory auction adapter",
        f"Current auctions received: {collection.items_received}",
        f"Crawl delay respected: {collection.crawl_delay_seconds:g} seconds",
        f"Valid inventory opportunities: {len(collection.inventory_opportunities)}",
        f"Clothing auctions without lot evidence excluded: {len(collection.clothing_non_lots)}",
        f"Commercial Top 5 count: {min(5, len(collection.inventory_opportunities))}",
        f"Scan complete: {collection.scan_complete}",
        f"Errors: {len(collection.errors)}",
        "Past auction page queried: false",
        "Paid Brave/OpenAI calls: 0",
        "Automatic contact/bid/purchase/payment: false",
    ]
    if collection.inventory_opportunities:
        lines.extend(("", "Verified active clothing inventory auctions:"))
        for item in collection.inventory_opportunities[:5]:
            lines.append(f"- {item.title} | {item.url}")
    else:
        lines.extend(("", "No active clothing inventory auction was found."))
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "non_lots": non_lots_path,
        "commercial_top5": top5_path,
        "summary": summary_path,
    }
