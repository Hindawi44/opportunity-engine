"""Conservative normalization for source-native Exact-Lot price/quantity tokens.

This module never searches, fetches, qualifies, buys, bids, contacts, converts
currency, or estimates tax/logistics. It only normalizes values already captured
from a verified source page. Ambiguous/multi-value pages fail closed.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Sequence
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = "SOURCE_NATIVE_VALUE_NORMALIZATION_V1"

_MARKET_CURRENCY = {
    "NO": "NOK",
    "SE": "SEK",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "NL": "EUR",
}
_MARKET_HOST_SUFFIX = {
    "NO": ".no",
    "SE": ".se",
}
_COUNT_UNITS = {
    "st": "COUNT",
    "st.": "COUNT",
    "stk": "COUNT",
    "plagg": "COUNT",
    "pcs": "COUNT",
    "pieces": "COUNT",
    "pièces": "COUNT",
    "pezzi": "COUNT",
    "stuks": "COUNT",
    "units": "COUNT",
}
_LABELED_QUANTITY_RE = re.compile(
    r"\b(?:kvantitet|quantity|menge|verfügbare\s+menge|verfugbare\s+menge|antall|antal|"
    r"quantité|quantite|quantità|quantita|hoeveelheid)\b\s*(?:[:|=\-]\s*)?"
    r"(?P<number>\d[\d\s.,]{0,10})\b",
    re.IGNORECASE,
)
_COUNT_QUANTITY_RE = re.compile(
    r"\b(?P<number>\d[\d\s.,]{0,10})\s*"
    r"(?P<unit>stk|st\.?|plagg|pcs|pieces|pièces|pezzi|stuks|units)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d[\d\s.,]*")
_PER_ITEM_BASIS_RE = re.compile(
    r"(?:"
    r"\b(?:pris|price)\s*(?:per|pr\.?)\s*(?:stk|st\.?|plagg|piece|unit)\b|"
    r"\bprix\s+(?:unitaire|par\s+(?:pi[eè]ce|piece))\b|"
    r"\bpar\s+(?:pi[eè]ce|piece)\b|"
    r"\b(?:al|a|per)\s+pezzo\b|"
    r"\b(?:prijs\s+)?per\s+stuk\b|"
    r"\b(?:st[uü]ckpreis|pro\s+st[uü]ck)\b|"
    r"\b(?:per\s+(?:piece|unit)|each)\b|"
    r"/(?:pc|pcs|stk|st\.?|pi[eè]ce|piece|pezzo|stuk)\b"
    r")",
    re.IGNORECASE,
)
_TOTAL_BASIS_RE = re.compile(
    r"\b(?:"
    r"totalpris|pris\s+for\s+(?:partiet|lotten)|"
    r"total\s+price|lot\s+price|"
    r"gesamtpreis|totalpreis|"
    r"prix\s+(?:du\s+lot|total)|"
    r"prezzo\s+(?:totale|del\s+lotto)|"
    r"totaalprijs|prijs\s+(?:voor|van)\s+(?:de\s+)?partij"
    r")\b",
    re.IGNORECASE,
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def capture_source_native_price_basis_candidates(
    text: str, *, limit: int = 12
) -> list[str]:
    """Capture explicit total/per-item labels without interpreting numeric values."""
    ordered: list[tuple[int, str]] = []
    for pattern in (_PER_ITEM_BASIS_RE, _TOTAL_BASIS_RE):
        for match in pattern.finditer(text):
            value = _compact(match.group(0))
            if value:
                ordered.append((match.start(), value))
    ordered.sort(key=lambda item: item[0])

    values: list[str] = []
    seen: set[str] = set()
    for _, value in ordered:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        if len(values) >= limit:
            break
    return values


def _price_basis(
    *, url: str, price_token: str, basis_candidates: Sequence[str]
) -> tuple[str, list[str]]:
    url_context = unquote(_compact(url)).replace("-", " ").replace("_", " ")
    evidence = [_compact(value) for value in basis_candidates if _compact(value)]
    contexts = [
        ("source_url", url_context),
        ("price_token", _compact(price_token)),
        *(("captured_context", value) for value in evidence),
    ]
    per_item_matches = [
        f"{source}:{match.group(0)}"
        for source, value in contexts
        if (match := _PER_ITEM_BASIS_RE.search(value))
    ]
    total_matches = [
        f"{source}:{match.group(0)}"
        for source, value in contexts
        if (match := _TOTAL_BASIS_RE.search(value))
    ]
    basis_evidence = list(dict.fromkeys([*per_item_matches, *total_matches]))
    per_item = bool(per_item_matches)
    total = bool(total_matches)
    if per_item and total:
        return "CONFLICTING", basis_evidence
    if per_item:
        return "PER_ITEM", basis_evidence
    if total:
        return "TOTAL", basis_evidence
    return "UNKNOWN", evidence


def _normalize_decimal_text(raw: str) -> Decimal | None:
    """Parse common European/Scandinavian numeric formatting conservatively."""
    match = _NUMBER_RE.search(_compact(raw))
    if not match:
        return None
    token = match.group(0).replace(" ", "")
    if not token:
        return None

    if "," in token and "." in token:
        # The last separator is treated as the decimal mark; the other is grouping.
        decimal_sep = "," if token.rfind(",") > token.rfind(".") else "."
        grouping_sep = "." if decimal_sep == "," else ","
        token = token.replace(grouping_sep, "").replace(decimal_sep, ".")
    elif "," in token:
        head, tail = token.rsplit(",", 1)
        token = head.replace(",", "") + (f".{tail}" if len(tail) in {1, 2} else tail)
    elif "." in token:
        head, tail = token.rsplit(".", 1)
        token = head.replace(".", "") + (f".{tail}" if len(tail) in {1, 2} else tail)

    try:
        value = Decimal(token)
    except InvalidOperation:
        return None
    if value <= 0:
        return None
    return value


def _host_matches_market(url: str, market: str) -> bool:
    suffix = _MARKET_HOST_SUFFIX.get(market)
    if not suffix:
        return False
    try:
        host = (urlsplit(_compact(url)).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return bool(host and (host.endswith(suffix) or host == suffix.lstrip(".")))


def _currency_from_token(token: str, *, market: str, url: str) -> str | None:
    lowered = _compact(token).casefold()
    if "€" in token or re.search(r"\b(?:eur|euro)\b", lowered):
        return "EUR"
    if re.search(r"\bsek\b", lowered):
        return "SEK"
    if re.search(r"\bnok\b", lowered):
        return "NOK"
    if re.search(r"\bkr\.?\b", lowered):
        expected = _MARKET_CURRENCY.get(market)
        if expected in {"SEK", "NOK"} and _host_matches_market(url, market):
            return expected
    return None


def _normalize_price(token: str, *, market: str, url: str) -> dict[str, Any] | None:
    amount = _normalize_decimal_text(token)
    currency = _currency_from_token(token, market=market, url=url)
    if amount is None or currency is None:
        return None
    return {
        "source_token": _compact(token),
        "amount": float(amount),
        "amount_decimal": format(amount, "f"),
        "currency": currency,
    }


def _normalize_quantity(token: str) -> dict[str, Any] | None:
    compact = _compact(token)
    labeled = _LABELED_QUANTITY_RE.search(compact)
    if labeled:
        amount = _normalize_decimal_text(labeled.group("number"))
        if amount is None or amount != amount.to_integral_value():
            return None
        return {
            "source_token": compact,
            "amount": int(amount),
            "unit": "COUNT",
            "unit_inferred_from_labeled_quantity": True,
        }

    count = _COUNT_QUANTITY_RE.search(compact)
    if not count:
        return None
    amount = _normalize_decimal_text(count.group("number"))
    unit = count.group("unit").casefold()
    if amount is None or amount != amount.to_integral_value() or unit not in _COUNT_UNITS:
        return None
    return {
        "source_token": compact,
        "amount": int(amount),
        "unit": _COUNT_UNITS[unit],
        "unit_inferred_from_labeled_quantity": False,
    }


def normalize_source_native_values(
    *,
    market: str,
    url: str,
    price_candidates: Sequence[str],
    quantity_candidates: Sequence[str],
    price_basis_candidates: Sequence[str] = (),
) -> dict[str, Any]:
    """Normalize only a single pair with an explicit total/per-item price basis."""
    prices = [_compact(value) for value in price_candidates if _compact(value)]
    quantities = [_compact(value) for value in quantity_candidates if _compact(value)]
    basis_candidates = [
        _compact(value) for value in price_basis_candidates if _compact(value)
    ]
    base = {
        "version": SCHEMA_VERSION,
        "price_basis_contract_version": "EXPLICIT_PRICE_BASIS_V1",
        "market_code": market,
        "source_url": _compact(url),
        "price_candidate_count": len(prices),
        "quantity_candidate_count": len(quantities),
        "price_basis_candidate_count": len(basis_candidates),
        "currency_conversion_performed": False,
        "tax_calculation_performed": False,
        "customs_calculation_performed": False,
        "logistics_calculation_performed": False,
        "normalization_is_qualification_evidence": False,
        "automatic_purchase_decision": False,
        "financial_analysis_ready": False,
    }

    if len(prices) != 1 or len(quantities) != 1:
        status = "AMBIGUOUS" if prices or quantities else "NO_CAPTURED_VALUES"
        return {
            **base,
            "status": status,
            "normalized_price": None,
            "normalized_quantity": None,
            "price_basis": "UNKNOWN",
            "price_basis_evidence": basis_candidates,
            "derived_unit_cost": None,
        }

    price = _normalize_price(prices[0], market=market, url=url)
    quantity = _normalize_quantity(quantities[0])
    if price is None or quantity is None:
        return {
            **base,
            "status": "UNSUPPORTED_OR_AMBIGUOUS_FORMAT",
            "normalized_price": price,
            "normalized_quantity": quantity,
            "price_basis": "UNKNOWN",
            "price_basis_evidence": basis_candidates,
            "derived_unit_cost": None,
        }

    price_basis, basis_evidence = _price_basis(
        url=url,
        price_token=prices[0],
        basis_candidates=basis_candidates,
    )
    if price_basis not in {"PER_ITEM", "TOTAL"}:
        return {
            **base,
            "status": "AMBIGUOUS_PRICE_BASIS",
            "normalized_price": price,
            "normalized_quantity": quantity,
            "price_basis": price_basis,
            "price_basis_evidence": basis_evidence,
            "derived_unit_cost": None,
        }

    if price_basis == "PER_ITEM":
        unit_cost = Decimal(price["amount_decimal"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        derivation = "SOURCE_PRICE_EXPLICITLY_PER_ITEM"
    else:
        unit_cost = (Decimal(price["amount_decimal"]) / Decimal(quantity["amount"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        derivation = "EXPLICIT_TOTAL_PRICE_DIVIDED_BY_NORMALIZED_COUNT"
    return {
        **base,
        "status": "NORMALIZED",
        "normalized_price": price,
        "normalized_quantity": quantity,
        "price_basis": price_basis,
        "price_basis_evidence": basis_evidence,
        "derived_unit_cost": {
            "amount": float(unit_cost),
            "amount_decimal": format(unit_cost, "f"),
            "currency": price["currency"],
            "per_unit": "COUNT",
            "derivation": derivation,
        },
    }
