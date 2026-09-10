"""Canonical provider-role policy for the unified search runtime.

This module records the production routing decision proven by the controlled
Exa-vs-Brave comparison:

* Exa is the primary search provider for exact lots, commercial inventory
  retrieval, and fabric procurement.
* Brave is a secondary provider. It remains an early-signal radar and may run
  one bounded Exact-Lot fallback only after Exa's final freshly verified
  coverage is weak. A Brave hit still cannot qualify anything by itself; the
  public page must pass the same strict verification and Multi-Hop gate.

The policy does not create a new runtime, add a provider, change markets, weaken
Exact-Lot evidence, or perform any commercial action.
"""
from __future__ import annotations

from dataclasses import dataclass


EXA = "exa"
BRAVE = "brave"

EXACT_LOT = "EXACT_LOT"
CLOTHING_INVENTORY_DISCOVERY = "CLOTHING_INVENTORY_DISCOVERY"
FABRIC_PROCUREMENT = "FABRIC_PROCUREMENT"
EARLY_MARKET_SIGNAL = "EARLY_MARKET_SIGNAL"
VERIFIED_EXACT_LOT_FALLBACK = "VERIFIED_EXACT_LOT_FALLBACK"

EXA_PRIMARY_ROLE = "PRIMARY_SEARCH"
BRAVE_SIGNAL_ONLY_ROLE = "SECONDARY_SIGNAL_AND_VERIFIED_FALLBACK"


@dataclass(frozen=True, slots=True)
class ProviderRole:
    provider: str
    role: str
    allowed_intents: frozenset[str]
    may_emit_opportunity_candidates: bool
    may_promote_to_opportunity: bool


PROVIDER_ROLES = {
    EXA: ProviderRole(
        provider=EXA,
        role=EXA_PRIMARY_ROLE,
        allowed_intents=frozenset(
            {
                EXACT_LOT,
                CLOTHING_INVENTORY_DISCOVERY,
                FABRIC_PROCUREMENT,
            }
        ),
        may_emit_opportunity_candidates=True,
        may_promote_to_opportunity=False,
    ),
    BRAVE: ProviderRole(
        provider=BRAVE,
        role=BRAVE_SIGNAL_ONLY_ROLE,
        allowed_intents=frozenset(
            {EARLY_MARKET_SIGNAL, VERIFIED_EXACT_LOT_FALLBACK}
        ),
        may_emit_opportunity_candidates=True,
        may_promote_to_opportunity=False,
    ),
}

PRIMARY_PROVIDER_BY_INTENT = {
    EXACT_LOT: EXA,
    CLOTHING_INVENTORY_DISCOVERY: EXA,
    FABRIC_PROCUREMENT: EXA,
    EARLY_MARKET_SIGNAL: BRAVE,
    VERIFIED_EXACT_LOT_FALLBACK: BRAVE,
}


def provider_role(provider: str) -> ProviderRole:
    normalized = str(provider or "").strip().casefold()
    try:
        return PROVIDER_ROLES[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported search provider: {provider!r}") from exc


def provider_allowed_for_intent(provider: str, intent: str) -> bool:
    normalized_intent = str(intent or "").strip().upper()
    return normalized_intent in provider_role(provider).allowed_intents


def require_provider_for_intent(provider: str, intent: str) -> None:
    """Fail closed when a provider is routed outside its approved production role."""
    normalized_intent = str(intent or "").strip().upper()
    role = provider_role(provider)
    if normalized_intent in role.allowed_intents:
        return
    raise RuntimeError(
        "SEARCH_PROVIDER_ROLE_BLOCKED: "
        f"provider={role.provider} role={role.role} intent={normalized_intent}"
    )


def primary_provider_for_intent(intent: str) -> str:
    normalized_intent = str(intent or "").strip().upper()
    try:
        return PRIMARY_PROVIDER_BY_INTENT[normalized_intent]
    except KeyError as exc:
        raise ValueError(f"unsupported search intent: {intent!r}") from exc


def production_routing_snapshot() -> dict[str, object]:
    """Return a small machine-readable statement for reports and diagnostics."""
    return {
        "schema_version": "search-provider-role-policy-1.1",
        "exact_lot_primary_provider": EXA,
        "clothing_inventory_primary_provider": EXA,
        "fabric_procurement_primary_provider": EXA,
        "early_market_signal_provider": BRAVE,
        "brave_signal_only": False,
        "brave_early_signal_allowed": True,
        "brave_exact_lot_allowed": False,
        "brave_verified_exact_lot_fallback_allowed": True,
        "brave_fallback_requires_weak_verified_exa_coverage": True,
        "brave_fallback_max_queries_per_market": 1,
        "brave_fallback_max_outbound_attempts_per_market": 1,
        "brave_hit_requires_live_page_verification": True,
        "brave_fabric_procurement_allowed": False,
        "automatic_provider_activation": False,
        "automatic_opportunity_promotion": False,
        "production_mutation": False,
    }
