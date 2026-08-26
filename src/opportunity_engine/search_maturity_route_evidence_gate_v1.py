"""Search Maturity Gate V1: read existing search evidence only.

The gate does not search, fetch pages, mutate production queries, or create a
second runtime. It reconciles already-produced CLOTHING_INVENTORY and
FABRIC_PROCUREMENT artifacts across the fixed six markets and returns one
explicit maturity decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


SIX_MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
CORE_MARKETS = ("NO", "SE", "DE")
EXPANSION_MARKETS = ("FR", "IT", "NL")
EXPECTED_FABRIC_COHORTS = {frozenset(CORE_MARKETS), frozenset(EXPANSION_MARKETS)}
_AUTOMATIC_SAFETY_KEYS = (
    "production_mutation",
    "automatic_query_activation",
    "automatic_provider_activation",
    "automatic_source_promotion",
    "automatic_contact",
    "automatic_bid",
    "automatic_reservation",
    "automatic_purchase",
    "automatic_payment",
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _positive_number(value: object) -> bool:
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _safety_ok(payload: Mapping[str, Any]) -> bool:
    for key in _AUTOMATIC_SAFETY_KEYS:
        if key in payload and payload.get(key) is not False:
            return False
    return True


def _fabric_candidates(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = report.get("candidates") or []
    return [row for row in rows if isinstance(row, Mapping)]


def _contextual_pair_ok(candidate: Mapping[str, Any]) -> bool:
    return (
        candidate.get("commercial_evidence_complete") is True
        and candidate.get("commercial_evidence_normalized") is True
        and candidate.get("commercial_evidence_pairing_mode")
        == "CONTEXTUAL_PRICE_QUANTITY_PAIR"
        and _positive_number(candidate.get("price"))
        and _positive_number(candidate.get("quantity"))
    )


def _fabric_runtime(report: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = report.get("exa_market_search")
    return nested if isinstance(nested, Mapping) else report


def _fabric_coverage(report: Mapping[str, Any]) -> tuple[str, ...]:
    runtime = _fabric_runtime(report)
    raw = (
        report.get("scheduled_market_coverage")
        or report.get("market_coverage")
        or runtime.get("scheduled_market_coverage")
        or runtime.get("market_coverage")
        or []
    )
    return tuple(str(market).upper() for market in raw)


def _fabric_report_assessment(report: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _fabric_runtime(report)
    coverage = _fabric_coverage(report)
    markets = [row for row in runtime.get("markets") or [] if isinstance(row, Mapping)]
    market_by_code = {str(row.get("market_code") or "").upper(): row for row in markets}
    candidates = _fabric_candidates(report)
    contextual_markets = sorted(
        {
            str(row.get("source_country") or "").upper()
            for row in candidates
            if _contextual_pair_ok(row)
        }
    )

    blockers: list[str] = []
    if frozenset(coverage) not in EXPECTED_FABRIC_COHORTS or len(coverage) != 3:
        blockers.append("FABRIC_COHORT_NOT_FIXED_THREE_MARKET_SET")
    if report.get("project_domain") != "FABRIC_PROCUREMENT":
        blockers.append("FABRIC_DOMAIN_CHANGED")
    if runtime.get("provider") not in {None, "exa"}:
        blockers.append("FABRIC_PROVIDER_CHANGED")
    if int(report.get("query_budget_total") or runtime.get("query_budget_total") or 0) != 3:
        blockers.append("FABRIC_QUERY_BUDGET_CHANGED")
    if int(report.get("requests_made") or runtime.get("requests_made") or 0) != 3:
        blockers.append("FABRIC_REQUEST_COUNT_CHANGED")
    if report.get("site_pinning_used") is not False:
        blockers.append("SITE_PINNING_PRESENT")
    if int(report.get("legacy_search_requests_made") or 0) != 0:
        blockers.append("LEGACY_SEARCH_REQUESTS_PRESENT")
    if int(report.get("search_requests_added_by_coverage_rotation") or runtime.get("search_requests_added_by_coverage_rotation") or 0) != 0:
        blockers.append("COVERAGE_ROTATION_ADDED_SEARCH_REQUESTS")
    for key in (
        "new_runtime_added",
        "new_provider_added",
        "new_source_added",
        "country_specific_search_paths_added",
    ):
        value = report.get(key)
        if value is None:
            value = runtime.get(key)
        if value is True:
            blockers.append(f"{key.upper()}_TRUE")
    if not _safety_ok(report) or not _safety_ok(runtime):
        blockers.append("FABRIC_AUTOMATIC_SAFETY_CHANGED")

    for market in coverage:
        row = market_by_code.get(market)
        if not row or str(row.get("status") or "").upper() != "SUCCESS":
            blockers.append(f"FABRIC_{market}_NOT_SUCCESS")
        elif int(row.get("accepted_candidate_count") or 0) < 1:
            blockers.append(f"FABRIC_{market}_NO_VERIFIED_COMMERCIAL_PAGE")

    if not set(contextual_markets).intersection(coverage):
        blockers.append("FABRIC_COHORT_HAS_NO_CONTEXTUAL_PRICE_QUANTITY_PROOF")

    return {
        "coverage": list(coverage),
        "contextual_pair_markets": contextual_markets,
        "candidate_count": len(candidates),
        "requests_made": int(report.get("requests_made") or runtime.get("requests_made") or 0),
        "query_budget_total": int(report.get("query_budget_total") or runtime.get("query_budget_total") or 0),
        "site_pinning_used": report.get("site_pinning_used"),
        "legacy_search_requests_made": int(report.get("legacy_search_requests_made") or 0),
        "blockers": blockers,
        "passed": not blockers,
    }


def _molton_primary_product_proof(reports: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    observed: list[dict[str, Any]] = []
    passed = False
    for report in reports:
        for row in _fabric_candidates(report):
            url = str(row.get("source_url") or "")
            host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
            source_name = str(row.get("source_name") or "").casefold()
            if host != "molton-markt.de" and source_name != "molton-markt.de":
                continue
            quantity = row.get("quantity")
            unit = str(row.get("quantity_unit") or "").casefold()
            price = row.get("price")
            primary_roll = (
                _contextual_pair_ok(row)
                and abs(float(quantity or 0) - 30.0) < 1e-9
                and unit in {"lfm", "laufmeter", "meter", "metre", "m"}
                and float(price or 0) >= 100.0
            )
            passed = passed or primary_roll
            observed.append(
                {
                    "title": row.get("title"),
                    "source_url": url,
                    "price": price,
                    "price_text": row.get("price_text"),
                    "quantity": quantity,
                    "quantity_unit": row.get("quantity_unit"),
                    "pairing_mode": row.get("commercial_evidence_pairing_mode"),
                    "primary_roll_evidence": primary_roll,
                }
            )
    return {
        "status": "PROVEN" if passed else ("FAILED" if observed else "NOT_OBSERVED"),
        "passed": passed,
        "observed": observed,
    }


def evaluate_search_maturity(
    *,
    input_root: Path,
    output_dir: Path,
    prior_fabric_reports: Iterable[Path] = (),
) -> dict[str, Any]:
    blockers: list[str] = []
    clothing: dict[str, Any] = {}

    for market in CORE_MARKETS:
        report = _load_json(input_root / f"{market.casefold()}-exa-exact-lot" / "search-run-report.json")
        strict_count = int(report.get("strict_exact_lot_count") or 0)
        passed = (
            report.get("status") == "SUCCESS"
            and report.get("execution_status") == "PASS"
            and report.get("domain") == "CLOTHING_INVENTORY"
            and report.get("source_mode") == "EXA_EXACT_LOT_MULTIHOP"
            and strict_count > 0
            and _safety_ok(report)
        )
        clothing[market] = {"strict_exact_lot_count": strict_count, "passed": passed}
        if not passed:
            blockers.append(f"CLOTHING_{market}_STRICT_EXACT_LOT_NOT_PROVEN")

    expansion = _load_json(output_dir / "unified-six-market-exa-runtime.json")
    if expansion.get("status") != "SUCCESS" or expansion.get("project_domain") != "CLOTHING_INVENTORY":
        blockers.append("CLOTHING_EXPANSION_RUNTIME_NOT_SUCCESS")
    if not _safety_ok(expansion):
        blockers.append("CLOTHING_EXPANSION_AUTOMATIC_SAFETY_CHANGED")
    if int(expansion.get("search_requests_added_by_route_continuity") or 0) != 0:
        blockers.append("ROUTE_CONTINUITY_ADDED_SEARCH_REQUESTS")
    expansion_markets = expansion.get("markets") or {}
    for market in EXPANSION_MARKETS:
        row = expansion_markets.get(market) if isinstance(expansion_markets, Mapping) else None
        row = row if isinstance(row, Mapping) else {}
        strict_count = int(row.get("strict_exact_lot_count") or 0)
        passed = row.get("status") == "SUCCESS" and strict_count > 0
        clothing[market] = {"strict_exact_lot_count": strict_count, "passed": passed}
        if not passed:
            blockers.append(f"CLOTHING_{market}_STRICT_EXACT_LOT_NOT_PROVEN")

    fabric_paths = [*prior_fabric_reports, output_dir / "fabric-procurement-watch.json"]
    fabric_reports = [_load_json(path) for path in fabric_paths]
    fabric_assessments = [_fabric_report_assessment(report) for report in fabric_reports]
    for assessment in fabric_assessments:
        blockers.extend(assessment["blockers"])

    covered_fabric_markets = sorted(
        {market for assessment in fabric_assessments for market in assessment["coverage"]}
    )
    seen_cohorts = {frozenset(assessment["coverage"]) for assessment in fabric_assessments}
    if set(covered_fabric_markets) != set(SIX_MARKETS):
        blockers.append("FABRIC_SIX_MARKET_COVERAGE_NOT_PROVEN")
    if not EXPECTED_FABRIC_COHORTS.issubset(seen_cohorts):
        blockers.append("FABRIC_BOTH_FIXED_COHORTS_NOT_PROVEN")

    molton = _molton_primary_product_proof(fabric_reports)
    if not molton["passed"]:
        blockers.append("MOLTON_PRIMARY_PRODUCT_EVIDENCE_NOT_PROVEN")

    blockers = sorted(set(blockers))
    mature = not blockers
    return {
        "schema_version": "search-maturity-route-evidence-gate-1.0",
        "decision": "MATURE" if mature else "BLOCKED",
        "search_engine_v1_mature": mature,
        "project_domains": ["CLOTHING_INVENTORY", "FABRIC_PROCUREMENT"],
        "fixed_markets": list(SIX_MARKETS),
        "clothing": clothing,
        "fabric": {
            "covered_markets": covered_fabric_markets,
            "reports": fabric_assessments,
            "molton_primary_product_proof": molton,
        },
        "blocking_reasons": blockers,
        "gate_search_requests_made": 0,
        "gate_page_fetches_made": 0,
        "new_runtime_added": False,
        "new_agent_added": False,
        "site_pinning_added": False,
        "exact_lot_relaxed": False,
        "production_mutation": False,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Search Engine V1 maturity from existing artifacts only")
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prior-fabric-report", type=Path, action="append", default=[])
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    result = evaluate_search_maturity(
        input_root=args.input_root,
        output_dir=args.output_dir,
        prior_fabric_reports=args.prior_fabric_report,
    )
    if args.json_output:
        _write_json(args.json_output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["search_engine_v1_mature"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
