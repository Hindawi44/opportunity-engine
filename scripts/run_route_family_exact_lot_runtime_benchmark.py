from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import unquote

from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "artifacts/route-family-exact-lot-runtime-benchmark"))
RESULTS_PER_QUERY = 20
MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")

ROUTE_FAMILY_CLOTHING_QUERIES = {
    "NO": (
        "Norge klær vareparti nettauksjon konkursbo lager pris antall stk",
        "Norge restlager klær grossist restparti overskuddslager pris antall",
    ),
    "SE": (
        "Sverige kläder konkursauktion varulager parti pris antal",
        "Sverige restparti kläder grossist överskottslager parti pris antal",
    ),
    "DE": (
        "Deutschland Bekleidung Insolvenz Auktion Warenlager Posten Preis Stück",
        "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück",
    ),
    "FR": (
        "France vêtements liquidation judiciaire enchères stock lot prix quantité",
        "France vêtements déstockage grossiste lot stock prix quantité",
    ),
    "IT": (
        "Italia abbigliamento liquidazione giudiziale asta stock lotto prezzo quantità pezzi",
        "Italia abbigliamento stock fallimento ingrosso lotto prezzo quantità",
    ),
    "NL": (
        "Nederland kleding faillissementsveiling voorraad partij prijs aantal stuks",
        "Nederland kleding restpartij partijhandel groothandel prijs aantal stuks",
    ),
}

# Clothing-only subset of the independently confirmed scoring set. It is never
# used to construct the route-family queries above.
GOLD = (
    {"id": "NO_AUKSJONEN_BLAKLADER_22", "market": "NO", "needles": ("blåkläder", "22 stk")},
    {"id": "NO_AUKSJONEN_BOSCH_32", "market": "NO", "needles": ("bosch car service", "32 stk")},
    {"id": "NO_AUKSJONEN_BJORNKLADER_12", "market": "NO", "needles": ("björnkläder", "12 stk")},
    {"id": "SE_BUDI_MC_170", "market": "SE", "needles": ("mc-intresserade", "170 plagg")},
    {"id": "DE_RESTPOSTEN24_SWEAT_2000", "market": "DE", "needles": ("damen-stocksweatshirts", "2000")},
    {"id": "FR_INTERENCHERES_LINGERIE_144", "market": "FR", "needles": ("stock de lingerie", "144 lots")},
    {"id": "NL_PARTIJ_BADKLEDING_500", "market": "NL", "needles": ("500 stuks", "badkleding")},
    {"id": "NL_PARTIJ_TEENSLIPPERS_4575", "market": "NL", "needles": ("4575", "teenslippers")},
)


def _runner_module():
    path = Path(__file__).resolve().parent / "run_exa_exact_lot_checkpoint.py"
    spec = importlib.util.spec_from_file_location("route_family_runtime_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load exact-lot runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _norm(value: object) -> str:
    return " ".join(unquote(str(value or "")).casefold().replace(".", " ").split())


def _candidate_text(candidate: dict) -> str:
    parts = [candidate.get("title"), candidate.get("opportunity_identity")]
    parts.extend(candidate.get("source_urls") or [])
    parts.extend(candidate.get("canonical_urls") or [])
    return _norm(" ".join(str(part or "") for part in parts))


def _score(all_candidates: list[dict]) -> dict:
    matches = []
    for anchor in GOLD:
        found = None
        for candidate in all_candidates:
            if candidate.get("market_code") != anchor["market"]:
                continue
            text = _candidate_text(candidate)
            if all(_norm(needle) in text for needle in anchor["needles"]):
                found = candidate
                break
        matches.append({
            "id": anchor["id"],
            "market": anchor["market"],
            "matched": found is not None,
            "matched_url": found.get("opportunity_identity") if found else None,
            "matched_title": found.get("title") if found else None,
        })
    matched = sum(item["matched"] for item in matches)
    return {
        "gold_count": len(matches),
        "matched_count": matched,
        "recall": round(matched / len(matches), 4),
        "matches": matches,
    }


def main() -> int:
    api_key = str(os.environ.get("EXA_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("EXA_API_KEY is required")

    runner = _runner_module()
    runner.MARKET_EXACT_LOT_QUERY_PACKS = dict(ROUTE_FAMILY_CLOTHING_QUERIES)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    market_reports = {}
    all_candidates = []
    total_queries = 0
    total_hits = 0
    total_exact = 0

    for market in MARKETS:
        market_dir = OUTPUT_DIR / market.casefold()
        result = runner.run_market(
            market=market,
            exa_api_key=api_key,
            output_dir=market_dir,
            results_per_query=RESULTS_PER_QUERY,
        )
        report = dict(result.get("search_run_report") or {})
        candidates = [dict(row) for row in result.get("all_discovered_candidates") or []]
        for candidate in candidates:
            candidate["market_code"] = market
        all_candidates.extend(candidates)
        total_queries += int(report.get("queries_submitted") or 0)
        total_hits += int(report.get("hits_received") or 0)
        total_exact += int(report.get("strict_exact_lot_count") or 0)
        market_reports[market] = {
            "status": report.get("status"),
            "queries_submitted": report.get("queries_submitted"),
            "hits_received": report.get("hits_received"),
            "primary_strict_exact_lot_count": report.get("primary_strict_exact_lot_count"),
            "strict_exact_lot_count": report.get("strict_exact_lot_count"),
            "direct_exact_lot_count": report.get("direct_exact_lot_count"),
            "multihop_exact_lot_count": report.get("multihop_exact_lot_count"),
            "fresh_current_exact_lot_count": report.get("final_fresh_current_strict_exact_lot_count"),
            "fresh_route_host_count": report.get("final_fresh_current_route_host_count"),
            "zero_yield_recall_triggered": report.get("zero_yield_recall_triggered"),
            "commercial_anchor_expansion_triggered": report.get("commercial_anchor_expansion_triggered"),
            "exact_lot_urls": [candidate.get("opportunity_identity") for candidate in candidates],
        }
        runner.write_discovery_artifacts(result, market_dir)

    score = _score(all_candidates)
    payload = {
        "schema_version": "route-family-exact-lot-runtime-benchmark-1.0",
        "project_domain": CLOTHING_INVENTORY,
        "provider": "exa",
        "production_mutation": False,
        "source_specific_queries": False,
        "gold_used_for_query_generation": False,
        "results_per_query": RESULTS_PER_QUERY,
        "markets": market_reports,
        "total_queries_submitted": total_queries,
        "total_hits_received": total_hits,
        "total_strict_exact_lots": total_exact,
        "score": score,
        "gold": list(GOLD),
    }
    (OUTPUT_DIR / "route-family-exact-lot-runtime-benchmark.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "ROUTE-FAMILY EXACT-LOT RUNTIME BENCHMARK V1",
        f"provider: Exa | results/query: {RESULTS_PER_QUERY}",
        f"queries submitted: {total_queries}",
        f"strict Exact-Lots: {total_exact}",
        f"Gold clothing recall after Verification -> Multi-Hop -> Exact-Lot: {score['matched_count']}/{score['gold_count']} = {score['recall']:.1%}",
        "",
    ]
    for market in MARKETS:
        row = market_reports[market]
        lines.append(
            f"{market}: exact={row['strict_exact_lot_count']} | primary={row['primary_strict_exact_lot_count']} | "
            f"fresh={row['fresh_current_exact_lot_count']} | hosts={row['fresh_route_host_count']} | queries={row['queries_submitted']}"
        )
    lines.extend(["", "MATCHES"])
    found = [item["id"] for item in score["matches"] if item["matched"]]
    lines.append(", ".join(found) if found else "NONE")
    lines.extend(["", "Gold anchors are scoring-only and never contribute qualification evidence."])
    summary = "\n".join(lines) + "\n"
    (OUTPUT_DIR / "route-family-exact-lot-runtime-benchmark.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
