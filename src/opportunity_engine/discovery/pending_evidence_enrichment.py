"""Deterministic evidence enrichment for already-verified pending Exact-Lot pages.

This module is deliberately narrower than commercial qualification. It may prove
field-specific evidence required for financial analysis, but it never decides
whether an opportunity should be bought, bid on, contacted, reserved, or paid.
Ambiguous evidence fails closed.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlsplit

from opportunity_engine.discovery.source_native_value_normalization import (
    normalize_source_native_values,
)

SCHEMA_VERSION = "PENDING_EVIDENCE_ENRICHMENT_V1"

PRICE_BLOCKER = "normalized source-native price value for financial analysis"
QUANTITY_BLOCKER = "normalized source-native quantity value for financial analysis"
CONDITION_BLOCKER = "condition"
FULFILMENT_BLOCKER = "pickup or shipping terms"
SELLER_BLOCKER = "seller or company identity"

ENRICHABLE_BLOCKERS = frozenset(
    {
        PRICE_BLOCKER,
        QUANTITY_BLOCKER,
        CONDITION_BLOCKER,
        FULFILMENT_BLOCKER,
        SELLER_BLOCKER,
    }
)

_STOCKITALY_PRICE_RE = re.compile(
    r"(?:^|/)products/(?P<whole>\d+)-(?P<cents>\d{2})-al-pezzo(?:-|/|$)",
    re.IGNORECASE,
)
_STOCKITALY_QUANTITY_RE = re.compile(
    r"-(?P<quantity>\d+)-pezzi(?:-|/|$)",
    re.IGNORECASE,
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _text_list(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    output: list[str] = []
    for raw in value:
        text = _text(raw)
        if text and text not in output:
            output.append(text)
    return output


def enrichment_target_blockers(missing_evidence: object) -> list[str]:
    """Return only blockers this enrichment stage is allowed to reason about."""
    return [
        value
        for value in _text_list(missing_evidence)
        if value.casefold() in ENRICHABLE_BLOCKERS
    ]


def _stockitaly_url_values(url: str) -> dict[str, Any] | None:
    """Parse explicit per-piece price and piece count from StockItaly24 product URLs.

    Example source-native route:
    ``/products/10-50-al-pezzo-huf-stock-abbigliamento-uomo-80-pezzi-...``
    The route itself explicitly states EUR 10.50 per piece and 80 pieces.
    """
    try:
        parsed = urlsplit(_text(url))
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host not in {"stockitaly24.com", "www.stockitaly24.com"}:
        return None

    path = unquote(parsed.path or "")
    price_match = _STOCKITALY_PRICE_RE.search(path)
    quantity_match = _STOCKITALY_QUANTITY_RE.search(path)
    if not price_match or not quantity_match:
        return None

    whole = int(price_match.group("whole"))
    cents = int(price_match.group("cents"))
    quantity = int(quantity_match.group("quantity"))
    if whole < 0 or not 0 <= cents <= 99 or quantity <= 0:
        return None
    amount_decimal = f"{whole}.{cents:02d}"
    return {
        "status": "VALIDATED_SOURCE_URL_VALUES",
        "source": "STOCKITALY24_PRODUCT_URL",
        "normalized_price": {
            "amount": float(amount_decimal),
            "amount_decimal": amount_decimal,
            "currency": "EUR",
        },
        "normalized_quantity": {
            "amount": quantity,
            "unit": "COUNT",
        },
        "price_basis": "PER_ITEM",
        "price_basis_evidence": ["source_url:al-pezzo"],
        "financial_analysis_values_only": True,
        "qualification_evidence": False,
    }


def build_pending_evidence_enrichment(
    *,
    market: str,
    url: str,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate only deterministic field evidence and fail closed otherwise."""
    source_evidence = dict(evidence or {})
    price_candidates = _text_list(source_evidence.get("source_native_price_candidates"))
    quantity_candidates = _text_list(source_evidence.get("source_native_quantity_candidates"))
    basis_candidates = _text_list(source_evidence.get("source_native_price_basis_candidates"))
    condition_candidates = _text_list(source_evidence.get("source_native_condition_candidates"))
    fulfilment_candidates = _text_list(source_evidence.get("source_native_fulfilment_candidates"))
    seller_candidates = _text_list(source_evidence.get("source_native_seller_identity_candidates"))

    normalization = normalize_source_native_values(
        market=_text(market).upper(),
        url=_text(url),
        price_candidates=price_candidates,
        quantity_candidates=quantity_candidates,
        price_basis_candidates=basis_candidates,
    )
    source_url_values = _stockitaly_url_values(url)

    validated_price = None
    validated_quantity = None
    validation_source = None
    price_basis = None
    price_basis_evidence: list[str] = []

    if source_url_values:
        validated_price = source_url_values["normalized_price"]
        validated_quantity = source_url_values["normalized_quantity"]
        validation_source = source_url_values["source"]
        price_basis = source_url_values["price_basis"]
        price_basis_evidence = list(source_url_values["price_basis_evidence"])
    elif normalization.get("status") == "NORMALIZED":
        validated_price = normalization.get("normalized_price")
        validated_quantity = normalization.get("normalized_quantity")
        validation_source = "SOURCE_NATIVE_VALUE_NORMALIZATION_V1"
        price_basis = normalization.get("price_basis")
        price_basis_evidence = list(normalization.get("price_basis_evidence") or [])

    resolved_blockers: list[str] = []
    if isinstance(validated_price, Mapping):
        resolved_blockers.append(PRICE_BLOCKER)
    if isinstance(validated_quantity, Mapping):
        resolved_blockers.append(QUANTITY_BLOCKER)

    # V1 intentionally does not auto-resolve these three fields. The capture
    # layer labels them evidence-only because snippets can be ambiguous. They
    # are surfaced for the next source-specific validator instead of promoted.
    field_statuses = {
        "normalized_price": "VALIDATED" if validated_price else "UNRESOLVED",
        "normalized_quantity": "VALIDATED" if validated_quantity else "UNRESOLVED",
        "condition": "CAPTURED_UNVALIDATED" if condition_candidates else "MISSING",
        "pickup_or_shipping_terms": (
            "CAPTURED_UNVALIDATED" if fulfilment_candidates else "MISSING"
        ),
        "seller_or_company_identity": (
            "CAPTURED_UNVALIDATED" if seller_candidates else "MISSING"
        ),
    }
    status = "VALIDATED_FIELDS" if resolved_blockers else "NO_VALIDATED_FIELDS"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "validation_source": validation_source,
        "resolved_blockers": resolved_blockers,
        "validated_price": validated_price,
        "validated_quantity": validated_quantity,
        "price_basis": price_basis,
        "price_basis_evidence": price_basis_evidence,
        "normalization": normalization,
        "field_statuses": field_statuses,
        "captured_unvalidated": {
            "condition_candidates": condition_candidates,
            "fulfilment_candidates": fulfilment_candidates,
            "seller_identity_candidates": seller_candidates,
        },
        "qualification_evidence": False,
        "commercial_decision_created": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
