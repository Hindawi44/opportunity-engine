"""Normalize already-fetched FABRIC_PROCUREMENT commercial evidence.

This extension stays inside ONE_UNIFIED_SEARCH_RUNTIME. It adds no search
request, page fetch, provider, source, market, agent or qualification bypass.
It only structures price/quantity evidence already present in the verified page
fetch consumed by the existing fabric route.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from opportunity_engine.search_experiment_execution_bridge_v1 import (
    _fabric_page_candidate as _base_fabric_page_candidate,
)
from opportunity_engine.discovery import unified_search_runtime_cli_hook as _runtime
import opportunity_engine.search_experiment_execution_bridge_v1 as _bridge


_INSTALLED = False

_PRICE_RE = re.compile(
    r"(?<![\d.,])(?P<amount>\d{1,7}(?:[.,]\d{1,2})?)\s*"
    r"(?P<currency>€|EUR|NOK|SEK|kr)(?![A-Za-z])",
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


def normalize_fabric_commercial_evidence(
    text: object,
    *,
    market: str | None = None,
) -> dict[str, Any]:
    """Extract conservative structured evidence from already-fetched page text."""
    body = " ".join(str(text or "").split())

    price = None
    price_text = None
    currency = None
    for match in _PRICE_RE.finditer(body):
        amount = _number(match.group("amount"))
        if amount is None or amount <= 0:
            # Ignore empty-cart/navigation prices such as 0,00 €.
            continue
        resolved_currency = _currency(match.group("currency"), market=market)
        if resolved_currency is None:
            continue
        price = amount
        price_text = match.group(0).strip()
        currency = resolved_currency
        break

    quantity = None
    quantity_unit = None
    quantity_text = None
    for match in _QUANTITY_RE.finditer(body):
        amount = _number(match.group("quantity"))
        if amount is None or amount <= 0:
            continue
        quantity = amount
        quantity_unit = match.group("unit").casefold()
        quantity_text = match.group(0).strip()
        break

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
    }


def _normalized_page_candidate(hit, *, page_fetcher):
    captured: dict[str, Any] = {}

    def capture(url: str):
        fetched = page_fetcher(url)
        captured["page"] = fetched
        return fetched

    row = dict(_base_fabric_page_candidate(hit, page_fetcher=capture))
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
            "commercial_evidence_source": row.get("commercial_evidence_source") or "VERIFIED_PAGE_TEXT",
            "analysis_eligible": complete,
            # Fabric remains separate from clothing Top5 even when analysis-ready.
            "top5_eligible": False,
        }
    )
    return candidate


_BASE_RUNTIME_FABRIC_CANDIDATE = _runtime._fabric_candidate


def install_fabric_route_commercial_evidence_normalization_v1() -> bool:
    """Patch only the established fabric verification/candidate functions."""
    global _INSTALLED
    if _INSTALLED:
        return False
    _bridge._fabric_page_candidate = _normalized_page_candidate
    _runtime._fabric_page_candidate = _normalized_page_candidate
    _runtime._fabric_candidate = _normalized_runtime_candidate
    _INSTALLED = True
    return True
