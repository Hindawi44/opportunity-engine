"""Exact public VENTA item-page verification and source logistics extraction.

This layer closes two gaps in the catalog-level VENTA watch:

* clothing words embedded in equipment names (for example ``Kleiderstangen``
  and ``Kleiderhaken``) must not create clothing-inventory opportunities;
* explicit bulk clothing lots should be checked on their exact public item page
  before source-backed pickup/logistics facts are exposed downstream.

The verifier is deliberately conservative. It never logs in, bids, contacts a
seller, purchases, pays, estimates missing shipment facts, converts currencies,
or calculates VAT/customs/logistics. Missing values remain missing.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import html
import re
from typing import Any, Mapping

import requests

from opportunity_engine.discovery.germany_venta import (
    ACTIVE,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_USER_AGENT,
    VentaPublicPage,
    canonicalize_venta_url,
)
from opportunity_engine.discovery.germany_venta_active import VentaActiveWatchResult

DEFAULT_ITEM_VERIFICATION_LIMIT = 10

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.I | re.S)
_HEADING_RE = re.compile(r"<(?:h1|h2)\b[^>]*>(?P<body>.*?)</(?:h1|h2)>", re.I | re.S)

# These are fixtures/shop equipment, not clothing inventory. The original VENTA
# catalog matcher treated the ``Kleider`` prefix as garment evidence.
_NON_CLOTHING_EQUIPMENT_RE = re.compile(
    r"\b(?:kleiderhaken|kleiderstange(?:n)?|kleiderständer|kleiderstaender|"
    r"kleiderbügel|kleiderbuegel|kleiderschrank|kleiderschränke|kleiderschraenke|"
    r"garderobenhaken|garderobenständer|garderobenstaender|schaufensterpuppe(?:n)?|"
    r"mannequin(?:s)?)\b",
    re.I,
)

_STRICT_CLOTHING_RE = re.compile(
    r"(?:bekleidung\w*|textil(?:ien)?\w*|mode(?:waren|bestand|artikel)\w*|"
    r"konfektion\w*|schuh\w*|jacke\w*|mantel\w*|mäntel\w*|maentel\w*|"
    r"hose\w*|(?:damen|herren|kinder)?kleider\b|(?:damen|herren|kinder)?kleid\b|"
    r"hemd\w*|pullover\w*|bluse\w*|rock\w*|shirt\w*|sweat\w*|anzug\w*|"
    r"blazer\w*|wäsche\w*|waesche\w*|lederbekleidung\w*)",
    re.I,
)

_LOCATION_RE = re.compile(
    r"\bStandort\s*(?:\||:)\s*(?P<value>.+?)"
    r"(?=\s+(?:Objekt|Position|Startpreis|Startgebot|Mindestpreis|Aktuelles\s+Gebot|"
    r"Höchstgebot|Aufgeld|MwSt|Mehrwertsteuer|Gesamtgewicht|Bruttogewicht|Gewicht|"
    r"Abmessungen|Maße|Masse|Dimensionen|Abholung|Besichtigung|Auktion|$))",
    re.I,
)
_POSTAL_CITY_RE = re.compile(
    r"\b(?P<postal>[0-9]{5})\s+(?P<city>[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß .'-]{1,80})"
)
_WEIGHT_RE = re.compile(
    r"\b(?:Gesamtgewicht|Bruttogewicht|Gewicht)\s*(?:\||:)?\s*"
    r"(?P<value>[0-9][0-9.,\s]*)\s*(?P<unit>kg|t)\b",
    re.I,
)
_DIMENSIONS_RE = re.compile(
    r"\b(?:Abmessungen|Maße|Masse|Dimensionen)\s*(?:\||:)?\s*"
    r"(?P<a>[0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*"
    r"(?P<b>[0-9]+(?:[.,][0-9]+)?)\s*[x×]\s*"
    r"(?P<c>[0-9]+(?:[.,][0-9]+)?)\s*(?P<unit>mm|cm|m)\b",
    re.I,
)
_PALLET_RE = re.compile(
    r"(?:\b(?:Anzahl\s+)?Paletten\s*(?:\||:)?\s*(?P<after>[0-9]+)\b|"
    r"\b(?P<before>[0-9]+)\s+Paletten\b)",
    re.I,
)
_START_PRICE_RE = re.compile(
    r"\b(?:Startpreis|Startgebot|Mindestpreis)\s*(?:\||:)?\s*€?\s*"
    r"(?P<value>[0-9][0-9.,\s]*)\s*(?:EUR|€)?\b",
    re.I,
)
_CURRENT_BID_RE = re.compile(
    r"\b(?:Aktuelles\s+Gebot|Höchstgebot|Hoechstgebot)\s*(?:\||:)?\s*€?\s*"
    r"(?P<value>[0-9][0-9.,\s]*)\s*(?:EUR|€)?\b",
    re.I,
)
_PREMIUM_RE = re.compile(
    r"\b(?:Käuferaufgeld|Kaeuferaufgeld|Aufgeld)\s*(?:\||:)?\s*"
    r"(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
    re.I,
)
_VAT_AFTER_RE = re.compile(
    r"\b(?:MwSt\.?|Mehrwertsteuer)\s*(?:\||:)?\s*"
    r"(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%",
    re.I,
)
_VAT_BEFORE_RE = re.compile(
    r"(?P<value>[0-9]+(?:[.,][0-9]+)?)\s*%\s*(?:MwSt\.?|Mehrwertsteuer)\b",
    re.I,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _strip_html(value: str) -> str:
    fragment = _SCRIPT_RE.sub(" ", value)
    fragment = _TAG_RE.sub(" ", fragment)
    return " ".join(html.unescape(fragment).split())


def _number_de(value: object) -> float | None:
    text = _compact(value).replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def _percent(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    return _number_de(match.group("value")) if match else None


def _money(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    return _number_de(match.group("value")) if match else None


def strict_clothing_title(title: object) -> bool:
    """Return clothing evidence while rejecting common shop-fixture compounds."""
    text = _compact(title)
    if not text or _NON_CLOTHING_EQUIPMENT_RE.search(text):
        return False
    return bool(_STRICT_CLOTHING_RE.search(text))


def _lot_title_is_clothing(lot: Mapping[str, Any]) -> bool:
    title = _compact(lot.get("title"))
    if strict_clothing_title(title):
        return True
    terms = {str(value).casefold() for value in lot.get("clothing_terms") or []}
    # A non-"kleider" term produced by the established parser is still useful,
    # unless the title is explicitly an equipment compound.
    if _NON_CLOTHING_EQUIPMENT_RE.search(title):
        return False
    return bool(terms - {"kleider"})


def fetch_venta_item_page(
    url: str,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> VentaPublicPage:
    """Fetch one exact public VENTA item page and fail closed on identity drift."""
    requested = canonicalize_venta_url(url)
    if requested is None or requested.kind != "ITEM_DETAIL" or not requested.object_id:
        raise ValueError("url must be an exact public VENTA item page")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be positive")

    client = session or requests
    response = client.get(
        requested.canonical_url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    final = canonicalize_venta_url(str(response.url))
    if final is None or final.kind != "ITEM_DETAIL":
        raise RuntimeError("VENTA item redirect left the exact public item scope")
    if (
        requested.catalog_number,
        requested.lot_number,
        requested.object_id,
    ) != (
        final.catalog_number,
        final.lot_number,
        final.object_id,
    ):
        raise RuntimeError("VENTA item redirect changed item identity")

    content_type = None
    if getattr(response, "headers", None):
        content_type = _compact(response.headers.get("content-type")) or None
    if content_type and "html" not in content_type.casefold():
        raise RuntimeError(f"unexpected VENTA item content type: {content_type}")

    raw = bytes(response.content)
    if len(raw) > max_response_bytes:
        raise RuntimeError(f"VENTA item page exceeds {max_response_bytes} bytes")
    encoding = getattr(response, "encoding", None) or "utf-8"
    decoded = raw.decode(encoding, errors="replace")
    compact = decoded.casefold()
    if "<html" not in compact and "<!doctype html" not in compact:
        raise RuntimeError("VENTA item response is not HTML")
    if any(marker in compact for marker in ("captcha", "cloudflare challenge")):
        raise RuntimeError("VENTA access challenge detected; no bypass attempted")

    return VentaPublicPage(
        requested_url=requested.canonical_url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=content_type,
        response_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        html=decoded,
    )


def parse_venta_item_page(
    page: VentaPublicPage,
    *,
    fallback_title: str,
    quantity: int | None,
    opportunity_identity: str,
    listing_status: str,
) -> dict[str, Any]:
    """Extract only explicit source facts needed by verification/logistics."""
    visible = _strip_html(page.html)
    headings = [_strip_html(match.group("body")) for match in _HEADING_RE.finditer(page.html)]
    source_title = next((value for value in headings if value and len(value) <= 500), "")
    title = source_title or _compact(fallback_title)
    clothing = strict_clothing_title(title) or (
        strict_clothing_title(fallback_title)
        and not _NON_CLOTHING_EQUIPMENT_RE.search(title)
    )

    location_match = _LOCATION_RE.search(visible)
    location = _compact(location_match.group("value")) if location_match else None
    source_postal_code: str | None = None
    source_city: str | None = None
    if location:
        postal_match = _POSTAL_CITY_RE.search(location)
        if postal_match:
            source_postal_code = postal_match.group("postal")
            source_city = _compact(postal_match.group("city").split(",", 1)[0])

    weight_kg: float | None = None
    weight_match = _WEIGHT_RE.search(visible)
    if weight_match:
        weight = _number_de(weight_match.group("value"))
        if weight is not None:
            weight_kg = weight * 1000.0 if weight_match.group("unit").casefold() == "t" else weight

    length_cm = width_cm = height_cm = None
    dimensions_match = _DIMENSIONS_RE.search(visible)
    if dimensions_match:
        values = [
            _number_de(dimensions_match.group("a")),
            _number_de(dimensions_match.group("b")),
            _number_de(dimensions_match.group("c")),
        ]
        if all(value is not None for value in values):
            unit = dimensions_match.group("unit").casefold()
            factor = {"mm": 0.1, "cm": 1.0, "m": 100.0}[unit]
            length_cm, width_cm, height_cm = [float(value) * factor for value in values]  # type: ignore[arg-type]

    pallet_match = _PALLET_RE.search(visible)
    pallet_count = None
    if pallet_match:
        raw_pallets = pallet_match.group("after") or pallet_match.group("before")
        pallet_count = int(raw_pallets) if raw_pallets else None

    start_price = _money(_START_PRICE_RE, visible)
    current_bid = _money(_CURRENT_BID_RE, visible)
    vat_percent = _percent(_VAT_AFTER_RE, visible)
    if vat_percent is None:
        vat_percent = _percent(_VAT_BEFORE_RE, visible)
    buyer_premium_percent = _percent(_PREMIUM_RE, visible)

    context_parts = [title]
    if quantity is not None:
        context_parts.append(f"quantity: {quantity}")
    if location:
        context_parts.append(f"location: {location}")
    if weight_kg is not None:
        context_parts.append(f"weight_kg: {weight_kg:g}")
    if all(value is not None for value in (length_cm, width_cm, height_cm)):
        context_parts.append(
            f"dimensions_cm: {length_cm:g} x {width_cm:g} x {height_cm:g}"
        )
    if pallet_count is not None:
        context_parts.append(f"pallet_count: {pallet_count}")
    if start_price is not None:
        context_parts.append(f"source start/minimum price: {start_price:g} EUR")
    if current_bid is not None:
        context_parts.append(f"source displayed bid: {current_bid:g} EUR")

    return {
        "url": page.requested_url,
        "title": title,
        "text": visible[:5000] or None,
        "location": location,
        "source_postal_code": source_postal_code,
        "source_city": source_city,
        "weight_kg": weight_kg,
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "pallet_count": pallet_count,
        "source_start_or_minimum_price_eur": start_price,
        "source_displayed_bid_eur": current_bid,
        "buyer_premium_percent": buyer_premium_percent,
        "vat_percent": vat_percent,
        "currency": "EUR" if (start_price is not None or current_bid is not None) else None,
        "quantity": quantity,
        "listing_status": listing_status,
        "page_role": "ITEM_LISTING",
        "opportunity_identity": opportunity_identity,
        "identity_stable": True,
        "clothing_inventory_evidence": clothing,
        "sale_evidence": clothing and listing_status == ACTIVE,
        "event_scenario": "LARGE_LOT_SALE",
        "bounded_context": " | ".join(context_parts)[:5000],
        "verified": True,
        "error": None,
        "response_sha256": page.sha256,
        "final_sale_price_trusted": False,
        "shipping_details_source": "VENTA_EXACT_ITEM_PAGE",
    }


def _run_full_scope_by_identity(diagnostics: Mapping[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for run in diagnostics.get("catalog_runs") or []:
        if not isinstance(run, Mapping):
            continue
        identity = _compact(run.get("opportunity_identity"))
        if identity:
            result[identity] = run.get("full_catalog_clothing_scope") is True
    return result


def _shipping_missing(verification: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _compact(verification.get("source_postal_code")):
        missing.append("source_postal_code")
    if verification.get("weight_kg") is None:
        missing.append("weight_kg")
    dimensions = all(
        verification.get(key) is not None
        for key in ("length_cm", "width_cm", "height_cm")
    )
    if not dimensions and verification.get("pallet_count") is None:
        missing.append("dimensions_or_pallet_count")
    return missing


def apply_venta_exact_item_verification(
    result: VentaActiveWatchResult,
    *,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    item_verification_limit: int = DEFAULT_ITEM_VERIFICATION_LIMIT,
) -> VentaActiveWatchResult:
    """Reject fixture false positives and verify bounded bulk item pages."""
    if item_verification_limit < 0 or item_verification_limit > 50:
        raise ValueError("item_verification_limit must be between 0 and 50")

    discovery = deepcopy(result.discovery_result)
    report = discovery["search_run_report"]
    diagnostics = report["venta_active"]
    full_scope_by_identity = _run_full_scope_by_identity(diagnostics)

    retained: list[dict[str, Any]] = []
    lexical_rejections: list[dict[str, Any]] = []
    exact_rejections: list[dict[str, Any]] = []
    item_errors: list[dict[str, Any]] = []
    item_pages_requested = 0
    item_pages_verified = 0
    verified_bulk_count = 0
    total_child_count = 0
    total_bulk_count = 0

    for raw_candidate in discovery.get("all_discovered_candidates") or []:
        if not isinstance(raw_candidate, Mapping):
            continue
        candidate = deepcopy(dict(raw_candidate))
        identity = _compact(candidate.get("opportunity_identity"))
        full_scope = full_scope_by_identity.get(identity, False)
        lots: list[dict[str, Any]] = []

        for raw_lot in candidate.get("child_lots") or []:
            if not isinstance(raw_lot, Mapping):
                continue
            lot = deepcopy(dict(raw_lot))
            if not _lot_title_is_clothing(lot):
                lexical_rejections.append(
                    {
                        "opportunity_identity": identity,
                        "object_id": lot.get("object_id"),
                        "title": lot.get("title"),
                        "reason": "clothing keyword belongs to shop fixture/equipment title",
                    }
                )
                continue
            lots.append(lot)

        verified_pages: list[dict[str, Any]] = []
        unverified_bulk_urls: list[str] = []
        verified_bulk_lots: list[dict[str, Any]] = []
        exact_checked = 0
        final_lots: list[dict[str, Any]] = []

        for lot in lots:
            if not lot.get("bulk_evidence"):
                final_lots.append(lot)
                continue
            if exact_checked >= item_verification_limit:
                unverified_bulk_urls.append(_compact(lot.get("canonical_url")))
                final_lots.append(lot)
                continue
            exact_checked += 1
            item_pages_requested += 1
            url = _compact(lot.get("canonical_url"))
            try:
                page = fetch_venta_item_page(
                    url,
                    session=session,
                    timeout=timeout,
                    max_response_bytes=max_response_bytes,
                )
                verification = parse_venta_item_page(
                    page,
                    fallback_title=_compact(lot.get("title")),
                    quantity=(
                        int(lot["quantity"])
                        if isinstance(lot.get("quantity"), int)
                        else None
                    ),
                    opportunity_identity=_compact(lot.get("opportunity_identity"))
                    or f"venta-object:{lot.get('object_id')}",
                    listing_status=_compact(lot.get("listing_status")) or ACTIVE,
                )
                item_pages_verified += 1
            except Exception as exc:
                item_errors.append(
                    {
                        "opportunity_identity": identity,
                        "object_id": lot.get("object_id"),
                        "url": url,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                unverified_bulk_urls.append(url)
                final_lots.append(lot)
                continue

            if verification.get("clothing_inventory_evidence") is not True:
                exact_rejections.append(
                    {
                        "opportunity_identity": identity,
                        "object_id": lot.get("object_id"),
                        "title": lot.get("title"),
                        "verified_title": verification.get("title"),
                        "url": url,
                        "reason": "exact item page did not verify clothing inventory",
                    }
                )
                continue

            lot["exact_item_page_verified"] = True
            lot["item_page_evidence"] = verification
            final_lots.append(lot)
            verified_pages.append(verification)
            verified_bulk_lots.append({**lot, "item_page_evidence": verification})
            verified_bulk_count += 1

        if not final_lots and not full_scope:
            continue

        candidate["child_lots"] = final_lots
        candidate["child_lot_count"] = len(final_lots)
        candidate["ordinary_child_lot_count"] = sum(
            bool(lot.get("ordinary_single_garment")) for lot in final_lots
        )
        candidate["observed_bulk_lot_count"] = sum(
            bool(lot.get("bulk_evidence")) for lot in final_lots
        )
        candidate["verified_bulk_lot_count"] = len(verified_bulk_lots)
        candidate["bulk_item_urls_requiring_verification"] = [
            value for value in unverified_bulk_urls if value
        ]
        candidate["verified_bulk_lots"] = verified_bulk_lots
        candidate["exact_item_pages_requested"] = exact_checked
        candidate["exact_item_pages_verified"] = len(verified_pages)

        if verified_pages:
            candidate.setdefault("verification", [])
            candidate["verification"] = [
                *[item for item in candidate["verification"] if isinstance(item, Mapping)],
                *verified_pages,
            ]

        # Propagate shipment facts only when one verified bulk lot is the unambiguous
        # freight target. Multiple lots stay explicit and require human lot selection.
        if len(verified_pages) == 1:
            verified = verified_pages[0]
            for key in (
                "source_postal_code",
                "source_city",
                "weight_kg",
                "length_cm",
                "width_cm",
                "height_cm",
                "pallet_count",
                "source_start_or_minimum_price_eur",
                "source_displayed_bid_eur",
                "buyer_premium_percent",
                "vat_percent",
                "shipping_details_source",
            ):
                if verified.get(key) is not None:
                    candidate[key] = verified.get(key)
            candidate["source_item_url"] = verified.get("url")
            candidate["exact_item_page_verified"] = True
            if verified.get("location"):
                candidate["location"] = verified.get("location")
            candidate["shipment_input_missing"] = _shipping_missing(verified)

        missing = [
            str(value)
            for value in candidate.get("missing_information") or []
            if str(value).strip()
        ]
        if not candidate["bulk_item_urls_requiring_verification"]:
            missing = [
                value
                for value in missing
                if "exact item-page verification" not in value.casefold()
            ]
        candidate["missing_information"] = sorted(set(missing))
        retained.append(candidate)
        total_child_count += candidate["child_lot_count"]
        total_bulk_count += candidate["observed_bulk_lot_count"]

    discovery["all_discovered_candidates"] = retained
    discovery["discovery_top5"] = []
    diagnostics["clothing_catalog_count"] = len(retained)
    diagnostics["clothing_child_lot_count"] = total_child_count
    diagnostics["observed_bulk_lot_count"] = total_bulk_count
    diagnostics["promoted_bulk_lot_count"] = 0
    diagnostics["lexical_non_clothing_lot_count"] = len(lexical_rejections)
    diagnostics["lexical_non_clothing_lots"] = lexical_rejections
    diagnostics["exact_item_non_clothing_lot_count"] = len(exact_rejections)
    diagnostics["exact_item_non_clothing_lots"] = exact_rejections
    diagnostics["exact_item_pages_requested"] = item_pages_requested
    diagnostics["exact_item_pages_verified"] = item_pages_verified
    diagnostics["verified_bulk_lot_count"] = verified_bulk_count
    diagnostics["exact_item_verification_errors"] = item_errors

    report["merged_candidates"] = len(retained)
    report["strong_leads_requiring_verification"] = len(retained)
    report["top5_count"] = 0
    report["top5_eligible_count"] = 0
    report["verification_attempted"] = item_pages_requested > 0
    report["verification_limit"] = item_verification_limit
    report["verification_failures"] = len(item_errors)
    report["opportunity_quality_status"] = (
        "LEADS_REQUIRING_VERIFICATION" if retained else "NO_VALID_OPPORTUNITIES"
    )
    report["no_opportunities_found"] = not retained
    report["false_positive_guard_triggered"] = int(
        report.get("false_positive_guard_triggered") or 0
    ) + len(lexical_rejections) + len(exact_rejections)

    adapter = report.get("source_adapter")
    if isinstance(adapter, dict):
        adapter["parent_candidate_count"] = len(retained)
        adapter["child_lot_count"] = total_child_count
        adapter["observed_bulk_lot_count"] = total_bulk_count
        adapter["promoted_bulk_candidate_count"] = 0
        adapter["single_garment_candidate_count"] = 0
        discovery["source_adapter"] = adapter

    return VentaActiveWatchResult(
        discovery_result=discovery,
        diagnostics=diagnostics,
    )
