"""Parse source-native facts from one public ReSalg auction listing.

ReSalg renders the current bid and deadline in bounded HTML attributes/scripts,
not reliably in visible text. This parser binds those values to the page's own
Produkt-ID so related-auction cards cannot contaminate the listing. It performs
no fetch, login, contact, bid, purchase, reservation, payment or estimation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urlsplit


VERSION = "RESALG_LISTING_ENRICHMENT_V1"

_PRODUCT_ID_RE = re.compile(
    r"Produkt-ID\s*<span\b[^>]*>\s*#(?P<value>\d+)\s*</span>",
    re.IGNORECASE | re.DOTALL,
)
_CURRENT_PRICE_RE = re.compile(
    r"\b(?:let|var|const)\s+gonCurrentPrice\s*=\s*[\"'](?P<value>[\d\s.,]+)[\"']",
    re.IGNORECASE,
)
_BID_COUNT_RE = re.compile(
    r"<li\b[^>]*class=[\"'][^\"']*\bbids\b[^\"']*[\"'][^>]*>\s*Bud\s*"
    r"<span\b[^>]*>(?P<value>\d+)</span>",
    re.IGNORECASE | re.DOTALL,
)
_CONDITION_RE = re.compile(
    r"<li\b[^>]*class=[\"'][^\"']*\bcondition\b[^\"']*[\"'][^>]*>\s*Tilstand\s*"
    r"<span\b[^>]*>(?P<value>.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
_LOCATION_RE = re.compile(
    r"(?:må\s+hentes\s+på|hentes\s+på)\s*<strong>(?P<value>[^<]+)</strong>",
    re.IGNORECASE | re.DOTALL,
)
_PALLET_CONTAINER_RE = re.compile(
    r"Pakket\s+i\s+(?P<value>\d+)\s+Palle\s+konteiner",
    re.IGNORECASE,
)
_BUYER_FEE_RE = re.compile(
    r"(?P<value>\d{1,2})\s*%\s*salgsomkostninger",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


class _CountdownCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "span":
            return
        values = {key.casefold(): str(value or "") for key, value in attrs}
        if values.get("data-ppt-countdown") and values.get("data-postid"):
            self.rows.append(values)


def _compact(value: object) -> str:
    return " ".join(unescape(str(value or "")).replace("\xa0", " ").split()).strip()


def _is_resalg_listing(url: str) -> bool:
    try:
        parsed = urlsplit(_compact(url))
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    parts = [part for part in (parsed.path or "").split("/") if part]
    return bool(host == "resalg.com" and len(parts) == 2 and parts[0] == "listing")


def _decimal(raw: str) -> Decimal | None:
    token = _compact(raw).replace(" ", "")
    if not token:
        return None
    if "," in token and "." in token:
        decimal_mark = "," if token.rfind(",") > token.rfind(".") else "."
        grouping_mark = "." if decimal_mark == "," else ","
        token = token.replace(grouping_mark, "").replace(decimal_mark, ".")
    elif "," in token:
        head, tail = token.rsplit(",", 1)
        token = head.replace(",", "") + (f".{tail}" if len(tail) <= 2 else tail)
    try:
        value = Decimal(token)
    except InvalidOperation:
        return None
    return value if value >= 0 else None


def _match(pattern: re.Pattern[str], html: str) -> str:
    match = pattern.search(html)
    if not match:
        return ""
    return _compact(_TAG_RE.sub(" ", match.group("value")))


def _deadline_for_product(
    html: str,
    product_id: str,
) -> tuple[str | None, int | None]:
    parser = _CountdownCollector()
    parser.feed(html)
    matches = [row for row in parser.rows if row.get("data-postid") == product_id]
    if not matches:
        return None, None

    raw_deadline = _compact(matches[0].get("data-ppt-countdown"))
    raw_offset = _compact(matches[0].get("data-timezone"))
    try:
        local = datetime.strptime(raw_deadline, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None, None
    try:
        offset_hours = int(raw_offset)
    except ValueError:
        offset_hours = None
    if offset_hours is None or not -12 <= offset_hours <= 14:
        return local.isoformat(), None
    aware = local.replace(tzinfo=timezone(timedelta(hours=offset_hours)))
    return aware.isoformat(), offset_hours


def parse_resalg_listing(
    *,
    url: str,
    html: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return facts bound to the current ReSalg Produkt-ID, or ``None``."""
    if not _is_resalg_listing(url) or not _compact(html):
        return None
    product_id = _match(_PRODUCT_ID_RE, html)
    if not product_id:
        return None

    price_raw = _match(_CURRENT_PRICE_RE, html)
    price = _decimal(price_raw)
    deadline, offset_hours = _deadline_for_product(html, product_id)
    reference_now = now or datetime.now(timezone.utc)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=timezone.utc)
    listing_status = "UNKNOWN"
    if deadline:
        parsed_deadline = datetime.fromisoformat(deadline)
        if parsed_deadline.tzinfo is not None:
            listing_status = "ACTIVE" if parsed_deadline > reference_now else "ENDED"

    condition = _match(_CONDITION_RE, html)
    condition_code = {
        "ny": "NEW",
        "brukt": "USED",
    }.get(condition.casefold(), condition.upper() or None)
    pallet_raw = _match(_PALLET_CONTAINER_RE, html)
    pallet_count = int(pallet_raw) if pallet_raw.isdigit() else None
    fee_raw = _match(_BUYER_FEE_RE, html)
    fee_percent = int(fee_raw) if fee_raw.isdigit() else None

    return {
        "version": VERSION,
        "source": "RESALG",
        "listing_id": product_id,
        "listing_status": listing_status,
        "current_bid": (
            {
                "amount": float(price),
                "amount_decimal": format(price, "f"),
                "currency": "NOK",
                "basis": "TOTAL_AUCTION_BID_BEFORE_FEES_AND_VAT",
                "source_token": f"gonCurrentPrice={price_raw}",
            }
            if price is not None
            else None
        ),
        "bid_count": int(value) if (value := _match(_BID_COUNT_RE, html)).isdigit() else None,
        "ends_at": deadline,
        "deadline_utc_offset_hours": offset_hours,
        "condition": condition_code,
        "pickup_location": _match(_LOCATION_RE, html) or None,
        "lot_container_quantity": (
            {"amount": pallet_count, "unit": "PALLET_CONTAINER"}
            if pallet_count is not None
            else None
        ),
        "buyer_fee_percent": fee_percent,
        "vat_applies_to_entire_amount": bool(
            re.search(r"mva\)?\s+på\s+hele\s+beløpet", html, re.IGNORECASE)
        ),
        "related_listing_values_excluded_by_product_id": True,
        "enrichment_is_qualification_evidence": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


__all__ = ["VERSION", "parse_resalg_listing"]
