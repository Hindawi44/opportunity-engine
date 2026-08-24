"""Reconcile operator stage labels with the already-unified live search runtime.

This is a reporting/truth guard, not a new search path. It runs after
UNIFIED_SEARCH_RUNTIME_V1 has written the six-market clothing and fabric search
facts, then updates stale legacy stage labels without hiding source failures.

Search development stays on one runtime path. No country-specific bypass,
source promotion, contact, bid, reservation, purchase, or payment is enabled.
"""
from __future__ import annotations

import atexit
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from opportunity_engine.discovery.unified_six_market_runtime_cli_hook import (
    render_unified_phone_summary,
)
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
)


_TARGET_CLI = "build_domain_market_intelligence_feed.py"
_PIPELINE_FILENAME = "unified-six-market-pipeline-v1.json"
_SUMMARY_FILENAME = "unified-six-market-phone-summary-v1.txt"
_RUNTIME_FILENAME = "unified-search-runtime-v1.json"
_AUDIT_FILENAME = "unified-search-truth-reconciliation-v1.json"
_INSTALLED = False


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


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


def _stage_index(market: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _compact(stage.get("stage")): stage
        for stage in market.get("stages") or []
        if isinstance(stage, dict) and _compact(stage.get("stage"))
    }


def _source_failure_count(discovery: Mapping[str, Any]) -> int:
    counts = discovery.get("source_execution_counts") or {}
    if not isinstance(counts, Mapping):
        return 0
    return _int(counts.get("FAILURE")) + _int(counts.get("FAILED"))


def _search_development_contract() -> dict[str, Any]:
    return {
        "mode": "ONE_UNIFIED_SEARCH_RUNTIME",
        "project_domains": [CLOTHING_INVENTORY, FABRIC_PROCUREMENT],
        "country_specific_search_paths_allowed": False,
        "search_development_must_reuse_unified_runtime": True,
        "new_agent_required": False,
        "new_source_required": False,
        "development_axes": [
            "QUERY_QUALITY",
            "RETRIEVAL_RECALL",
            "DIRECT_PAGE_VERIFICATION",
            "MULTI_HOP_RESOLUTION",
            "COMMERCIAL_VALUE_EXTRACTION",
            "LEARNING_FEEDBACK",
        ],
    }


def reconcile_unified_search_truth(
    ledger: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply live search truth to stale stage labels without erasing failures."""
    reconciled = deepcopy(dict(ledger))
    runtime = reconciled.get("search_runtime") or {}
    if not isinstance(runtime, Mapping):
        runtime = {}
    clothing = runtime.get(CLOTHING_INVENTORY) or {}
    if not isinstance(clothing, Mapping):
        clothing = {}
    search_markets = clothing.get("markets") or {}
    if not isinstance(search_markets, Mapping):
        search_markets = {}

    changes: list[dict[str, Any]] = []
    markets = reconciled.get("markets") or []
    if not isinstance(markets, list):
        markets = []

    for market in markets:
        if not isinstance(market, dict):
            continue
        code = _compact(market.get("market_code")).upper()
        search = search_markets.get(code) or {}
        if not isinstance(search, Mapping):
            continue
        search_status = _compact(search.get("status")).upper()
        if search_status != "SUCCESS":
            continue

        hits = _int(search.get("hits_received"))
        exa_exact = _int(search.get("strict_exact_lot_count"))
        stages = _stage_index(market)
        discovery = stages.get("DISCOVERY")
        exact_stage = stages.get("EXACT_LOT_VERIFICATION")
        qualification = stages.get("COMMERCIAL_QUALIFICATION")
        evidence = stages.get("EVIDENCE")
        decision = stages.get("OPPORTUNITY_DECISION")
        if not discovery or not exact_stage or not qualification or not decision:
            continue

        existing_exact = _int(exact_stage.get("verified_active_exact_lot_count"))
        effective_exact = max(existing_exact, exa_exact)
        source_failures = _source_failure_count(discovery)

        market_changes: dict[str, Any] = {
            "market_code": code,
            "search_status": search_status,
            "hits_received": hits,
            "exa_exact_lot_count": exa_exact,
            "effective_exact_lot_count": effective_exact,
            "source_failure_count_preserved": source_failures,
            "stage_changes": [],
        }

        old_discovery = _compact(discovery.get("status")).upper() or "UNKNOWN"
        if effective_exact > 0:
            new_discovery = "SUCCESS"
        elif hits > 0 and old_discovery == "FAILURE":
            new_discovery = "PARTIAL"
        else:
            new_discovery = old_discovery
        if new_discovery != old_discovery:
            market_changes["stage_changes"].append(
                {"stage": "DISCOVERY", "from": old_discovery, "to": new_discovery}
            )
            discovery["legacy_status_before_search_truth"] = old_discovery
            discovery["status"] = new_discovery
        discovery["unified_search_status"] = search_status
        discovery["unified_search_hits"] = hits
        discovery["verified_exact_lot_count"] = effective_exact
        discovery["source_failures_preserved"] = source_failures > 0
        discovery["partial_source_failure_count"] = source_failures

        old_exact = _compact(exact_stage.get("status")).upper() or "UNKNOWN"
        new_exact = "SUCCESS" if effective_exact > 0 else "VALID_ZERO"
        if new_exact != old_exact:
            market_changes["stage_changes"].append(
                {"stage": "EXACT_LOT_VERIFICATION", "from": old_exact, "to": new_exact}
            )
            exact_stage["legacy_status_before_search_truth"] = old_exact
            exact_stage["status"] = new_exact
        exact_stage["verified_active_exact_lot_count"] = effective_exact
        exact_stage["exa_verified_exact_lot_count"] = exa_exact
        exact_stage["capability_implemented"] = True
        exact_stage["engine_version"] = "UNIFIED_EXA_EXACT_LOT_MULTIHOP_V1"

        qualification_count = _int(qualification.get("qualification_count"))
        financial_ready = _int(qualification.get("financial_decision_ready_count"))
        old_qualification = _compact(qualification.get("status")).upper() or "UNKNOWN"
        if effective_exact > 0 and not financial_ready and not qualification_count:
            new_qualification = "REQUIRES_VERIFICATION"
        elif effective_exact == 0 and old_qualification in {
            "NOT_IMPLEMENTED",
            "BLOCKED_BY_EXACT_LOT",
        }:
            new_qualification = "NOT_READY"
        else:
            new_qualification = old_qualification
        if new_qualification != old_qualification:
            market_changes["stage_changes"].append(
                {
                    "stage": "COMMERCIAL_QUALIFICATION",
                    "from": old_qualification,
                    "to": new_qualification,
                }
            )
            qualification["legacy_status_before_search_truth"] = old_qualification
            qualification["status"] = new_qualification
        if effective_exact > 0 and not financial_ready:
            qualification["commercial_value_extraction_required"] = True
            qualification["verified_exact_lot_count"] = effective_exact

        if evidence is not None and effective_exact > 0:
            old_evidence = _compact(evidence.get("status")).upper() or "UNKNOWN"
            if old_evidence in {
                "NOT_READY",
                "BLOCKED_BY_COMMERCIAL_QUALIFICATION",
                "BLOCKED_BY_EXACT_LOT",
            }:
                evidence["legacy_status_before_search_truth"] = old_evidence
                evidence["status"] = "REQUIRES_EVIDENCE"
                market_changes["stage_changes"].append(
                    {"stage": "EVIDENCE", "from": old_evidence, "to": "REQUIRES_EVIDENCE"}
                )

        old_decision = _compact(decision.get("status")).upper() or "UNKNOWN"
        if effective_exact > 0 and not financial_ready and old_decision not in {
            "CANDIDATE_AVAILABLE",
            "READY_FOR_HUMAN_DECISION",
        }:
            new_decision = "CANDIDATE_AVAILABLE_REQUIRES_VERIFICATION"
        else:
            new_decision = old_decision
        if new_decision != old_decision:
            market_changes["stage_changes"].append(
                {"stage": "OPPORTUNITY_DECISION", "from": old_decision, "to": new_decision}
            )
            decision["legacy_status_before_search_truth"] = old_decision
            decision["status"] = new_decision
        decision["verified_exact_lot_count"] = effective_exact

        market["search_truth_reconciled"] = True
        market["unified_search_provider"] = "exa"
        market["country_specific_search_path"] = False
        changes.append(market_changes)

    reconciled["search_truth_reconciled"] = True
    reconciled["search_truth_authority"] = "UNIFIED_SEARCH_RUNTIME_V1"
    reconciled["separated_country_search_paths"] = False
    reconciled["search_development_contract"] = _search_development_contract()
    audit = {
        "schema_version": "unified-search-truth-reconciliation-1.0",
        "status": "SUCCESS",
        "search_truth_authority": "UNIFIED_SEARCH_RUNTIME_V1",
        "market_change_count": len(changes),
        "markets": changes,
        "search_development_contract": _search_development_contract(),
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    return reconciled, audit


def _render_search_runtime_section(ledger: Mapping[str, Any]) -> str:
    runtime = ledger.get("search_runtime") or {}
    clothing = runtime.get(CLOTHING_INVENTORY) or {} if isinstance(runtime, Mapping) else {}
    fabric = runtime.get(FABRIC_PROCUREMENT) or {} if isinstance(runtime, Mapping) else {}
    lines = ["", "حقيقة البحث الموحد"]
    clothing_markets = clothing.get("markets") or {} if isinstance(clothing, Mapping) else {}
    for code in ("NO", "SE", "DE", "FR", "IT", "NL"):
        row = clothing_markets.get(code) or {} if isinstance(clothing_markets, Mapping) else {}
        lines.append(
            f"{code} ملابس: {row.get('status', 'NOT_RUN')} | "
            f"hits={row.get('hits_received', 0)} | Exact-Lots={row.get('strict_exact_lot_count', 0)}"
        )
    fabric_markets = fabric.get("markets") or {} if isinstance(fabric, Mapping) else {}
    for code in ("FR", "IT", "NL"):
        row = fabric_markets.get(code) or {} if isinstance(fabric_markets, Mapping) else {}
        lines.append(
            f"{code} أقمشة: {row.get('status', 'NOT_RUN')} | "
            f"hits={row.get('hits_received', 0)} | candidates={row.get('candidate_count', 0)}"
        )
    lines.extend(
        [
            "تطوير البحث: نفس المسار الموحد فقط؛ لا مسارات دول منفصلة.",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def reconcile_runtime_artifacts(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir)
    pipeline_path = root / _PIPELINE_FILENAME
    runtime_path = root / _RUNTIME_FILENAME
    ledger = _load_json(pipeline_path)
    runtime = _load_json(runtime_path)
    if not ledger or not runtime:
        raise ValueError("Unified pipeline and unified search runtime are required")
    if not isinstance(ledger.get("search_runtime"), Mapping):
        raise ValueError("Unified pipeline is missing search_runtime truth")

    reconciled, audit = reconcile_unified_search_truth(ledger)
    _write_json(pipeline_path, reconciled)
    _write_json(root / _AUDIT_FILENAME, audit)

    runtime["report_truth_reconciled"] = True
    runtime["search_development_contract"] = _search_development_contract()
    runtime["separated_country_search_paths"] = False
    _write_json(runtime_path, runtime)

    summary_path = root / _SUMMARY_FILENAME
    summary_path.write_text(
        render_unified_phone_summary(reconciled).rstrip()
        + "\n"
        + _render_search_runtime_section(reconciled),
        encoding="utf-8",
    )
    return {
        "pipeline": pipeline_path,
        "runtime": runtime_path,
        "summary": summary_path,
        "audit": root / _AUDIT_FILENAME,
    }


def _output_dir_from_argv(argv: list[str]) -> Path:
    for index, value in enumerate(argv):
        if value == "--output-dir" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if value.startswith("--output-dir="):
            return Path(value.split("=", 1)[1])
    return Path("artifacts/multi-market-daily-operator-checkpoint")


def _reconcile_after_unified_search() -> None:
    root = _output_dir_from_argv(sys.argv)
    if not (root / _PIPELINE_FILENAME).exists() or not (root / _RUNTIME_FILENAME).exists():
        return
    paths = reconcile_runtime_artifacts(root)
    print(f"unified_search_truth_reconciliation: {paths['audit']}")


def install_unified_search_truth_reconciliation_cli_hook() -> bool:
    """Register before Unified Search Runtime so LIFO executes this after it."""
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != _TARGET_CLI:
        return False
    atexit.register(_reconcile_after_unified_search)
    _INSTALLED = True
    return True
