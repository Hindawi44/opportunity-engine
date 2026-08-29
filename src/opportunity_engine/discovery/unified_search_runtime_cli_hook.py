"""Unify live Exa search truth across all six markets and both project domains.

This migration hook removes the operational gap between the legacy NO/SE/DE
checkpoint and the FR/IT/NL expansion cycles. It also adds a generic Exa fabric
procurement search for FR/IT/NL without adding hard-coded supplier domains.

Safety remains read-only: no query/source promotion, contact, bid, reservation,
purchase, or payment is enabled.
"""
from __future__ import annotations

import atexit
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit

from opportunity_engine.discovery.exa_search import ExaSearchProvider
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)


SIX_MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
EXPANSION_EXA_MARKETS = ("FR", "IT", "NL")
FABRIC_MARKETS = ("FR", "IT", "NL")
FABRIC_EXA_QUERIES = {
    "FR": "France grossiste tissus tissu en gros rouleau de tissu stock déstockage prix",
    "IT": "Italia ingrosso tessuti tessuti a stock rotoli magazzino prezzo",
    "NL": "Nederland stoffen groothandel restpartij stofrollen voorraad prijs",
}
FABRIC_RESULTS_PER_MARKET = 5
RUN_MULTI_CLI = "run_multi_market_daily_operator_checkpoint.py"
DAILY_BULLETIN_CLI = "build_domain_market_intelligence_feed.py"
UNIFIED_PIPELINE_FILENAME = "unified-six-market-pipeline-v1.json"
UNIFIED_PHONE_SUMMARY_FILENAME = "unified-six-market-phone-summary-v1.txt"
FABRIC_FILENAME = "fabric-procurement-watch.json"
_INSTALLED = False


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safety() -> dict[str, bool]:
    return {
        "production_mutation": False,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _argv_value(name: str, default: str) -> str:
    for index, value in enumerate(sys.argv):
        if value == name and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
        if value.startswith(name + "="):
            return value.split("=", 1)[1]
    return default


def _input_root() -> Path:
    return Path(_compact(os.environ.get("INPUT_ROOT")) or "artifacts/multi-market-inputs")


def _output_dir() -> Path:
    return Path(
        _compact(os.environ.get("OUTPUT_DIR"))
        or _argv_value("--output-dir", "artifacts/multi-market-daily-operator-checkpoint")
    )


def _runner_module():
    path = Path(__file__).resolve().parents[3] / "scripts" / "run_exa_exact_lot_checkpoint.py"
    spec = importlib.util.spec_from_file_location("unified_runtime_exa_checkpoint", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Exa checkpoint runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exact_urls(result: Mapping[str, Any]) -> list[str]:
    urls: set[str] = set()
    for row in result.get("all_discovered_candidates") or []:
        if not isinstance(row, Mapping):
            continue
        for url in row.get("canonical_urls") or row.get("source_urls") or []:
            clean = _compact(url)
            if clean:
                urls.add(clean)
    return sorted(urls)


def _merge_cycle_exact_truth(
    cycle_path: Path,
    *,
    market: str,
    report: Mapping[str, Any],
    urls: list[str],
) -> None:
    cycle = _load_json(cycle_path)
    if not cycle:
        return
    if _compact(report.get("status")).upper() != "SUCCESS":
        return

    exa_count = int(report.get("strict_exact_lot_count") or 0)
    existing = cycle.get("exact_lot_verification") or {}
    if not isinstance(existing, Mapping):
        existing = {}
    existing_count = int(existing.get("verified_active_exact_lot_lead_count") or 0)
    combined_count = max(existing_count, exa_count)
    existing_urls = {
        _compact(url)
        for url in existing.get("verified_exact_lot_urls") or []
        if _compact(url)
    }
    combined_urls = sorted(existing_urls | set(urls))
    existing_verified_pages = int(existing.get("source_page_verified_count") or 0)
    exa_verified_pages = int(report.get("direct_exact_lot_count") or 0) + int(
        report.get("multihop_exact_lot_count") or 0
    )

    cycle["discovery_status"] = "SUCCESS"
    cycle["discovery_accepted_signal_count"] = max(
        int(cycle.get("discovery_accepted_signal_count") or 0), exa_count
    )
    cycle["exact_lot_verification"] = {
        **dict(existing),
        "engine_version": "UNIFIED_EXA_EXACT_LOT_MULTIHOP_V1",
        "status": "SUCCESS" if combined_count else "VALID_ZERO",
        "candidate_lead_count": max(
            int(existing.get("candidate_lead_count") or 0), exa_count
        ),
        "source_page_verified_count": max(existing_verified_pages, exa_verified_pages),
        "verified_active_exact_lot_lead_count": combined_count,
        "verified_exact_lot_urls": combined_urls,
        "exa_verified_active_exact_lot_count": exa_count,
        "exa_source_mode": report.get("source_mode"),
        "exa_query_pack": report.get("query_pack"),
    }
    cycle["exact_lot_verification_status"] = cycle["exact_lot_verification"]["status"]
    cycle["primary_search_provider"] = "exa"
    cycle["unified_search_runtime"] = True
    cycle["unified_market_coverage"] = list(SIX_MARKETS)
    cycle["country_specific_exact_lot_bypass"] = False
    _write_json(cycle_path, cycle)


def _run_expansion_clothing_exa() -> None:
    api_key = _compact(os.environ.get("EXA_API_KEY"))
    output_dir = _output_dir()
    input_root = _input_root()
    status: dict[str, Any] = {
        "schema_version": "unified-six-market-exa-runtime-1.0",
        "generated_at": _now(),
        "project_domain": CLOTHING_INVENTORY,
        "markets": {},
        **_safety(),
    }
    if not api_key:
        status["status"] = "SKIPPED_NO_EXA_API_KEY"
        _write_json(output_dir / "unified-six-market-exa-runtime.json", status)
        return

    runner = _runner_module()
    cycle_files = {
        "FR": "france-case-memory-v1.json",
        "IT": "italy-case-memory-v1.json",
        "NL": "netherlands-case-memory-v1.json",
    }
    for market in EXPANSION_EXA_MARKETS:
        source_dir = input_root / f"{market.casefold()}-exa-exact-lot"
        try:
            result = runner.run_market(
                market=market,
                exa_api_key=api_key,
                output_dir=source_dir,
                results_per_query=FABRIC_RESULTS_PER_MARKET,
            )
            paths = runner.write_discovery_artifacts(result, source_dir)
            unified_path = runner.write_unified_opportunity_report(
                result,
                source_dir,
                market_code=market,
                currency=runner.MARKET_CURRENCIES[market],
                domain=CLOTHING_INVENTORY,
            )
            paths["unified_opportunity_report"] = unified_path
            report = dict(result.get("search_run_report") or {})
            urls = _exact_urls(result)
            _merge_cycle_exact_truth(
                output_dir / cycle_files[market],
                market=market,
                report=report,
                urls=urls,
            )
            status["markets"][market] = {
                "status": report.get("status"),
                "hits_received": report.get("hits_received", 0),
                "strict_exact_lot_count": report.get("strict_exact_lot_count", 0),
                "exact_lot_urls": urls,
            }
        except Exception as exc:  # keep legacy market cycle available on retrieval errors
            status["markets"][market] = {
                "status": "FAILURE",
                "error_type": type(exc).__name__,
                "error": _compact(exc)[:500],
                "strict_exact_lot_count": 0,
                "exact_lot_urls": [],
            }
    status["status"] = "SUCCESS" if any(
        row.get("status") == "SUCCESS" for row in status["markets"].values()
    ) else "FAILURE"
    _write_json(output_dir / "unified-six-market-exa-runtime.json", status)


def _fabric_candidate(*, market: str, row: Mapping[str, Any]) -> dict[str, Any]:
    url = _compact(row.get("final_url") or row.get("url"))
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    title = _compact(row.get("title")) or host or "Verified fabric commercial page"
    candidate_id = "fabric-exa:" + sha256(f"{market}|{url}".encode("utf-8")).hexdigest()[:24]
    return {
        "candidate_id": candidate_id,
        "source_id": f"exa-market-{market.casefold()}",
        "source_name": host or "Exa verified fabric market route",
        "source_country": market,
        "source_kind": "EXA_VERIFIED_FABRIC_ROUTE",
        "location": None,
        "title": title[:1000],
        "description": title[:1000],
        "source_url": url,
        "observed_at": _now(),
        "fabric_terms": [],
        "bridal_terms": [],
        "value_terms": ["verified inventory", "verified trade or price"],
        "price_text": None,
        "price": None,
        "currency": "EUR",
        "quantity": None,
        "quantity_unit": None,
        "procurement_relevance_score": 75,
        "recommended_operator_action": "REVIEW_PRICE_QUANTITY_SAMPLE_AND_SHIPPING",
        "verification_status": "VERIFIED_COMMERCIAL_FABRIC_PAGE",
        "project_domain": FABRIC_PROCUREMENT,
        "not_a_clothing_inventory_opportunity": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        **_safety(),
    }


def _run_fabric_exa_search() -> dict[str, Any]:
    api_key = _compact(os.environ.get("EXA_API_KEY"))
    report: dict[str, Any] = {
        "schema_version": "unified-fabric-exa-search-1.0",
        "generated_at": _now(),
        "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
        "purpose": "UNIFIED_FABRIC_PROCUREMENT_SEARCH",
        "project_domain": FABRIC_PROCUREMENT,
        "provider": "exa",
        "market_coverage": list(FABRIC_MARKETS),
        "query_budget_total": len(FABRIC_MARKETS),
        "requests_made": 0,
        "candidate_count": 0,
        "candidates": [],
        "markets": [],
        **_safety(),
    }
    if not api_key:
        report["status"] = "SKIPPED_NO_EXA_API_KEY"
        report["status_counts"] = {"SKIPPED_NO_EXA_API_KEY": len(FABRIC_MARKETS)}
        return report

    provider = ExaSearchProvider(api_key)
    candidates: dict[str, dict[str, Any]] = {}
    statuses: list[str] = []
    for market in FABRIC_MARKETS:
        query = FABRIC_EXA_QUERIES[market]
        if classify_project_domain(text=query) != FABRIC_PROCUREMENT:
            raise RuntimeError(f"Fabric query escaped project domain: {market}: {query}")
        market_row: dict[str, Any] = {
            "market_code": market,
            "query": query,
            "provider": "exa",
            "hits_received": 0,
            "verified_page_count": 0,
            "accepted_candidate_count": 0,
            "rejection_reason_counts": {},
            "candidate_urls": [],
        }
        try:
            hits = list(provider.search(query, count=FABRIC_RESULTS_PER_MARKET))[
                :FABRIC_RESULTS_PER_MARKET
            ]
            report["requests_made"] += 1
            market_row["hits_received"] = len(hits)
            # Import the experiment verifier only when fabric execution actually
            # runs. Importing it at module load time creates a clean-interpreter
            # cycle through discovery.__init__ back into this hook.
            from opportunity_engine.search_experiment_execution_bridge_v1 import (
                _fabric_page_candidate,
            )
            from opportunity_engine.discovery.keyword_shadow_verification import fetch_public_page

            audit = [
                _fabric_page_candidate(hit, page_fetcher=fetch_public_page) for hit in hits
            ]
            market_row["verified_page_count"] = sum(
                item.get("fetch_ok") is True for item in audit
            )
            accepted = [
                item for item in audit if item.get("commercial_fabric_page") is True
            ]
            rejected = [
                item for item in audit if item.get("commercial_fabric_page") is not True
            ]
            for item in accepted:
                candidate = _fabric_candidate(market=market, row=item)
                candidates[candidate["source_url"]] = candidate
            reasons = Counter(
                _compact(item.get("rejection_reason")) or "UNDIAGNOSED"
                for item in rejected
            )
            market_row["accepted_candidate_count"] = len(accepted)
            market_row["rejection_reason_counts"] = dict(sorted(reasons.items()))
            market_row["candidate_urls"] = sorted(
                _compact(item.get("final_url") or item.get("url"))
                for item in accepted
                if _compact(item.get("final_url") or item.get("url"))
            )
            market_row["status"] = "SUCCESS" if accepted else "VALID_ZERO"
        except Exception as exc:
            report["requests_made"] += 1
            market_row["status"] = "FAILURE"
            market_row["error_type"] = type(exc).__name__
            market_row["error"] = _compact(exc)[:500]
        statuses.append(str(market_row["status"]))
        report["markets"].append(market_row)

    report["candidates"] = sorted(
        candidates.values(), key=lambda item: (item["source_country"], item["source_url"])
    )
    report["candidate_count"] = len(report["candidates"])
    report["status_counts"] = dict(sorted(Counter(statuses).items()))
    report["status"] = "SUCCESS" if any(
        status in {"SUCCESS", "VALID_ZERO"} for status in statuses
    ) else "FAILURE"
    return report


def _merge_fabric_report(output_dir: Path, exa_report: Mapping[str, Any]) -> dict[str, Any]:
    existing = _load_json(output_dir / FABRIC_FILENAME)
    merged = dict(existing) if existing else {}
    existing_candidates = [
        row for row in merged.get("candidates") or [] if isinstance(row, Mapping)
    ]
    exa_candidates = [
        row for row in exa_report.get("candidates") or [] if isinstance(row, Mapping)
    ]
    by_url: dict[str, dict[str, Any]] = {}
    for row in [*existing_candidates, *exa_candidates]:
        url = _compact(row.get("source_url") or row.get("url"))
        if url:
            by_url[url] = dict(row)
    merged.update(
        {
            "schema_version": "unified-fabric-procurement-runtime-1.0",
            "generated_at": _now(),
            "feed_family": "FABRIC_DEADSTOCK_PROCUREMENT_FEED_V1",
            "purpose": "UNIFIED_FABRIC_PROCUREMENT_INTELLIGENCE",
            "project_domain": FABRIC_PROCUREMENT,
            "market_coverage": list(FABRIC_MARKETS),
            "provider_modes": sorted(
                set(merged.get("provider_modes") or []) | {"exa", "legacy_official_watch"}
            ),
            "exa_market_search": dict(exa_report),
            "candidates": sorted(
                by_url.values(),
                key=lambda item: (
                    str(item.get("source_country") or ""),
                    str(item.get("source_url") or ""),
                ),
            ),
            "candidate_count": len(by_url),
            "not_part_of_clothing_top5": True,
            **_safety(),
        }
    )
    _write_json(output_dir / FABRIC_FILENAME, merged)
    return merged


def _clothing_runtime(input_root: Path) -> dict[str, Any]:
    markets: dict[str, Any] = {}
    for market in SIX_MARKETS:
        source_dir = input_root / f"{market.casefold()}-exa-exact-lot"
        report = _load_json(source_dir / "search-run-report.json")
        resolution = _load_json(source_dir / "exa-exact-lot-resolution.json")
        markets[market] = {
            "status": report.get("status") or "NOT_RUN",
            "provider": "exa",
            "hits_received": int(report.get("hits_received") or 0),
            "strict_exact_lot_count": int(report.get("strict_exact_lot_count") or 0),
            "exact_lot_urls": resolution.get("strict_exact_lot_urls") or [],
            "source_mode": report.get("source_mode"),
        }
    return {
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "market_coverage": list(SIX_MARKETS),
        "markets": markets,
        **_safety(),
    }


def _fabric_runtime(report: Mapping[str, Any]) -> dict[str, Any]:
    exa = report.get("exa_market_search") or {}
    market_rows = exa.get("markets") or [] if isinstance(exa, Mapping) else []
    by_market = {
        _compact(row.get("market_code")).upper(): dict(row)
        for row in market_rows
        if isinstance(row, Mapping)
    }
    return {
        "project_domain": FABRIC_PROCUREMENT,
        "provider": "exa",
        "market_coverage": list(FABRIC_MARKETS),
        "candidate_count": int(exa.get("candidate_count") or 0)
        if isinstance(exa, Mapping)
        else 0,
        "markets": {
            market: {
                "status": (by_market.get(market) or {}).get("status", "NOT_RUN"),
                "hits_received": int((by_market.get(market) or {}).get("hits_received") or 0),
                "verified_page_count": int(
                    (by_market.get(market) or {}).get("verified_page_count") or 0
                ),
                "candidate_count": int(
                    (by_market.get(market) or {}).get("accepted_candidate_count") or 0
                ),
                "candidate_urls": (by_market.get(market) or {}).get("candidate_urls") or [],
            }
            for market in FABRIC_MARKETS
        },
        **_safety(),
    }


def _append_unified_runtime(
    output_dir: Path,
    *,
    clothing: Mapping[str, Any],
    fabric: Mapping[str, Any],
) -> None:
    pipeline_path = output_dir / UNIFIED_PIPELINE_FILENAME
    ledger = _load_json(pipeline_path)
    if not ledger:
        return
    ledger["project_domains"] = [CLOTHING_INVENTORY, FABRIC_PROCUREMENT]
    ledger["search_runtime"] = {
        CLOTHING_INVENTORY: dict(clothing),
        FABRIC_PROCUREMENT: dict(fabric),
    }
    ledger["separated_country_search_paths"] = False
    ledger["fabric_is_first_class_project_domain"] = True
    ledger["fabric_mixed_into_clothing_top5"] = False
    ledger["unified_search_runtime_version"] = "UNIFIED_SEARCH_RUNTIME_V1"
    _write_json(pipeline_path, ledger)

    summary_path = output_dir / UNIFIED_PHONE_SUMMARY_FILENAME
    base = summary_path.read_text(encoding="utf-8").rstrip() if summary_path.exists() else ""
    lines = [base, "", "بحث Exa الموحد — CLOTHING_INVENTORY"]
    clothing_markets = clothing.get("markets") or {}
    for market in SIX_MARKETS:
        row = clothing_markets.get(market) or {}
        lines.append(
            f"{market}: {row.get('status')} | hits={row.get('hits_received', 0)} | "
            f"Exact-Lots={row.get('strict_exact_lot_count', 0)}"
        )
    lines.extend(["", "بحث Exa الموحد — FABRIC_PROCUREMENT"])
    fabric_markets = fabric.get("markets") or {}
    for market in FABRIC_MARKETS:
        row = fabric_markets.get(market) or {}
        lines.append(
            f"{market}: {row.get('status')} | hits={row.get('hits_received', 0)} | "
            f"verified={row.get('verified_page_count', 0)} | candidates={row.get('candidate_count', 0)}"
        )
    lines.extend(
        [
            "الأقمشة مجال مشروع مستقل داخل نفس التشغيل، ولا تختلط مع Top5 الملابس.",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    summary_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _finalize_daily_search_runtime() -> None:
    output_dir = _output_dir()
    input_root = _input_root()
    try:
        exa_fabric = _run_fabric_exa_search()
        merged_fabric = _merge_fabric_report(output_dir, exa_fabric)
        clothing = _clothing_runtime(input_root)
        fabric = _fabric_runtime(merged_fabric)
        _append_unified_runtime(output_dir, clothing=clothing, fabric=fabric)
        _write_json(
            output_dir / "unified-search-runtime-v1.json",
            {
                "schema_version": "unified-search-runtime-1.0",
                "generated_at": _now(),
                "project_domains": [CLOTHING_INVENTORY, FABRIC_PROCUREMENT],
                "clothing_inventory": clothing,
                "fabric_procurement": fabric,
                "separated_country_search_paths": False,
                **_safety(),
            },
        )
    except Exception as exc:
        _write_json(
            output_dir / "unified-search-runtime-v1.json",
            {
                "schema_version": "unified-search-runtime-1.0",
                "generated_at": _now(),
                "status": "FAILURE",
                "error_type": type(exc).__name__,
                "error": _compact(exc)[:1000],
                **_safety(),
            },
        )


def install_unified_search_runtime_cli_hook() -> bool:
    """Register only on the two established daily checkpoint CLIs."""
    global _INSTALLED
    if _INSTALLED:
        return False
    target = Path(sys.argv[0]).name
    if target == RUN_MULTI_CLI:
        atexit.register(_run_expansion_clothing_exa)
    elif target == DAILY_BULLETIN_CLI:
        # Installed after the unified river but before the older fabric hooks in
        # discovery.__init__. LIFO therefore lets the older fabric artifact land
        # first, then this callback merges Exa FR/IT/NL and rewrites the unified
        # operator view before the river consumes final fabric truth.
        atexit.register(_finalize_daily_search_runtime)
    else:
        return False
    _INSTALLED = True
    return True
