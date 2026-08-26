"""Bounded six-market coverage rotation for the existing unified fabric search.

The established Unified Search Runtime already treats FABRIC_PROCUREMENT as a
first-class project domain, but its live Exa fabric search is currently scheduled
for FR/IT/NL only. Expanding all six markets on every run would double the fabric
search budget from three Exa requests to six.

This compatibility layer keeps the existing budget exactly unchanged: three
fabric search requests per run and five results per request. It alternates two
three-market cohorts so two consecutive GitHub runs cover all six fixed markets.
No runtime, provider, source, country, project domain, qualification rule, page
fetch allowance, or automatic commercial action is added.
"""
from __future__ import annotations

import os
from typing import Any, Mapping

from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime
from opportunity_engine.discovery import unified_search_truth_reconciliation_cli_hook as reconciliation
from opportunity_engine.project_domain_boundary import FABRIC_PROCUREMENT, classify_project_domain


VERSION = "SIX_MARKET_FABRIC_COVERAGE_ROTATION_V1"
ROTATION_SEED_ENV = "SIX_MARKET_FABRIC_ROTATION_SEED"
FIXED_QUERY_BUDGET_PER_RUN = 3
FIXED_RESULTS_PER_QUERY = runtime.FABRIC_RESULTS_PER_MARKET
ALL_MARKETS = tuple(runtime.SIX_MARKETS)
COHORTS = (
    ("NO", "SE", "DE"),
    ("FR", "IT", "NL"),
)
FABRIC_EXA_QUERIES = {
    "NO": "Norge stoffgrossist stoffer metervare stoffruller restlager lager pris",
    "SE": "Sverige tyggrossist tyger metervara tygrullar restlager lager pris",
    "DE": "Deutschland Stoffgroßhandel Meterware Stoffballen Restposten Lager Preis",
    "FR": "France grossiste tissus tissu en gros rouleau de tissu stock déstockage prix",
    "IT": "Italia ingrosso tessuti tessuti a stock rotoli magazzino prezzo",
    "NL": "Nederland stoffen groothandel restpartij stofrollen voorraad prijs",
}
SEARCH_REQUESTS_ADDED_PER_RUN = 0
PAGE_RESULT_BUDGET_ADDED_PER_RUN = 0
_INSTALLED = False
_UPSTREAM_FABRIC_RUNNER = None
_UPSTREAM_FABRIC_RUNTIME = None


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _rotation_seed() -> int:
    raw = _compact(os.environ.get(ROTATION_SEED_ENV)) or _compact(
        os.environ.get("GITHUB_RUN_NUMBER")
    )
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def select_fabric_market_cohort(*, seed: int | None = None) -> tuple[str, ...]:
    """Return exactly three fixed markets; consecutive seeds alternate cohorts."""
    resolved_seed = _rotation_seed() if seed is None else max(0, int(seed))
    return COHORTS[resolved_seed % len(COHORTS)]


def _validate_contract() -> None:
    if set(ALL_MARKETS) != set(FABRIC_EXA_QUERIES):
        raise RuntimeError("six-market fabric query coverage does not match fixed markets")
    if any(len(cohort) != FIXED_QUERY_BUDGET_PER_RUN for cohort in COHORTS):
        raise RuntimeError("fabric rotation changed the fixed three-query budget")
    if set(COHORTS[0]) & set(COHORTS[1]):
        raise RuntimeError("fabric rotation cohorts must not overlap")
    if set(COHORTS[0]) | set(COHORTS[1]) != set(ALL_MARKETS):
        raise RuntimeError("fabric rotation cohorts must cover all six fixed markets")
    for market, query in FABRIC_EXA_QUERIES.items():
        if "site:" in query.casefold():
            raise RuntimeError(f"site-pinned fabric query is forbidden: {market}")
        if classify_project_domain(text=query) != FABRIC_PROCUREMENT:
            raise RuntimeError(f"fabric query escaped project domain: {market}")


def _run_fabric_exa_search_rotated() -> dict[str, Any]:
    upstream = _UPSTREAM_FABRIC_RUNNER
    if upstream is None:
        raise RuntimeError("upstream unified fabric runner is unavailable")
    report = dict(upstream())
    seed = _rotation_seed()
    scheduled = list(select_fabric_market_cohort(seed=seed))
    report.update(
        {
            "coverage_scheduler_version": VERSION,
            "all_market_coverage": list(ALL_MARKETS),
            "scheduled_market_coverage": scheduled,
            "rotation_seed": seed,
            "query_budget_total": FIXED_QUERY_BUDGET_PER_RUN,
            "query_budget_unchanged": True,
            "results_per_query": FIXED_RESULTS_PER_QUERY,
            "page_result_budget_unchanged": True,
            "search_requests_added_by_coverage_rotation": SEARCH_REQUESTS_ADDED_PER_RUN,
            "country_specific_search_paths_added": False,
            "new_runtime_added": False,
            "new_provider_added": False,
            "new_source_added": False,
        }
    )
    return report


def _fabric_runtime_with_rotation(report: Mapping[str, Any]) -> dict[str, Any]:
    upstream = _UPSTREAM_FABRIC_RUNTIME
    if upstream is None:
        raise RuntimeError("upstream fabric runtime projection is unavailable")
    projected = dict(upstream(report))
    exa = report.get("exa_market_search") or {}
    if not isinstance(exa, Mapping):
        exa = {}
    projected.update(
        {
            "all_market_coverage": list(ALL_MARKETS),
            "scheduled_market_coverage": list(
                exa.get("scheduled_market_coverage") or projected.get("market_coverage") or []
            ),
            "coverage_scheduler_version": exa.get("coverage_scheduler_version") or VERSION,
            "rotation_seed": int(exa.get("rotation_seed") or 0),
            "query_budget_total": FIXED_QUERY_BUDGET_PER_RUN,
            "query_budget_unchanged": True,
            "search_requests_added_by_coverage_rotation": SEARCH_REQUESTS_ADDED_PER_RUN,
        }
    )
    return projected


def _render_search_runtime_section_all_six(ledger: Mapping[str, Any]) -> str:
    search_runtime = ledger.get("search_runtime") or {}
    if not isinstance(search_runtime, Mapping):
        search_runtime = {}
    clothing = search_runtime.get("CLOTHING_INVENTORY") or {}
    fabric = search_runtime.get("FABRIC_PROCUREMENT") or {}
    if not isinstance(clothing, Mapping):
        clothing = {}
    if not isinstance(fabric, Mapping):
        fabric = {}

    clothing_markets = clothing.get("markets") or {}
    fabric_markets = fabric.get("markets") or {}
    if not isinstance(clothing_markets, Mapping):
        clothing_markets = {}
    if not isinstance(fabric_markets, Mapping):
        fabric_markets = {}
    scheduled = {
        _compact(code).upper()
        for code in fabric.get("scheduled_market_coverage") or fabric.get("market_coverage") or []
        if _compact(code)
    }

    lines = ["", "حقيقة البحث الموحد"]
    for code in ALL_MARKETS:
        row = clothing_markets.get(code) or {}
        if not isinstance(row, Mapping):
            row = {}
        lines.append(
            f"{code} ملابس: {row.get('status', 'NOT_RUN')} | "
            f"hits={row.get('hits_received', 0)} | Exact-Lots={row.get('strict_exact_lot_count', 0)}"
        )
    for code in ALL_MARKETS:
        row = fabric_markets.get(code) or {}
        if not isinstance(row, Mapping):
            row = {}
        lines.append(
            f"{code} أقمشة: {row.get('status', 'NOT_RUN')} | "
            f"hits={row.get('hits_received', 0)} | candidates={row.get('candidate_count', 0)} | "
            f"scheduled={str(code in scheduled).lower()}"
        )
    lines.extend(
        [
            f"تغطية الأقمشة: {VERSION} | 3/6 أسواق في كل تشغيل، بلا زيادة في طلبات البحث.",
            "تطوير البحث: نفس المسار الموحد فقط؛ لا مسارات دول منفصلة.",
            "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
        ]
    )
    return "\n".join(lines) + "\n"


def install_six_market_fabric_coverage_rotation_v1() -> bool:
    """Extend only scheduling/visibility of the existing unified fabric runtime."""
    global _INSTALLED, _UPSTREAM_FABRIC_RUNNER, _UPSTREAM_FABRIC_RUNTIME
    if _INSTALLED:
        return False

    _validate_contract()
    _UPSTREAM_FABRIC_RUNNER = runtime._run_fabric_exa_search
    _UPSTREAM_FABRIC_RUNTIME = runtime._fabric_runtime

    scheduled = select_fabric_market_cohort()
    runtime.FABRIC_MARKETS = scheduled
    runtime.FABRIC_EXA_QUERIES = dict(FABRIC_EXA_QUERIES)
    runtime._run_fabric_exa_search = _run_fabric_exa_search_rotated
    runtime._fabric_runtime = _fabric_runtime_with_rotation
    reconciliation._render_search_runtime_section = _render_search_runtime_section_all_six

    _INSTALLED = True
    return True
