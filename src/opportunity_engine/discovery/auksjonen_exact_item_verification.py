"""Exact public Auksjonen item-page verification for inventory opportunities.

The verifier fetches only the already-discovered public item page and extracts
source-published facts. It never logs in, contacts a seller, bids, buys, pays,
estimates missing shipment data, or infers commercial values from images.
"""
from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .auksjonen_public_api_adapter import AuksjonenLiveClothingListing

DEFAULT_ITEM_VERIFICATION_LIMIT = 5
DEFAULT_MAX_RESPONSE_BYTES = 3_000_000
_AUKSJONEN_ITEM_HOSTS = frozenset({"ny.auksjonen.no", "www.auksjonen.no", "auksjonen.no"})

_SCRIPT_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_H1_RE = re.compile(r"<h1\b[^>]*>(?P<body>.*?)</h1>", re.I | re.S)
_META_DESCRIPTION_RE = re.compile(
    r"<meta\b[^>]*(?:name|property)=[\"'](?:description|og:description)[\"'][^>]*content=[\"'](?P<value>.*?)[\"'][^>]*>",
    re.I | re.S,
)
_IMG_RE = re.compile(r"<img\b[^>]*(?:src|data-src)=[\"'](?P<url>https?://[^\"']+)[\"']", re.I)
_QUANTITY_RES = (
    re.compile(r"\b(?:Antall|Mengde)\s*:?\s*(?P<value>\d{1,5})\b", re.I),
    re.compile(
        r"\b(?P<value>\d{1,5})\s*(?:stk|plagg|jakker|bukser|kjoler|skjorter|gensere|sko|varer)\b",
        re.I,
    ),
)
_QUANTITY_UNKNOWN_RE = re.compile(
    r"(?:\b(?:eksakt\s+)?antall(?:et)?(?:\s+og\s+størrelsesfordeling)?\s+"
    r"(?:er\s+)?(?:ikke\s+(?:kontrollert|oppgitt|kjent)|ukjent)\b|\bukjent\s+antall\b)",
    re.I,
)
_CONDITION_RE = re.compile(
    r"\b(?:Tilstand|Condition)\s*:?\s*(?P<value>Ny|Nytt|Nye|Ubrukt|Uåpnet|Uåpnede|Brukt|New|Used)\b",
    re.I,
)
_POSTAL_CITY_RE = re.compile(r"\b(?P<postal>\d{4})\s+(?P<city>[A-ZÆØÅ][A-Za-zÆØÅæøå .'-]{1,80})")
_WEIGHT_RE = re.compile(
    r"\b(?:Totalvekt|Bruttovekt|Vekt)\s*:?\s*(?P<value>[0-9][0-9.,\s]*)\s*(?P<unit>kg|g|t|tonn)\b",
    re.I,
)
_DIMENSIONS_RE = re.compile(
    r"\b(?:Dimensjoner|Mål(?:\s*\(L\s*[x×]\s*B\s*[x×]\s*H\))?|L\s*[x×]\s*B\s*[x×]\s*H)\s*:?\s*"
    r"(?P<a>[0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*"
    r"(?P<b>[0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*"
    r"(?P<c>[0-9]+(?:[.,][0-9]+)?)\s*(?P<unit>mm|cm|m)\b",
    re.I,
)
_PALLET_RE = re.compile(
    r"(?:\b(?:Antall\s+)?paller\s*:?\s*(?P<after>\d+)\b|\b(?P<before>\d+)\s+paller\b)",
    re.I,
)
_PREMIUM_RE = re.compile(
    r"\b(?:Kjøpersalær|Auksjonsgebyr|Salær)\s*:?\s*(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
    re.I,
)
_VAT_RE = re.compile(
    r"\b(?:MVA|Merverdiavgift)\s*:?\s*(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _strip_html(value: str) -> str:
    fragment = _SCRIPT_RE.sub(" ", value)
    fragment = _TAG_RE.sub(" ", fragment)
    return _compact(html_module.unescape(fragment))


def _number(value: object) -> float | None:
    text = _compact(value).replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number >= 0 else None


def _walk(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, Mapping):
        row = dict(value)
        yield row
        for child in row.values():
            yield from _walk(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _walk(child)


def _json_objects(html: str) -> Iterable[dict[str, Any]]:
    pattern = re.compile(
        r"<script[^>]*(?:type=[\"'](?:application/ld\+json|application/json)[\"']|id=[\"']__NEXT_DATA__[\"'])[^>]*>(.*?)</script>",
        re.I | re.S,
    )
    for match in pattern.finditer(html):
        try:
            payload = json.loads(html_module.unescape(match.group(1)).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        yield from _walk(payload)


def _first_json_value(objects: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> object | None:
    folded_keys = tuple(key.casefold() for key in keys)
    for item in objects:
        folded = {str(key).casefold(): value for key, value in item.items()}
        for key in folded_keys:
            value = folded.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _normalize_condition(value: object) -> str | None:
    text = _compact(value).casefold()
    if not text:
        return None
    if "newcondition" in text or text in {
        "ny",
        "nytt",
        "nye",
        "ubrukt",
        "uåpnet",
        "uåpnede",
        "new",
    }:
        return "NEW_OR_UNUSED"
    if "usedcondition" in text or text in {"brukt", "used"}:
        return "USED"
    return None


def _quantity_from_text(text: str) -> int | None:
    for pattern in _QUANTITY_RES:
        match = pattern.search(text)
        if match:
            value = int(match.group("value"))
            return value if value > 0 else None
    return None


def _quantity_is_explicitly_unknown(text: str) -> bool:
    """Return True when the seller explicitly says the piece count is unknown."""
    return bool(_QUANTITY_UNKNOWN_RE.search(_compact(text)))


def _labeled_quantity_from_visible_text(text: str) -> int | None:
    """Accept page-wide quantity only when it carries an explicit Antall/Mengde label."""
    match = _QUANTITY_RES[0].search(text)
    if match is None:
        return None
    value = int(match.group("value"))
    return value if value > 0 else None


def parse_auksjonen_item_page(html: str, *, fallback_title: str = "") -> dict[str, Any]:
    """Extract explicit item, condition and shipment facts from one public page."""
    visible = _strip_html(html)
    objects = list(_json_objects(html))

    heading = _H1_RE.search(html)
    title = _strip_html(heading.group("body")) if heading else None
    title = title or _compact(_first_json_value(objects, ("name", "title"))) or _compact(fallback_title) or None

    description = _compact(_first_json_value(objects, ("description", "longDescription", "shortDescription"))) or None
    if description is None:
        meta = _META_DESCRIPTION_RE.search(html)
        if meta:
            description = _compact(html_module.unescape(meta.group("value"))) or None

    # Quantity is unusually prone to false positives because auction pages contain
    # unrelated counters, navigation totals and model numbers. Trust the source's
    # own title/description first, and let an explicit "unknown/not checked"
    # statement veto any numeric field that would otherwise look authoritative.
    quantity_context = " ".join(filter(None, (title, description)))
    quantity_unknown = _quantity_is_explicitly_unknown(quantity_context)
    quantity = None
    if not quantity_unknown:
        json_quantity = _first_json_value(objects, ("quantity", "itemCount", "numberOfItems", "amountOfItems"))
        if json_quantity not in (None, ""):
            try:
                parsed_quantity = int(float(str(json_quantity)))
            except (TypeError, ValueError):
                parsed_quantity = 0
            quantity = parsed_quantity if parsed_quantity > 0 else None
        if quantity is None:
            quantity = _quantity_from_text(quantity_context)
        if quantity is None:
            quantity = _labeled_quantity_from_visible_text(visible)

    condition = _normalize_condition(_first_json_value(objects, ("itemCondition", "condition")))
    if condition is None:
        condition_match = _CONDITION_RE.search(visible)
        if condition_match:
            condition = _normalize_condition(condition_match.group("value"))

    source_postal_code = None
    source_city = None
    postal_match = _POSTAL_CITY_RE.search(visible)
    if postal_match:
        source_postal_code = postal_match.group("postal")
        source_city = _compact(postal_match.group("city").split(",", 1)[0]) or None

    weight_kg = None
    weight_match = _WEIGHT_RE.search(visible)
    if weight_match:
        weight = _number(weight_match.group("value"))
        if weight is not None:
            unit = weight_match.group("unit").casefold()
            factor = {"g": 0.001, "kg": 1.0, "t": 1000.0, "tonn": 1000.0}[unit]
            weight_kg = weight * factor

    length_cm = width_cm = height_cm = None
    dimensions_match = _DIMENSIONS_RE.search(visible)
    if dimensions_match:
        values = [_number(dimensions_match.group(name)) for name in ("a", "b", "c")]
        if all(value is not None for value in values):
            factor = {"mm": 0.1, "cm": 1.0, "m": 100.0}[dimensions_match.group("unit").casefold()]
            length_cm, width_cm, height_cm = [float(value) * factor for value in values]  # type: ignore[arg-type]

    pallet_count = None
    pallet_match = _PALLET_RE.search(visible)
    if pallet_match:
        raw = pallet_match.group("after") or pallet_match.group("before")
        pallet_count = int(raw) if raw else None

    buyer_premium_percent = None
    premium_match = _PREMIUM_RE.search(visible)
    if premium_match:
        buyer_premium_percent = _number(premium_match.group("value"))

    vat_percent = None
    vat_match = _VAT_RE.search(visible)
    if vat_match:
        vat_percent = _number(vat_match.group("value"))

    image_urls = []
    for match in _IMG_RE.finditer(html):
        image_url = html_module.unescape(match.group("url"))
        if image_url not in image_urls:
            image_urls.append(image_url)
        if len(image_urls) >= 20:
            break

    return {
        "title": title,
        "description": description,
        "quantity": quantity,
        "quantity_explicitly_unknown": quantity_unknown,
        "condition": condition,
        "source_postal_code": source_postal_code,
        "source_city": source_city,
        "weight_kg": weight_kg,
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "pallet_count": pallet_count,
        "buyer_premium_percent": buyer_premium_percent,
        "vat_percent": vat_percent,
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "visual_quantity_inference_performed": False,
        "estimated_values_added": False,
    }


def fetch_auksjonen_item_page(
    url: str,
    *,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> tuple[str, str, int, str]:
    """Fetch one exact public Auksjonen item page and fail closed on redirect drift."""
    parsed = urlparse(_compact(url))
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _AUKSJONEN_ITEM_HOSTS
        or "/auksjon/" not in parsed.path
    ):
        raise ValueError("url must be an exact public Auksjonen item page")
    if timeout <= 0 or max_response_bytes <= 0:
        raise ValueError("timeout and max_response_bytes must be positive")

    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.7",
            "User-Agent": "OpportunityEngine/Auksjonen-Exact-Item-Verification-1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - bounded public HTTPS source
        final_url = str(response.geturl())
        final = urlparse(final_url)
        if (
            final.scheme != "https"
            or final.hostname not in _AUKSJONEN_ITEM_HOSTS
            or "/auksjon/" not in final.path
        ):
            raise RuntimeError("Auksjonen item redirect left the exact public item scope")
        if parsed.path.rstrip("/").split("/")[-1] != final.path.rstrip("/").split("/")[-1]:
            raise RuntimeError("Auksjonen item redirect changed object identity")
        content_type = str(response.headers.get("Content-Type") or "")
        if "html" not in content_type.casefold():
            raise RuntimeError(f"unexpected Auksjonen item content type: {content_type}")
        raw = response.read(max_response_bytes + 1)
        if len(raw) > max_response_bytes:
            raise RuntimeError(f"Auksjonen item page exceeds {max_response_bytes} bytes")
    decoded = raw.decode("utf-8", errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("Auksjonen item response is not HTML")
    if any(marker in compact for marker in ("captcha", "cloudflare challenge")):
        raise RuntimeError("Auksjonen access challenge detected; no bypass attempted")
    return decoded, final_url, len(raw), hashlib.sha256(raw).hexdigest()


def verify_auksjonen_inventory_lots(
    listings: Sequence[AuksjonenLiveClothingListing],
    *,
    limit: int = DEFAULT_ITEM_VERIFICATION_LIMIT,
    fetcher: Callable[[str], tuple[str, str, int, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Verify a bounded number of active inventory lots on their exact item pages."""
    if limit < 0:
        raise ValueError("limit must be non-negative")
    fetch = fetcher or fetch_auksjonen_item_page
    evidence: dict[str, dict[str, Any]] = {}
    for listing in list(listings)[:limit]:
        row: dict[str, Any] = {
            "url": listing.url,
            "object_id": listing.object_id,
            "status": "FAILED",
            "exact_item_page_verified": False,
            "shipping_details_source": None,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        try:
            page_html, final_url, response_bytes, sha256 = fetch(listing.url)
            parsed = parse_auksjonen_item_page(page_html, fallback_title=listing.title)
            row.update(parsed)
            row.update(
                {
                    "status": "VERIFIED",
                    "exact_item_page_verified": True,
                    "final_url": final_url,
                    "response_bytes": response_bytes,
                    "page_sha256": sha256,
                    "shipping_details_source": "Auksjonen.no exact public item page",
                }
            )
        except Exception as exc:  # source failure is evidence, not a guessed result
            row["error"] = f"{type(exc).__name__}: {exc}"
        evidence[listing.url] = row
    return evidence


def write_auksjonen_exact_item_evidence(
    evidence: Mapping[str, Mapping[str, Any]],
    output_dir: str | Path,
) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rows = [dict(value) for value in evidence.values()]
    payload = {
        "schema_version": "auksjonen-exact-item-verification-1.0",
        "attempted_count": len(rows),
        "verified_count": sum(1 for row in rows if row.get("exact_item_page_verified") is True),
        "failed_count": sum(1 for row in rows if row.get("status") == "FAILED"),
        "items": rows,
        "visual_quantity_inference_performed": False,
        "estimated_values_added": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    path = destination / "auksjonen-exact-item-verification.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path