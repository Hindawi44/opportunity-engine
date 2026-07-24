"""Canonical V2.9 contract for auction-cost and logistics evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from opportunity_engine.evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceType,
    ResearchEvidence,
)

_COST_COMPONENTS = {
    "auction_price": (EvidenceType.COST, "auction_price_nok", False),
    "auction_fee": (EvidenceType.COST, "auction_fee_nok", True),
    "vat": (EvidenceType.COST, "vat_nok", True),
    "transport": (EvidenceType.LOGISTICS, "transport_cost_nok", True),
    "dismantling": (EvidenceType.LOGISTICS, "dismantling_cost_nok", True),
    "storage": (EvidenceType.LOGISTICS, "storage_cost_nok", True),
}
_BLOCKED_HOSTS = {"unknown.no", "example.com", "example.org", "example.net", "localhost"}


def _value(candidate: Any, name: str, default: Any = None) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _public_https_url(raw: Any) -> str:
    url = str(raw or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host or host in _BLOCKED_HOSTS:
        raise ValueError("source_url must be a real public HTTPS URL")
    if host.endswith((".local", ".localhost", ".invalid", ".test", ".example")):
        raise ValueError("source_url must be a real public HTTPS URL")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("source_url must not point to a private or reserved address")
    return url


def candidate_to_auction_cost_evidence(candidate: Any, opportunity_id: str) -> ResearchEvidence:
    """Convert one explicit auction-cost candidate into canonical persisted evidence.

    No other writer may construct auction cost or logistics evidence manually.
    Zero is accepted only when the candidate explicitly states ``zero_cost_confirmed=True``;
    auction price itself must always be positive.
    """
    opportunity_id = str(opportunity_id or "").strip()
    if not opportunity_id:
        raise ValueError("opportunity_id is required")

    component = str(_value(candidate, "component") or "").strip().casefold()
    if component not in _COST_COMPONENTS:
        raise ValueError("unsupported cost component")
    evidence_type, financial_field, zero_allowed = _COST_COMPONENTS[component]

    amount = _value(candidate, "amount_nok", _value(candidate, "numeric_value"))
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ValueError("amount_nok is required")
    amount = float(amount)
    zero_confirmed = _value(candidate, "zero_cost_confirmed") is True
    if amount < 0 or (amount == 0 and (not zero_allowed or not zero_confirmed)):
        raise ValueError("amount_nok must be positive unless a zero cost is explicitly confirmed")

    currency = str(_value(candidate, "currency") or "NOK").strip().upper()
    if currency != "NOK":
        raise ValueError("currency must be NOK")

    source_url = _public_https_url(_value(candidate, "source_url", _value(candidate, "url")))
    source_name = str(_value(candidate, "source_name") or "").strip()
    if not source_name:
        raise ValueError("source_name is required")

    observed_at = str(_value(candidate, "observed_at") or datetime.now(timezone.utc).isoformat()).strip()
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc

    basis = str(_value(candidate, "basis") or "").strip()
    if not basis:
        raise ValueError("basis is required")

    statement = f"Verified {component.replace('_', ' ')} cost: {amount:.2f} NOK."
    return ResearchEvidence.create(
        opportunity_id=opportunity_id,
        evidence_type=evidence_type,
        statement=statement,
        source_name=source_name,
        source_url=source_url,
        confidence=EvidenceConfidence.HIGH,
        direction=EvidenceDirection.NEUTRAL,
        numeric_value=amount,
        currency="NOK",
        notes=basis,
        metadata={
            "schema_version": "2.9",
            "cost_component": component,
            "financial_field": financial_field,
            "zero_cost_confirmed": zero_confirmed,
            "observed_at": observed_at,
            "external": True,
        },
    )
