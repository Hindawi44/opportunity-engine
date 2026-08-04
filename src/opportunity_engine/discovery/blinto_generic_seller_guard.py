"""Reject generic Blinto seller roles before Swedish identity resolution.

This guard operates on the bounded seller-identity report produced from public
Blinto pages. Generic role descriptions such as ``återförsäljare`` are preserved
as classifications, but they are never allowed to become company identities.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping


_GENERIC_SELLER_CLASSIFICATIONS = {
    "återförsäljare": "RESELLER_OR_DEALER",
    "aterforsaljare": "RESELLER_OR_DEALER",
    "återförsäljaren": "RESELLER_OR_DEALER",
    "aterforsaljaren": "RESELLER_OR_DEALER",
    "reseller": "RESELLER_OR_DEALER",
    "dealer": "RESELLER_OR_DEALER",
    "distributör": "DISTRIBUTOR_OR_SUPPLIER",
    "distributor": "DISTRIBUTOR_OR_SUPPLIER",
    "leverantör": "DISTRIBUTOR_OR_SUPPLIER",
    "leverantoren": "DISTRIBUTOR_OR_SUPPLIER",
    "supplier": "DISTRIBUTOR_OR_SUPPLIER",
    "företag": "GENERIC_BUSINESS_ROLE",
    "foretag": "GENERIC_BUSINESS_ROLE",
    "company": "GENERIC_BUSINESS_ROLE",
    "säljare": "GENERIC_SELLER_ROLE",
    "saljare": "GENERIC_SELLER_ROLE",
    "seller": "GENERIC_SELLER_ROLE",
}
_TRAILING_PUNCTUATION_RE = re.compile(r"[\s\.,;:!?…'\"”’\)\]\}]+$")
_LEADING_PUNCTUATION_RE = re.compile(r"^[\s\.,;:!?…'\"“‘\(\[\{]+")


def _normalise_role_label(value: object) -> str:
    text = " ".join(str(value or "").split())
    text = _LEADING_PUNCTUATION_RE.sub("", text)
    text = _TRAILING_PUNCTUATION_RE.sub("", text)
    return text.casefold()


def generic_seller_classification(value: object) -> str | None:
    """Return a classification when ``value`` is only a generic seller role."""

    return _GENERIC_SELLER_CLASSIFICATIONS.get(_normalise_role_label(value))


def sanitize_blinto_seller_identity_report(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove generic role labels from company identity fields truthfully."""

    sanitized = deepcopy(dict(report))
    evidence: list[dict[str, Any]] = []
    rejected = 0

    for raw_item in sanitized.get("seller_evidence") or ():
        if not isinstance(raw_item, Mapping):
            continue
        item = deepcopy(dict(raw_item))
        classification = generic_seller_classification(item.get("company_name"))
        if classification is not None:
            item["company_name"] = None
            item["seller_type"] = item.get("seller_type") or classification
            rejected += 1
        evidence.append(item)

    sanitized["seller_evidence"] = evidence
    sanitized["seller_evidence_count"] = len(evidence)
    sanitized["accepted_identity_count"] = sum(
        bool(item.get("company_name") or item.get("organisationsnummer"))
        for item in evidence
    )
    sanitized["explicit_company_name_count"] = sum(
        bool(item.get("company_name")) for item in evidence
    )
    sanitized["organisation_number_count"] = sum(
        bool(item.get("organisationsnummer")) for item in evidence
    )
    sanitized["seller_classification_count"] = sum(
        bool(item.get("seller_type")) for item in evidence
    )
    sanitized["generic_identity_rejection_count"] = rejected

    if (
        sanitized.get("status") == "SUCCESS"
        and sanitized["accepted_identity_count"] == 0
    ):
        sanitized["status"] = "VALID_ZERO"

    return sanitized
