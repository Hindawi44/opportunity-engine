"""Normalize already-fetched FABRIC_PROCUREMENT commercial evidence.

This extension stays inside ONE_UNIFIED_SEARCH_RUNTIME. It adds no search
request, page fetch, provider, source, market, agent or qualification bypass.
It only structures price/quantity evidence already present in the verified page
fetch consumed by the existing fabric route.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from opportunity_engine.discovery import unified_search_runtime_cli_hook as _runtime


_INSTALLED = False

_PRICE_SUFFIX_RE = re.compile(
    r"(?<![\d.,])(?P<amount>\d{1,7}(?:[.,]\d{1,2})?)\s*"
    r"(?P<currency>€|EUR|NOK|SEK|kr)(?![A-Za-z])",
    re.IGNORECASE,
)
_PRICE_PREFIX_RE = re.compile(
    r"(?P<currency>€|EUR|NOK|SEK|kr)\s*"
    r"(?P<amount>\d{1,7}(?:[.,]\d{1,2})?)",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(
    r"(?<![\d.,])(?P<quantity>\d{1,7}(?:[.,]\d{1,2})?)\s*"
    r"(?P<unit>lfm|laufmeter(?:n)?|meters?|metres?|mètres?|metri|"
    r"m(?![²2])|rolls?|rollen?|rotoli|rouleaux?|st(?:ü|u)ck|stuks?|pcs?|pezzi)\b",
    re.IGNORECASE,
)

_MARKET_CURRENCY = {
    "NO": "NOK",
    "SE": "SEK",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "NL": "EUR",
}

_PRICE_CONTEXT_REJECT = (
    "minimum order",
    "ordine minimo",
    "totale ordine minimo",
    "minimum bestelbedrag",
    "minimale bestelling",
    "sample",
    "campione",
    "staal",
    "shipping",
    "spedizione",
    "verzending",
    "versand",
    "free shipping",
    "gratis verzending",
)
_AREA_PRICE_AFTER_REJECT = (
    "/m²",
    "/m2",
    "pro m²",
    "pro m2",
    "per m²",
    "per m2",
    "g/m²",
    "g/m2",
)
# Cross-sell sections can contain internally coherent price/quantity pairs for
# accessories or related products. They are not evidence for the verified page's
# primary product. Truncate only at explicit section headings already present in
# the fetched page text; no extra fetch or source-specific hostname rule is used.
_CROSS_SELL_SECTION_MARKERS = (
    "zu diesem produkt empfehlen wir",
    "kunden, welche diesen artikel bestellten",
    "related products",
    "you may also like",
    "customers also bought",
)
_PAIR_MAX_DISTANCE = 90


def _number(value: str) -> float | None:
    clean = str(value or "").strip().replace(" ", "")
    if not clean:
        return None
    if "," in clean and "." in clean:
        if clean.rfind(",") > clean.rfind("."):
            clean = clean.replace(".", "").replace(",", ".")
        else:
            clean = clean.replace(",", "")
    else:
        clean = clean.replace(",", ".")
    try:
        parsed = float(clean)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _currency(raw: str, *, market: str | None) -> str | None:
    value = str(raw or "").strip().upper()
    if value in {"€", "EUR"}:
        return "EUR"
    if value in {"NOK", "SEK"}:
        return value
    if value == "KR":
        return _MARKET_CURRENCY.get(str(market or "").upper())
    return None


def _primary_product_body(body: str) -> str:
    """Exclude explicit cross-sell sections from primary-product evidence."""
    folded = body.casefold()
    cut_points = [
        folded.find(marker)
        for marker in _CROSS_SELL_SECTION_MARKERS
        if folded.find(marker) > 0
    ]
    if not cut_points:
        return body
    return body[: min(cut_points)].rstrip()


def _price_candidates(body: str, *, market: str | None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for shape, pattern in (
        ("AMOUNT_THEN_CURRENCY", _PRICE_SUFFIX_RE),
        ("CURRENCY_THEN_AMOUNT", _PRICE_PREFIX_RE),
    ):
        for match in pattern.finditer(body):
            span = (match.start(), match.end())
            if span in seen:
                continue
            seen.add(span)

            amount = _number(match.group("amount"))
            if amount is None or amount <= 0:
                # Ignore empty-cart/navigation prices such as 0,00 €.
                continue
            currency = _currency(match.group("currency"), market=market)
            if currency is None:
                continue

            before = body[max(0, match.start() - 24) : match.start()].casefold()
            after = body[match.end() : match.end() + 14].casefold()
            if any(marker in before for marker in _PRICE_CONTEXT_REJECT):
                continue
            if any(marker in after for marker in _AREA_PRICE_AFTER_REJECT):
                continue

            candidates.append(
                {
                    "price": amount,
                    "price_text": match.group(0).strip(),
                    "currency": currency,
                    "start": match.start(),
                    "end": match.end(),
                    "shape": shape,
                }
            )

    candidates.sort(key=lambda item: (int(item["start"]), int(item["end"])))
    return candidates


def _quantity_candidates(body: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for match in _QUANTITY_RE.finditer(body):
        amount = _number(match.group("quantity"))
        if amount is None or amount <= 0:
            continue
        candidates.append(
            {
                "quantity": amount,
                "quantity_unit": match.group("unit").casefold(),
                "quantity_text": match.group(0).strip(),
                "start": match.start(),
                "end": match.end(),
            }
        )
    return candidates


def _span_distance(first: Mapping[str, Any], second: Mapping[str, Any]) -> int:
    first_start = int(first["start"])
    first_end = int(first["end"])
    second_start = int(second["start"])
    second_end = int(second["end"])
    if first_end <= second_start:
        return second_start - first_end
    if second_end <= first_start:
        return first_start - second_end
    return 0


def _best_contextual_pair(
    body: str,
    *,
    prices: list[dict[str, Any]],
    quantities: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    ranked: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []

    for quantity in quantities:
        for price in prices:
            distance = _span_distance(quantity, price)
            if distance > _PAIR_MAX_DISTANCE:
                continue

            price_after_quantity = int(price["start"]) >= int(quantity["end"])
            score = (200 if price_after_quantity else 120) - distance

            # Tier tables commonly use "6 Meter € 6,50". Currency-first prices
            # immediately after a quantity are stronger purchase-price evidence
            # than an unrelated page-level total.
            if price_after_quantity and price.get("shape") == "CURRENCY_THEN_AMOUNT":
                score += 80

            # A quantity explicitly introduced as minimum-order text should not
            # outrank a later quantity+unit-price tier for the same page.
            quantity_before = body[
                max(0, int(quantity["start"]) - 24) : int(quantity["start"])
            ].casefold()
            if any(
                marker in quantity_before
                for marker in ("minimum order", "ordine minimo", "minimale bestelling")
            ):
                score -= 80

            # Stable tie-break: prefer the earliest equally strong local pair.
            ranked.append(
                (
                    score,
                    -max(int(quantity["start"]), int(price["start"])),
                    quantity,
                    price,
                )
            )

    if not ranked:
        return None

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, quantity, price = ranked[0]
    return quantity, price


def normalize_fabric_commercial_evidence(
    text: object,
    *,
    market: str | None = None,
) -> dict[str, Any]:
    """Extract conservative structured evidence from already-fetched page text."""
    body = " ".join(str(text or "").split())
    body = _primary_product_body(body)

    prices = _price_candidates(body, market=market)
    quantities = _quantity_candidates(body)
    pair = _best_contextual_pair(body, prices=prices, quantities=quantities)

    if pair is not None:
        quantity_row, price_row = pair
        price = price_row["price"]
        price_text = price_row["price_text"]
        currency = price_row["currency"]
        quantity = quantity_row["quantity"]
        quantity_unit = quantity_row["quantity_unit"]
        quantity_text = quantity_row["quantity_text"]
        pairing_mode = "CONTEXTUAL_PRICE_QUANTITY_PAIR"
    else:
        # Preserve conservative legacy behavior when only one evidence type is
        # available. Prefix-price shapes are accepted only through a contextual
        # quantity pair; this avoids broad capture of standalone shipping/sample
        # thresholds such as "€ 100".
        suffix_prices = [
            row for row in prices if row.get("shape") == "AMOUNT_THEN_CURRENCY"
        ]
        price_row = suffix_prices[0] if suffix_prices else None
        quantity_row = quantities[0] if quantities else None

        price = price_row["price"] if price_row else None
        price_text = price_row["price_text"] if price_row else None
        currency = price_row["currency"] if price_row else None
        quantity = quantity_row["quantity"] if quantity_row else None
        quantity_unit = quantity_row["quantity_unit"] if quantity_row else None
        quantity_text = quantity_row["quantity_text"] if quantity_row else None
        pairing_mode = "INDEPENDENT_SINGLE_EVIDENCE" if (price_row or quantity_row) else None

    return {
        "price": price,
        "price_text": price_text,
        "currency": currency or _MARKET_CURRENCY.get(str(market or "").upper()),
        "quantity": quantity,
        "quantity_unit": quantity_unit,
        "quantity_text": quantity_text,
        "commercial_evidence_normalized": price is not None or quantity is not None,
        "commercial_evidence_complete": price is not None and quantity is not None,
        "commercial_evidence_source": "VERIFIED_PAGE_TEXT",
        "commercial_evidence_pairing_mode": pairing_mode,
    }


# Capture the runtime's clean lazy bridge resolver before replacing the runtime
# hook with normalized evidence. The captured resolver imports the experiment
# bridge only when a page is actually verified, after package initialization.
_BASE_FABRIC_PAGE_CANDIDATE = _runtime._fabric_page_candidate


def _normalized_page_candidate(hit, *, page_fetcher):
    captured: dict[str, Any] = {}

    def capture(url: str):
        fetched = page_fetcher(url)
        captured["page"] = fetched
        return fetched

    row = dict(_BASE_FABRIC_PAGE_CANDIDATE(hit, page_fetcher=capture))
    fetched = captured.get("page")
    if fetched is None or row.get("commercial_fabric_page") is not True:
        return row

    combined = f"{getattr(fetched, 'title', '')} {getattr(fetched, 'text', '')}"
    evidence = normalize_fabric_commercial_evidence(combined)
    row.update(
        {
            "normalized_price": evidence["price"],
            "normalized_price_text": evidence["price_text"],
            "normalized_currency": evidence["currency"],
            "normalized_quantity": evidence["quantity"],
            "normalized_quantity_unit": evidence["quantity_unit"],
            "normalized_quantity_text": evidence["quantity_text"],
            "commercial_evidence_normalized": evidence["commercial_evidence_normalized"],
            "commercial_evidence_complete": evidence["commercial_evidence_complete"],
            "commercial_evidence_source": evidence["commercial_evidence_source"],
            "commercial_evidence_pairing_mode": evidence[
                "commercial_evidence_pairing_mode"
            ],
        }
    )
    return row


def _normalized_runtime_candidate(*, market: str, row: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(_BASE_RUNTIME_FABRIC_CANDIDATE(market=market, row=row))
    price = row.get("normalized_price")
    quantity = row.get("normalized_quantity")
    currency = row.get("normalized_currency") or _MARKET_CURRENCY.get(market.upper())
    complete = price is not None and quantity is not None
    candidate.update(
        {
            "price_text": row.get("normalized_price_text"),
            "price": price,
            "currency": currency,
            "quantity": quantity,
            "quantity_unit": row.get("normalized_quantity_unit"),
            "commercial_evidence_normalized": bool(row.get("commercial_evidence_normalized")),
            "commercial_evidence_complete": complete,
            "commercial_evidence_source": row.get("commercial_evidence_source")
            or "VERIFIED_PAGE_TEXT",
            "commercial_evidence_pairing_mode": row.get(
                "commercial_evidence_pairing_mode"
            ),
            "analysis_eligible": complete,
            # Fabric remains separate from clothing Top5 even when analysis-ready.
            "top5_eligible": False,
        }
    )
    return candidate


_BASE_RUNTIME_FABRIC_CANDIDATE = _runtime._fabric_candidate


def install_fabric_route_commercial_evidence_normalization_v1() -> bool:
    """Patch only the established runtime fabric verification/candidate hooks.

    The Search Experiment bridge keeps its own conservative verifier. Avoiding
    an eager back-import here prevents clean-interpreter circular imports while
    preserving normalized evidence on the unified production runtime.
    """
    global _INSTALLED
    if _INSTALLED:
        return False
    _runtime._fabric_page_candidate = _normalized_page_candidate
    _runtime._fabric_candidate = _normalized_runtime_candidate
    _INSTALLED = True
    return True
