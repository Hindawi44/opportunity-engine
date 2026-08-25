"""Controlled commercial-anchor query expansion.

Commercial entity names may improve discovery recall, but they are search anchors
only. They never count as project-domain, inventory, sale, price, quantity or
Exact-Lot evidence.

For Sweden, the existing anchor stage may prefer company names from a previously
persisted Bolagsverket liquidation/insolvency signal. This reuses the checkpoint
SQLite state that is already restored before discovery; it does not add a search
provider, source-specific query, runtime, or query budget.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)

MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET = 2

ALLOWED_COMMERCIAL_ANCHOR_TYPES = frozenset(
    {"BRAND", "RETAIL_CHAIN", "BRIDAL", "WHOLESALER", "MANUFACTURER", "OFFICIAL_COMPANY"}
)

SWEDEN_OFFICIAL_ANCHOR_SOURCE = "Bolagsverket Värdefulla datamängder"
SWEDEN_OFFICIAL_ANCHOR_SIGNAL_TYPE = "INSOLVENCY_OR_LIQUIDATION"
SWEDEN_OFFICIAL_ANCHOR_ORIGIN = "OFFICIAL_SWEDISH_LIQUIDATION_SIGNAL_V1"
SWEDEN_OFFICIAL_ANCHOR_DB_RELATIVE_PATH = Path("se-blinto/opportunity_engine.db")
SWEDEN_OFFICIAL_ANCHOR_SCAN_LIMIT = 100

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
        "NO": "Norge stoff fabric {anchor} restlager engros rullar till salu",
        "SE": "Sverige tyg fabric {anchor} restparti grossist rullar säljes",
        "DE": "Deutschland Stoff fabric {anchor} Restposten Großhandel Rollen zu verkaufen",
        "FR": "France tissu fabric {anchor} déstockage grossiste rouleaux à vendre",
        "IT": "Italia tessuto fabric {anchor} stock ingrosso rotoli in vendita",
        "NL": "Nederland stof fabric {anchor} restpartij groothandel rollen te koop",
    },
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_anchor_value(value: object) -> str | None:
    text = _compact(value)
    if not text or len(text) > 200:
        return None
    folded = text.casefold()
    if "site:" in folded or "://" in folded:
        return None
    if not any(character.isalpha() for character in text):
        return None
    return text


def _sweden_official_anchor_db_path() -> Path:
    input_root = _compact(os.environ.get("INPUT_ROOT")) or "artifacts/multi-market-inputs"
    return Path(input_root) / SWEDEN_OFFICIAL_ANCHOR_DB_RELATIVE_PATH


def _official_signal_payload(payload_json: object) -> dict[str, Any] | None:
    try:
        payload = json.loads(str(payload_json or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _verified_official_signal(payload_json: object) -> bool:
    payload = _official_signal_payload(payload_json)
    if payload is None:
        return False
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        return False
    if metadata.get("official_register") is not True or metadata.get("signal_only") is not True:
        return False
    evidence = payload.get("evidence") or []
    return any(
        isinstance(item, dict)
        and item.get("verified") is True
        and item.get("evidence_type") == "OFFICIAL_SWEDISH_COMPANY_STATUS"
        for item in evidence
    )


def _official_bulk_anchor(payload_json: object) -> bool:
    payload = _official_signal_payload(payload_json)
    if payload is None:
        return False
    metadata = payload.get("metadata") or {}
    return isinstance(metadata, dict) and metadata.get("official_bulk_anchor_v1") is True


def load_sweden_official_company_anchors(
    *,
    max_anchors: int = MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    database_path: str | Path | None = None,
) -> tuple[tuple[str, str], ...]:
    """Load bounded Bolagsverket-backed Swedish company anchors from restored SQLite.

    Only persisted WATCH signals with the exact official provider, Swedish country,
    insolvency/liquidation type, confidence >= 0.99 and verified official-register
    evidence are accepted. Official bulk clothing-liquidation anchors are preferred
    over legacy official signals, while the externally visible query cap remains
    unchanged. Failure or absence is a valid zero and falls back to the existing
    controlled catalog.
    """
    if max_anchors < 0:
        raise ValueError("max_anchors must be non-negative")
    if max_anchors > MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET:
        raise ValueError(
            f"max_anchors must be <= {MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET}"
        )
    if not max_anchors:
        return ()

    path = Path(database_path) if database_path is not None else _sweden_official_anchor_db_path()
    if not path.is_file():
        return ()

    rows: list[tuple[object, ...]] = []
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            rows = list(
                connection.execute(
                    """
                    SELECT company_name, source_provider, source_country, signal_type,
                           status, confidence, payload_json
                    FROM market_signals
                    WHERE source_country = ?
                      AND signal_type = ?
                      AND company_name IS NOT NULL
                      AND TRIM(company_name) <> ''
                    ORDER BY last_seen_at DESC, signal_id ASC
                    LIMIT ?
                    """,
                    (
                        "SE",
                        SWEDEN_OFFICIAL_ANCHOR_SIGNAL_TYPE,
                        SWEDEN_OFFICIAL_ANCHOR_SCAN_LIMIT,
                    ),
                )
            )
        finally:
            connection.close()
    except sqlite3.Error:
        return ()

    eligible: list[tuple[int, int, str]] = []
    for recency_rank, row in enumerate(rows):
        company_name, source_provider, source_country, signal_type, status, confidence, payload_json = row
        company = _safe_anchor_value(company_name)
        if not company:
            continue
        if _compact(source_provider) != SWEDEN_OFFICIAL_ANCHOR_SOURCE:
            continue
        if _compact(source_country).upper() != "SE":
            continue
        if _compact(signal_type) != SWEDEN_OFFICIAL_ANCHOR_SIGNAL_TYPE:
            continue
        if _compact(status).upper() != "WATCH":
            continue
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            continue
        if confidence_value < 0.99 or not _verified_official_signal(payload_json):
            continue
        bulk_priority = 0 if _official_bulk_anchor(payload_json) else 1
        eligible.append((bulk_priority, recency_rank, company))

    eligible.sort(key=lambda item: (item[0], item[1]))
    anchors: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, _, company in eligible:
        marker = company.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        anchors.append(("OFFICIAL_COMPANY", company))
        if len(anchors) >= max_anchors:
            break
    return tuple(anchors)


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

    official_sweden_anchors: tuple[tuple[str, str], ...] = ()
    if market_code == "SE" and project_domain == CLOTHING_INVENTORY:
        official_sweden_anchors = load_sweden_official_company_anchors(max_anchors=max_queries)

    if official_sweden_anchors:
        anchors = official_sweden_anchors
        anchor_origin = SWEDEN_OFFICIAL_ANCHOR_ORIGIN
    else:
        anchors = MARKET_COMMERCIAL_ANCHORS.get(
            (project_domain, market_code),
            COMMERCIAL_ANCHORS.get(project_domain, ()),
        )
        market_specific = (project_domain, market_code) in MARKET_COMMERCIAL_ANCHORS
        anchor_origin = (
            "EVIDENCE_BACKED_MARKET_ENTITY_V1"
            if market_specific
            else "CONTROLLED_GLOBAL_CATALOG_V1"
        )

    rows: list[dict[str, Any]] = []
    for anchor_type, anchor_value in anchors:
        if anchor_type not in ALLOWED_COMMERCIAL_ANCHOR_TYPES:
            raise ValueError(f"unsupported commercial anchor type: {anchor_type}")
        safe_value = _safe_anchor_value(anchor_value)
        if not safe_value:
            continue
        rows.append(
            {
                "market_code": market_code,
                "project_domain": project_domain,
                "anchor_type": anchor_type,
                "anchor_value": safe_value,
                "anchor_origin": anchor_origin,
                "query": frame.format(anchor=safe_value),
                "anchor_is_qualification_evidence": False,
                "source_specific": False,
            }
        )
        if len(rows) >= max_queries:
            break
    return tuple(rows)
