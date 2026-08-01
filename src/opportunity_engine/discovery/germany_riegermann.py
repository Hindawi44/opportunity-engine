"""Fixture-first Riegermann adapter for German clothing auction events.

The adapter parses already captured public HTML. It performs no network requests,
login, bidding, contacting, purchasing, payment, FX conversion, VAT calculation,
premium calculation, logistics calculation, or profitability analysis.

Riegermann clothing auctions are aggregated as one parent auction event with
child lots. Ordinary single-garment lots remain child evidence. Only explicit
commercial bulk lots may be emitted as separate candidates, and even those stay
outside Top 5 until their exact item page is verified by a later live adapter.
"""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    STRONG_LEAD_REQUIRES_VERIFICATION,
    UNKNOWN,
    normalize_public_url,
)

RIEGERMANN_HOST = "riegermann.de"
AUCTION_EVENT = "AUCTION_EVENT"
UPCOMING = "UPCOMING"
REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
AGGREGATION_MODE = "AUCTION_EVENT_WITH_CHILD_LOTS"

_AUCTION_INFORMATION_PATH = re.compile(
    r"^/de/[^/]+/a/(?P<auction_id>[0-9]+)/?$",
    re.I,
)
_AUCTION_CATALOG_PATH = re.compile(
    r"^/de/objekte/au-(?P<auction_id>[0-9]+)/[^/?]+/?$",
    re.I,
)
_ITEM_DETAIL_PATH = re.compile(
    r"^/de/l/(?P<object_id>[0-9]+)/[^/?]+/?$",
    re.I,
)
_ARTICLE_BLOCK = re.compile(r"<article\b[^>]*>(?P<body>.*?)</article>", re.I | re.S)
_ITEM_HREF = re.compile(
    r'''href\s*=\s*["'](?P<href>/de/l/(?P<object_id>[0-9]+)/[^"'?#]+)["']''',
    re.I,
)
_CLOTHING_TERMS = (
    "bekleidung",
    "kleidung",
    "lederbekleidung",
    "lederjacke",
    "ledermantel",
    "jacke",
    "mantel",
    "hose",
    "hosen",
    "kleid",
    "rock",
    "schuhe",
    "stiefel",
    "bluse",
    "pullover",
    "mode",
)
_BULK_TERMS = (
    "posten",
    "konvolut",
    "sortiment",
    "warenbestand",
    "lagerbestand",
    "restposten",
    "paket",
    "mehrere",
)
_QUANTITY_RE = re.compile(
    r"\b(?P<count>[0-9]{1,7})\s*"
    r"(?:stück|stk\.?|teile|jacken|mäntel|hosen|kleider|paar|artikel)\b",
    re.I,
)
_LOT_NUMBER_RE = re.compile(
    r"\b(?:los(?:-nr\.?|nummer)?|pos(?:ition)?\.?)\s*:?\s*(?P<number>[0-9A-Za-z.-]+)",
    re.I,
)
_BID_COUNT_RE = re.compile(r"\b(?P<count>[0-9]+)\s+gebote?\b", re.I)
_NOT_SOLD_TERMS = ("nicht verkauft", "ohne zuschlag")
_SOLD_TERMS = ("verkauft", "zuschlag erteilt")
_ENDED_TERMS = ("auktion beendet", "abgeschlossen", "versteigerung beendet")
_ACTIVE_TERMS = ("aktuell", "jetzt bieten", "online", "gebot abgeben")
_UPCOMING_TERMS = ("vorschau", "demnächst")
_POST_SALE_TERMS = ("nachverkauf",)


@dataclass(frozen=True, slots=True)
class RiegermannUrlIdentity:
    canonical_url: str
    kind: str
    auction_id: str | None = None
    object_id: str | None = None


@dataclass(frozen=True, slots=True)
class RiegermannChildLot:
    auction_id: str
    object_id: str
    canonical_url: str
    lot_number: str | None
    title: str
    description: str | None
    listing_status: str
    quantity: int | None
    clothing_evidence: bool
    bulk_evidence: bool
    ordinary_single_garment: bool
    promotion_eligible: bool
    top5_eligible: bool
    source_price_kind: str | None
    source_start_or_minimum_price_eur: float | None
    source_displayed_bid_eur: float | None
    source_bid_count: int | None
    final_sale_price_eur: float | None
    final_sale_price_trusted: bool
    normalized_price_eur: float | None = None
    price_nok: float | None = None
    bid_price_nok: float | None = None

    @property
    def opportunity_identity(self) -> str:
        return f"riegermann-object:{self.object_id}"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["opportunity_identity"] = self.opportunity_identity
        result["parent_opportunity_identity"] = (
            f"riegermann-auction:{self.auction_id}"
        )
        return result


@dataclass(frozen=True, slots=True)
class RiegermannAuctionEvent:
    auction_id: str
    canonical_url: str
    title: str
    listing_status: str
    scenario: str
    location: str | None
    auction_type: str | None
    bidding_start_at: str | None
    award_start_at: str | None
    award_end_at: str | None
    pickup_window: str | None
    description: str | None
    buyer_premium_percent: float | None
    vat_percent: float | None
    child_lots: tuple[RiegermannChildLot, ...]

    @property
    def opportunity_identity(self) -> str:
        return f"riegermann-auction:{self.auction_id}"

    @property
    def promoted_bulk_lots(self) -> tuple[RiegermannChildLot, ...]:
        return tuple(lot for lot in self.child_lots if lot.promotion_eligible)

    @property
    def ordinary_child_lots(self) -> tuple[RiegermannChildLot, ...]:
        return tuple(lot for lot in self.child_lots if lot.ordinary_single_garment)


@dataclass(frozen=True, slots=True)
class RiegermannAdapterResult:
    parent_candidate: dict[str, Any]
    promoted_bulk_candidates: tuple[dict[str, Any], ...]
    child_lots: tuple[dict[str, Any], ...]

    def to_discovery_result(self) -> dict[str, Any]:
        return {
            "all_discovered_candidates": [
                self.parent_candidate,
                *self.promoted_bulk_candidates,
            ],
            "discovery_top5": [],
            "source_adapter": {
                "source": "Riegermann",
                "market_code": "DE",
                "currency": "EUR",
                "aggregation_mode": AGGREGATION_MODE,
                "parent_candidate_count": 1,
                "child_lot_count": len(self.child_lots),
                "promoted_bulk_candidate_count": len(
                    self.promoted_bulk_candidates
                ),
                "single_garment_candidate_count": 0,
                "nok_price_fields_written": False,
                "normalized_price_written": False,
            },
        }


def _normalized_host(host: str | None) -> str:
    value = (host or "").casefold()
    return value[4:] if value.startswith("www.") else value


def _compact(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _strip_html(value: str) -> str:
    fragment = re.sub(
        r"<(script|style|noscript)\b[^>]*>.*?</\1>",
        " ",
        value,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(fragment).split())


def _canonical_url(parsed_path: str) -> str:
    path = parsed_path.rstrip("/") or "/"
    return urlunparse(("https", RIEGERMANN_HOST, path, "", "", ""))


def canonicalize_riegermann_url(url: str) -> RiegermannUrlIdentity | None:
    """Return a stable identity for exact public auction and item pages."""
    normalized = normalize_public_url(url)
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if _normalized_host(parsed.hostname) != RIEGERMANN_HOST:
        return None
    path = parsed.path or "/"
    match = _AUCTION_INFORMATION_PATH.fullmatch(path)
    if match:
        return RiegermannUrlIdentity(
            canonical_url=_canonical_url(path),
            kind="AUCTION_INFORMATION",
            auction_id=match.group("auction_id"),
        )
    match = _AUCTION_CATALOG_PATH.fullmatch(path)
    if match:
        return RiegermannUrlIdentity(
            canonical_url=_canonical_url(path),
            kind="AUCTION_CATALOG",
            auction_id=match.group("auction_id"),
        )
    match = _ITEM_DETAIL_PATH.fullmatch(path)
    if match:
        return RiegermannUrlIdentity(
            canonical_url=_canonical_url(path),
            kind="ITEM_DETAIL",
            object_id=match.group("object_id"),
        )
    return None


def map_riegermann_lifecycle(text: str) -> str:
    """Map explicit public Riegermann lifecycle wording conservatively."""
    normalized = _compact(text)
    if any(term in normalized for term in _ENDED_TERMS):
        return ENDED
    if any(term in normalized for term in _POST_SALE_TERMS):
        return REQUIRES_VERIFICATION
    if any(term in normalized for term in _UPCOMING_TERMS):
        return UPCOMING
    if any(term in normalized for term in _ACTIVE_TERMS):
        return ACTIVE
    return UNKNOWN


def _extract_first_tag(source: str, tags: Iterable[str]) -> str | None:
    for tag in tags:
        match = re.search(
            rf"<{tag}\b[^>]*>(?P<body>.*?)</{tag}>",
            source,
            flags=re.I | re.S,
        )
        if match:
            value = _strip_html(match.group("body")).strip()
            if value:
                return value
    return None


def _definition_value(source: str, label: str) -> str | None:
    match = re.search(
        rf"<dt\b[^>]*>\s*{re.escape(label)}\s*</dt>\s*"
        rf"<dd\b[^>]*>(?P<value>.*?)</dd>",
        source,
        flags=re.I | re.S,
    )
    if not match:
        return None
    value = _strip_html(match.group("value")).strip()
    return value or None


def _class_text(source: str, class_name: str) -> str | None:
    match = re.search(
        rf"<(?P<tag>[a-z0-9]+)\b[^>]*class=[\"'][^\"']*"
        rf"\b{re.escape(class_name)}\b[^\"']*[\"'][^>]*>"
        rf"(?P<body>.*?)</(?P=tag)>",
        source,
        flags=re.I | re.S,
    )
    if not match:
        return None
    value = _strip_html(match.group("body")).strip()
    return value or None


def _parse_number(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9,.\-]", "", value)
    if not cleaned or cleaned == "-":
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if number >= 0 else None


def _parse_eur(text: str, labels: tuple[str, ...]) -> float | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*:?\s*(?:EUR|€)?\s*"
        rf"(?P<value>[0-9][0-9 .]*(?:,[0-9]{{1,2}})?)\s*(?:EUR|€)?",
        text,
        flags=re.I,
    )
    return _parse_number(match.group("value")) if match else None


def _parse_percent(text: str, labels: tuple[str, ...]) -> float | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*:?\s*(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
        text,
        flags=re.I,
    )
    return _parse_number(match.group("value")) if match else None


def _quantity(text: str) -> int | None:
    counts = [int(match.group("count")) for match in _QUANTITY_RE.finditer(text)]
    if not counts:
        return None
    return max(counts)


def _scenario(text: str) -> str:
    normalized = _compact(text)
    if "insolvenz" in normalized:
        return "COMPANY_BANKRUPTCY"
    if any(
        term in normalized
        for term in (
            "liquidation",
            "geschäftsauflösung",
            "betriebsauflösung",
            "räumungsverkauf",
            "lagerauflösung",
        )
    ):
        return "INVENTORY_LIQUIDATION"
    return "AUCTION"


def _parse_lot_block(
    block: str,
    *,
    auction_id: str,
    fallback_status: str,
) -> RiegermannChildLot | None:
    href_match = _ITEM_HREF.search(block)
    if not href_match:
        return None
    identity = canonicalize_riegermann_url(
        f"https://{RIEGERMANN_HOST}{href_match.group('href')}"
    )
    if identity is None or identity.object_id is None:
        return None

    visible = _strip_html(block)
    title = (
        _class_text(block, "lot-title")
        or _extract_first_tag(block, ("h2", "h3", "a"))
        or f"Riegermann object {identity.object_id}"
    )
    description = _class_text(block, "description")
    combined = " ".join(value for value in (title, description, visible) if value)
    normalized = _compact(combined)
    clothing = any(term in normalized for term in _CLOTHING_TERMS)
    quantity = _quantity(combined)
    bulk = any(term in normalized for term in _BULK_TERMS) or (
        quantity is not None and quantity >= 2
    )
    ordinary = clothing and not bulk

    lot_number_match = _LOT_NUMBER_RE.search(visible)
    lot_number = (
        lot_number_match.group("number") if lot_number_match else None
    )
    bid_count_match = _BID_COUNT_RE.search(visible)
    bid_count = int(bid_count_match.group("count")) if bid_count_match else None

    minimum = _parse_eur(visible, ("Mindestpreis",))
    start = _parse_eur(visible, ("Startpreis",))
    if start is not None:
        source_price_kind = "START_PRICE"
        source_price = start
    elif minimum is not None:
        source_price_kind = "MINIMUM_PRICE"
        source_price = minimum
    else:
        source_price_kind = None
        source_price = None

    displayed_bid = _parse_eur(
        visible,
        ("Aktuelles Gebot", "Höchstgebot", "Gebot"),
    )
    if not bid_count or bid_count <= 0:
        displayed_bid = None

    not_sold = any(term in normalized for term in _NOT_SOLD_TERMS)
    sold = not not_sold and any(term in normalized for term in _SOLD_TERMS)
    final_price = _parse_eur(visible, ("Preis",)) if sold else None
    final_trusted = sold and final_price is not None

    explicit_status = map_riegermann_lifecycle(visible)
    status = explicit_status if explicit_status != UNKNOWN else fallback_status

    return RiegermannChildLot(
        auction_id=auction_id,
        object_id=identity.object_id,
        canonical_url=identity.canonical_url,
        lot_number=lot_number,
        title=title,
        description=description,
        listing_status=status,
        quantity=quantity,
        clothing_evidence=clothing,
        bulk_evidence=bulk,
        ordinary_single_garment=ordinary,
        promotion_eligible=clothing and bulk,
        top5_eligible=False,
        source_price_kind=source_price_kind,
        source_start_or_minimum_price_eur=source_price,
        source_displayed_bid_eur=displayed_bid,
        source_bid_count=bid_count,
        final_sale_price_eur=final_price,
        final_sale_price_trusted=final_trusted,
    )


def parse_riegermann_catalog_html(
    url: str,
    source_html: str,
) -> RiegermannAuctionEvent:
    """Parse one captured public auction catalog into an event and child lots."""
    identity = canonicalize_riegermann_url(url)
    if (
        identity is None
        or identity.kind not in {"AUCTION_CATALOG", "AUCTION_INFORMATION"}
        or identity.auction_id is None
    ):
        raise ValueError("url must be an exact Riegermann auction page")

    visible = _strip_html(source_html)
    title = _extract_first_tag(source_html, ("h1", "title"))
    if not title:
        raise ValueError("auction title is required")

    status = map_riegermann_lifecycle(visible)
    child_lots = tuple(
        lot
        for match in _ARTICLE_BLOCK.finditer(source_html)
        if (
            lot := _parse_lot_block(
                match.group("body"),
                auction_id=identity.auction_id,
                fallback_status=status,
            )
        )
        is not None
    )
    description = _class_text(source_html, "auction-description")
    context = " ".join(value for value in (title, description, visible) if value)

    return RiegermannAuctionEvent(
        auction_id=identity.auction_id,
        canonical_url=identity.canonical_url,
        title=title,
        listing_status=status,
        scenario=_scenario(context),
        location=_definition_value(source_html, "Ort")
        or _definition_value(source_html, "Standort")
        or _definition_value(source_html, "Abholort"),
        auction_type=_definition_value(source_html, "Auktionsart"),
        bidding_start_at=_definition_value(source_html, "Gebotsbeginn"),
        award_start_at=_definition_value(source_html, "Zuschläge ab"),
        award_end_at=_definition_value(source_html, "Zuschläge bis"),
        pickup_window=_definition_value(source_html, "Abholung"),
        description=description,
        buyer_premium_percent=_parse_percent(
            visible,
            ("Aufgeld", "Käuferaufgeld"),
        ),
        vat_percent=_parse_percent(
            visible,
            ("MwSt", "Mehrwertsteuer"),
        ),
        child_lots=child_lots,
    )


def parse_riegermann_item_html(
    url: str,
    source_html: str,
    *,
    auction_id: str,
    fallback_status: str = UNKNOWN,
) -> RiegermannChildLot:
    """Parse one captured public item page with explicit parent auction context."""
    identity = canonicalize_riegermann_url(url)
    if identity is None or identity.kind != "ITEM_DETAIL":
        raise ValueError("url must be an exact Riegermann item page")
    synthetic = (
        f'<article><a href="{urlparse(identity.canonical_url).path}">'
        f"{_extract_first_tag(source_html, ('h1', 'title')) or 'Riegermann item'}"
        f"</a>{source_html}</article>"
    )
    lot = _parse_lot_block(
        synthetic,
        auction_id=auction_id,
        fallback_status=fallback_status,
    )
    if lot is None:
        raise ValueError("item page could not be parsed")
    return lot


def _parent_candidate(event: RiegermannAuctionEvent) -> dict[str, Any]:
    child_lots = [lot.to_dict() for lot in event.child_lots]
    confirmed = [
        "source: Riegermann",
        f"auction identity: {event.opportunity_identity}",
        f"child lots observed: {len(event.child_lots)}",
        f"explicit bulk child lots: {len(event.promoted_bulk_lots)}",
    ]
    if event.location:
        confirmed.append(f"location: {event.location}")
    if event.buyer_premium_percent is not None:
        confirmed.append(
            f"source buyer premium: {event.buyer_premium_percent:g}%"
        )
    if event.vat_percent is not None:
        confirmed.append(f"source VAT wording: {event.vat_percent:g}%")

    return {
        "title": event.title,
        "scenario": event.scenario,
        "opportunity_state": STRONG_LEAD_REQUIRES_VERIFICATION,
        "reason": (
            "verified Riegermann clothing auction event retained as one parent "
            "opportunity with child lots"
        ),
        "page_role": AUCTION_EVENT,
        "opportunity_identity": event.opportunity_identity,
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "listing_status": (
            event.listing_status
            if event.listing_status in {ACTIVE, ENDED}
            else UNKNOWN
        ),
        "market_code": "DE",
        "currency": "EUR",
        "location": event.location,
        "company_name": None,
        "inventory_type": "clothing_auction_event",
        "price": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": None,
        "source_urls": [event.canonical_url],
        "source_providers": ["Riegermann"],
        "aggregation_mode": AGGREGATION_MODE,
        "child_lot_count": len(event.child_lots),
        "ordinary_child_lot_count": len(event.ordinary_child_lots),
        "promoted_bulk_lot_count": len(event.promoted_bulk_lots),
        "child_lots": child_lots,
        "confirmed_information": confirmed,
        "missing_information": [
            "verified exact item pages for promoted bulk lots",
            "cross-border logistics basis",
            "documented final payable price",
        ],
        "next_verification_step": (
            "Verify only promoted bulk child lots on exact public item pages."
        ),
        "next_action": (
            "Retain ordinary garments as child evidence; verify explicit bulk lots."
        ),
    }


def _bulk_candidate(
    event: RiegermannAuctionEvent,
    lot: RiegermannChildLot,
) -> dict[str, Any]:
    return {
        "title": lot.title,
        "scenario": "LARGE_LOT_SALE",
        "opportunity_state": STRONG_LEAD_REQUIRES_VERIFICATION,
        "reason": (
            "explicit Riegermann commercial bulk lot requires exact item-page "
            "verification before Top 5"
        ),
        "page_role": ITEM_LISTING,
        "opportunity_identity": lot.opportunity_identity,
        "parent_opportunity_identity": event.opportunity_identity,
        "identity_stable": True,
        "top5_eligible": False,
        "analysis_eligible": False,
        "promotion_eligible": True,
        "listing_status": (
            lot.listing_status
            if lot.listing_status in {ACTIVE, ENDED}
            else UNKNOWN
        ),
        "market_code": "DE",
        "currency": "EUR",
        "location": event.location,
        "company_name": None,
        "inventory_type": "commercial_clothing_bulk_lot",
        "price": None,
        "price_nok": None,
        "bid_price_nok": None,
        "quantity": lot.quantity,
        "source_urls": [lot.canonical_url],
        "source_providers": ["Riegermann"],
        "source_object_id": lot.object_id,
        "lot_number": lot.lot_number,
        "source_price_kind": lot.source_price_kind,
        "source_start_or_minimum_price_eur": (
            lot.source_start_or_minimum_price_eur
        ),
        "source_displayed_bid_eur": lot.source_displayed_bid_eur,
        "source_bid_count": lot.source_bid_count,
        "final_sale_price_eur": lot.final_sale_price_eur,
        "final_sale_price_trusted": lot.final_sale_price_trusted,
        "normalized_price_enabled": False,
        "fx_conversion_enabled": False,
        "confirmed_information": [
            "explicit commercial bulk wording or documented quantity",
            f"source object identity: {lot.opportunity_identity}",
        ],
        "missing_information": [
            "verified exact item description",
            "documented final payable price",
            "cross-border logistics basis",
        ],
        "next_verification_step": (
            "Open and verify the exact public Riegermann item page."
        ),
        "next_action": "Keep outside Top 5 until exact item-page verification.",
    }


def build_riegermann_adapter_result(
    event: RiegermannAuctionEvent,
) -> RiegermannAdapterResult:
    """Build one parent candidate and only explicit bulk child candidates."""
    promoted = tuple(_bulk_candidate(event, lot) for lot in event.promoted_bulk_lots)
    return RiegermannAdapterResult(
        parent_candidate=_parent_candidate(event),
        promoted_bulk_candidates=promoted,
        child_lots=tuple(lot.to_dict() for lot in event.child_lots),
    )
