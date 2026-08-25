"""Controlled commercial-anchor query expansion.

Commercial entity names may improve discovery recall, but they are search anchors
only. They never count as project-domain, inventory, sale, price, quantity or
Exact-Lot evidence.
"""
from __future__ import annotations

from typing import Any

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)

MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET = 2

ALLOWED_COMMERCIAL_ANCHOR_TYPES = frozenset(
    {"BRAND", "RETAIL_CHAIN", "BRIDAL", "WHOLESALER", "MANUFACTURER"}
)

# V1 deliberately keeps the default active catalog small. The type contract
# supports the approved commercial-anchor families without creating a source
# list or a separate runtime.
COMMERCIAL_ANCHORS: dict[str, tuple[tuple[str, str], ...]] = {
    CLOTHING_INVENTORY: (
        ("BRAND", "Jack & Jones"),
        ("BRIDAL", "Pronovias"),
        ("RETAIL_CHAIN", "Vero Moda"),
    ),
    FABRIC_PROCUREMENT: (
        ("WHOLESALER", "Wouters Textiles"),
    ),
}

# Market-specific anchors are allowed only when prior live Exact-Lot evidence
# proves that the commercial entity is a useful discovery route. This is still
# an entity-name search anchor, never a domain/URL pin and never qualification
# evidence. Germany's Salzmann route yielded 22 strict Exact-Lots in live
# checkpoint 32813183448, while checkpoint 32814383057 showed that relying on a
# bridal-brand query to rediscover that route is unstable.
MARKET_COMMERCIAL_ANCHORS: dict[
    tuple[str, str], tuple[tuple[str, str], ...]
] = {
    (CLOTHING_INVENTORY, "DE"): (
        ("WHOLESALER", "Salzmann Restwaren"),
        ("BRAND", "Jack & Jones"),
    ),
}

_QUERY_FRAMES: dict[str, dict[str, str]] = {
    CLOTHING_INVENTORY: {
        "NO": "Norge klær clothing {anchor} restlager grossist parti til salgs",
        "SE": "Sverige kläder clothing {anchor} restparti grossist lager säljes",
        "DE": "Deutschland Bekleidung clothing {anchor} Restposten Großhandel Lager zu verkaufen",
        "FR": "France vêtements clothing {anchor} déstockage grossiste stock lot à vendre",
        "IT": "Italia abbigliamento clothing {anchor} stock lotto ingrosso in vendita",
        "NL": "Nederland kleding clothing {anchor} restpartij groothandel voorraad te koop",
    },
    FABRIC_PROCUREMENT: {
        "NO": "Norge stoff fabric {anchor} restlager engros ruller til salgs",
        "SE": "Sverige tyg fabric {anchor} restparti grossist rullar säljes",
        "DE": "Deutschland Stoff fabric {anchor} Restposten Großhandel Rollen zu verkaufen",
        "FR": "France tissu fabric {anchor} déstockage grossiste rouleaux à vendre",
        "IT": "Italia tessuto fabric {anchor} stock ingrosso rotoli in vendita",
        "NL": "Nederland stof fabric {anchor} restpartij groothandel rollen te koop",
    },
}


def build_commercial_anchor_queries(
    *,
    market: str,
    project_domain: str,
    max_queries: int = MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
) -> tuple[dict[str, Any], ...]:
    """Return a bounded source-neutral anchor query pack for one market/domain."""
    market_code = str(market or "").upper().strip()
    if max_queries < 0:
        raise ValueError("max_queries must be non-negative")
    if max_queries > MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET:
        raise ValueError(
            f"max_queries must be <= {MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET}"
        )
    frame = _QUERY_FRAMES.get(project_domain, {}).get(market_code)
    if not frame or not max_queries:
        return ()

    anchors = MARKET_COMMERCIAL_ANCHORS.get(
        (project_domain, market_code),
        COMMERCIAL_ANCHORS.get(project_domain, ()),
    )
    market_specific = (project_domain, market_code) in MARKET_COMMERCIAL_ANCHORS

    rows: list[dict[str, Any]] = []
    for anchor_type, anchor_value in anchors:
        if anchor_type not in ALLOWED_COMMERCIAL_ANCHOR_TYPES:
            raise ValueError(f"unsupported commercial anchor type: {anchor_type}")
        rows.append(
            {
                "market_code": market_code,
                "project_domain": project_domain,
                "anchor_type": anchor_type,
                "anchor_value": anchor_value,
                "anchor_origin": (
                    "EVIDENCE_BACKED_MARKET_ENTITY_V1"
                    if market_specific
                    else "CONTROLLED_GLOBAL_CATALOG_V1"
                ),
                "query": frame.format(anchor=anchor_value),
                "anchor_is_qualification_evidence": False,
                "source_specific": False,
            }
        )
        if len(rows) >= max_queries:
            break
    return tuple(rows)
