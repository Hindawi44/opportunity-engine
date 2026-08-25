"""Persistence and proven-route continuity parity for FR/IT/NL Exa expansion markets.

This is a bounded compatibility layer over the existing unified search runtime.
It adds no search request, provider, source, market, runtime, agent, or qualification
rule. It only:

* persists FR/IT/NL unified Exact-Lot reports into the same SQLite shape already
  used by NO/SE/DE;
* extends the existing previous-checkpoint SQLite allow-list with those three DBs;
* lets the existing proven-route recovery use prior FR/IT/NL strict URLs even when
  Exa's current top results drift to different hosts, still under the existing
  12-recovery-fetch and global page-fetch ceilings;
* provides one transitional, auditable IT route seed from checkpoint #340 only
  when no restored IT Exa SQLite database exists yet.

Every remembered URL is freshly fetched and must pass the unchanged strict
Exact-Lot verifier. Route memory is never qualification evidence and receives no
Tool Learning credit.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import unquote, urlsplit

from opportunity_engine.discovery import checkpoint_state_restore
from opportunity_engine.discovery import provider_unique_page_verification as verifier
from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime
from opportunity_engine.persistence.live_unified_persistence import (
    UnifiedPersistenceExecutionError,
    persist_unified_report_with_artifacts,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

VERSION = "EXPANSION_ROUTE_CONTINUITY_V1"
BOOTSTRAP_SCHEMA_VERSION = "proven-route-bootstrap-1.0"
EXPANSION_MARKETS = frozenset({"FR", "IT", "NL"})
EXPANSION_DATABASE_RELATIVE_PATHS = (
    "fr-exa-exact-lot/opportunity_engine.db",
    "it-exa-exact-lot/opportunity_engine.db",
    "nl-exa-exact-lot/opportunity_engine.db",
)
PROVEN_ROUTE_BOOTSTRAP_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "learning"
    / "proven-route-bootstrap-v1.json"
)
SEARCH_REQUESTS_ADDED = 0
_INSTALLED = False

_ORIGINAL_ROUTE_LOADER = verifier._load_proven_route_recovery_candidates
_ORIGINAL_RUN_EXPANSION_CLOTHING_EXA = runtime._run_expansion_clothing_exa


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _title_from_url(url: str) -> str:
    token = unquote(urlsplit(url).path or "").strip("/").rsplit("/", 1)[-1]
    return _compact(token.replace("-", " ").replace("_", " "))[:500]


def _candidate(
    *,
    market: str,
    query: str,
    url: str,
    title: str,
    origin: str,
    source_run_id: str = "",
) -> dict[str, str]:
    row = {
        "market_code": market,
        "query": query,
        "title": _compact(title) or _title_from_url(url) or "Historical verified clothing Exact-Lot",
        "url": url,
        "domain": verifier._normalized_host(url),
        "provider": verifier.PROVEN_ROUTE_RECOVERY_PROVIDER,
        "proven_route_recovery": "true",
        "route_memory_origin": origin,
        "route_memory_is_qualification_evidence": "false",
        "fresh_page_verification_required": "true",
    }
    if source_run_id:
        row["historical_source_run_id"] = source_run_id
    return row


def _load_hostless_sqlite_candidates(
    *,
    market: str,
    current_urls: set[str],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    """Load prior strict expansion-market URLs without requiring same-host rediscovery."""
    if market not in EXPANSION_MARKETS or limit <= 0:
        return []
    database = verifier._restored_exact_lot_database(market)
    if database is None:
        return []
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                """
                SELECT source_url, title
                FROM unified_opportunities
                WHERE market_code = ?
                  AND domain = ?
                  AND UPPER(source_provider) = 'EXA'
                  AND verified = 1
                  AND identity_stable = 1
                  AND top5_eligible = 1
                ORDER BY last_seen_at DESC, id DESC
                """,
                (market, CLOTHING_INVENTORY),
            ).fetchall()
        finally:
            connection.close()
    except (sqlite3.Error, OSError):
        return []

    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_url, raw_title in rows:
        url = _compact(raw_url)
        if not url or url in current_urls or url in seen:
            continue
        if not verifier._looks_item_specific_url(url):
            continue
        seen.add(url)
        output.append(
            _candidate(
                market=market,
                query=query,
                url=url,
                title=_compact(raw_title),
                origin="EXPANSION_SQLITE_HOSTLESS_CONTINUITY_V1",
            )
        )
        if len(output) >= limit:
            break
    return output


def _bootstrap_payload() -> dict[str, Any]:
    try:
        payload = json.loads(PROVEN_ROUTE_BOOTSTRAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("schema_version") != BOOTSTRAP_SCHEMA_VERSION:
        return {}
    if payload.get("project_domain") != CLOTHING_INVENTORY:
        return {}
    if _compact(payload.get("provider")).casefold() != "exa":
        return {}
    if payload.get("route_memory_is_qualification_evidence") is not False:
        return {}
    if payload.get("fresh_page_verification_required") is not True:
        return {}
    if int(payload.get("search_request_count") or -1) != 0:
        return {}
    for field in (
        "production_mutation",
        "automatic_query_activation",
        "automatic_provider_activation",
        "automatic_source_promotion",
        "automatic_contact",
        "automatic_bid",
        "automatic_reservation",
        "automatic_purchase",
        "automatic_payment",
    ):
        if payload.get(field) is not False:
            return {}
    return payload


def _load_transitional_bootstrap_candidates(
    *,
    market: str,
    current_urls: set[str],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    """Use the audited bootstrap only before an expansion-market DB exists."""
    if market not in EXPANSION_MARKETS or limit <= 0:
        return []
    if verifier._restored_exact_lot_database(market) is not None:
        return []
    payload = _bootstrap_payload()
    if _compact(payload.get("market_code")).upper() != market:
        return []
    source_run_id = _compact(payload.get("source_run_id"))
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_url in payload.get("strict_exact_lot_urls") or []:
        url = _compact(raw_url)
        if not url or url in current_urls or url in seen:
            continue
        if not verifier._looks_item_specific_url(url):
            continue
        seen.add(url)
        output.append(
            _candidate(
                market=market,
                query=query,
                url=url,
                title="",
                origin="HISTORICAL_STRICT_ROUTE_BOOTSTRAP_V1",
                source_run_id=source_run_id,
            )
        )
        if len(output) >= limit:
            break
    return output


def _load_expansion_route_recovery_candidates(
    *,
    market: str,
    current_hosts: set[str],
    current_urls: set[str],
    query: str,
    limit: int,
) -> list[dict[str, str]]:
    """Preserve the original same-host path, then fill only unused recovery capacity."""
    rows = list(
        _ORIGINAL_ROUTE_LOADER(
            market=market,
            current_hosts=current_hosts,
            current_urls=current_urls,
            query=query,
            limit=limit,
        )
    )
    if market not in EXPANSION_MARKETS or len(rows) >= limit:
        return rows

    used_urls = set(current_urls)
    used_urls.update(_compact(row.get("url")) for row in rows if _compact(row.get("url")))
    remaining = limit - len(rows)
    hostless = _load_hostless_sqlite_candidates(
        market=market,
        current_urls=used_urls,
        query=query,
        limit=remaining,
    )
    rows.extend(hostless)
    used_urls.update(_compact(row.get("url")) for row in hostless if _compact(row.get("url")))
    remaining = limit - len(rows)
    if remaining > 0:
        rows.extend(
            _load_transitional_bootstrap_candidates(
                market=market,
                current_urls=used_urls,
                query=query,
                limit=remaining,
            )
        )
    return rows


def _persist_expansion_market_sqlite() -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    input_root = runtime._input_root()
    for market in runtime.EXPANSION_EXA_MARKETS:
        source_dir = input_root / f"{market.casefold()}-exa-exact-lot"
        report_path = source_dir / "unified-opportunity-report.json"
        database_path = source_dir / "opportunity_engine.db"
        if not report_path.is_file():
            statuses[market] = {"status": "SKIPPED_NO_UNIFIED_REPORT"}
            continue
        try:
            summary, summary_path = persist_unified_report_with_artifacts(
                report_path,
                source_dir,
                database_url=f"sqlite:///{database_path}",
                config_path="alembic.ini",
            )
            statuses[market] = {
                "status": "SUCCESS",
                "persisted_record_count": int(summary.get("persisted_record_count") or 0),
                "database_path": database_path.as_posix(),
                "summary_path": summary_path.as_posix(),
            }
        except UnifiedPersistenceExecutionError as exc:
            statuses[market] = {
                "status": "FAILURE",
                "error": _compact(exc)[:500],
                "error_artifact": exc.artifact_path.as_posix(),
            }
    return statuses


def _run_expansion_clothing_exa_with_continuity() -> None:
    """Run the existing expansion callback, then persist its already-produced truth."""
    _ORIGINAL_RUN_EXPANSION_CLOTHING_EXA()
    statuses = _persist_expansion_market_sqlite()
    status_path = runtime._output_dir() / "unified-six-market-exa-runtime.json"
    payload = runtime._load_json(status_path)
    if payload:
        payload["expansion_route_continuity_version"] = VERSION
        payload["expansion_sqlite_persistence"] = statuses
        payload["search_requests_added_by_route_continuity"] = SEARCH_REQUESTS_ADDED
        payload["route_memory_is_qualification_evidence"] = False
        payload["fresh_page_verification_required"] = True
        payload["proven_route_recovery_uses_existing_page_fetch_ceiling"] = True
        runtime._write_json(status_path, payload)


def _extend_expansion_database_restore_allowlist() -> None:
    paths = tuple(checkpoint_state_restore.DATABASE_RELATIVE_PATHS)
    missing = tuple(path for path in EXPANSION_DATABASE_RELATIVE_PATHS if path not in paths)
    if missing:
        checkpoint_state_restore.DATABASE_RELATIVE_PATHS = (*paths, *missing)


def install_expansion_route_continuity_v1() -> bool:
    """Install synchronous compatibility patches before the existing runtime registers."""
    global _INSTALLED
    if _INSTALLED:
        return False
    _extend_expansion_database_restore_allowlist()
    verifier._load_proven_route_recovery_candidates = _load_expansion_route_recovery_candidates
    runtime._run_expansion_clothing_exa = _run_expansion_clothing_exa_with_continuity
    _INSTALLED = True
    return True
