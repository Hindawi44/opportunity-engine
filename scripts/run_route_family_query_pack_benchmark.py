from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.exa_search import ExaSearchProvider

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "artifacts/route-family-query-pack-benchmark"))
RESULTS_PER_QUERY = 20

# Two generic commercial route families per market/domain. No source, seller,
# brand, Gold-Set title or URL is present in query construction.
QUERY_PACK = (
    ("NO", "CLOTHING_INVENTORY", "AUCTION_LIQUIDATION", "Norge klær vareparti nettauksjon konkursbo lager pris antall stk"),
    ("NO", "CLOTHING_INVENTORY", "WHOLESALE_STOCK", "Norge restlager klær grossist restparti overskuddslager pris antall"),
    ("NO", "FABRIC_PROCUREMENT", "AUCTION_LIQUIDATION", "Norge stoff tekstil konkursbo auksjon lager ruller pris antall"),
    ("NO", "FABRIC_PROCUREMENT", "WHOLESALE_STOCK", "Norge stoff metervare restlager grossist parti ruller pris antall"),
    ("SE", "CLOTHING_INVENTORY", "AUCTION_LIQUIDATION", "Sverige kläder konkursauktion varulager parti pris antal"),
    ("SE", "CLOTHING_INVENTORY", "WHOLESALE_STOCK", "Sverige restparti kläder grossist överskottslager parti pris antal"),
    ("SE", "FABRIC_PROCUREMENT", "AUCTION_LIQUIDATION", "Sverige tyg textil konkursauktion varulager rullar pris antal"),
    ("SE", "FABRIC_PROCUREMENT", "WHOLESALE_STOCK", "Sverige tyg textil restparti grossist rullar pris antal"),
    ("DE", "CLOTHING_INVENTORY", "AUCTION_LIQUIDATION", "Deutschland Bekleidung Insolvenz Auktion Warenlager Posten Preis Stück"),
    ("DE", "CLOTHING_INVENTORY", "WHOLESALE_STOCK", "Deutschland Bekleidung Restposten Großhandel Sonderposten Preis Menge Stück"),
    ("DE", "FABRIC_PROCUREMENT", "AUCTION_LIQUIDATION", "Deutschland Stoff Textil Insolvenz Auktion Rollen Preis Menge"),
    ("DE", "FABRIC_PROCUREMENT", "WHOLESALE_STOCK", "Deutschland Stoff Textil Restposten Großhandel Rollen Preis Menge"),
    ("FR", "CLOTHING_INVENTORY", "AUCTION_LIQUIDATION", "France vêtements liquidation judiciaire enchères stock lot prix quantité"),
    ("FR", "CLOTHING_INVENTORY", "WHOLESALE_STOCK", "France vêtements déstockage grossiste lot stock prix quantité"),
    ("FR", "FABRIC_PROCUREMENT", "AUCTION_LIQUIDATION", "France tissu liquidation judiciaire enchères stock rouleaux prix quantité"),
    ("FR", "FABRIC_PROCUREMENT", "WHOLESALE_STOCK", "France tissu déstockage grossiste rouleaux stock prix quantité"),
    ("IT", "CLOTHING_INVENTORY", "AUCTION_LIQUIDATION", "Italia abbigliamento liquidazione giudiziale asta stock lotto prezzo quantità pezzi"),
    ("IT", "CLOTHING_INVENTORY", "WHOLESALE_STOCK", "Italia abbigliamento stock fallimento ingrosso lotto prezzo quantità"),
    ("IT", "FABRIC_PROCUREMENT", "AUCTION_LIQUIDATION", "Italia tessuto liquidazione giudiziale asta rotoli prezzo quantità"),
    ("IT", "FABRIC_PROCUREMENT", "WHOLESALE_STOCK", "Italia tessuto stock fallimento ingrosso rotoli prezzo quantità"),
    ("NL", "CLOTHING_INVENTORY", "AUCTION_LIQUIDATION", "Nederland kleding faillissementsveiling voorraad partij prijs aantal stuks"),
    ("NL", "CLOTHING_INVENTORY", "WHOLESALE_STOCK", "Nederland kleding restpartij partijhandel groothandel prijs aantal stuks"),
    ("NL", "FABRIC_PROCUREMENT", "AUCTION_LIQUIDATION", "Nederland stof textiel faillissementsveiling voorraad rollen prijs aantal"),
    ("NL", "FABRIC_PROCUREMENT", "WHOLESALE_STOCK", "Nederland stof textiel restpartij partijhandel groothandel rollen prijs aantal"),
)

GOLD_SET = (
    {"id": "NO_AUKSJONEN_BLAKLADER_22", "market": "NO", "needles": ("blåkläder", "22 stk")},
    {"id": "NO_AUKSJONEN_BOSCH_32", "market": "NO", "needles": ("bosch car service", "32 stk")},
    {"id": "NO_AUKSJONEN_BJORNKLADER_12", "market": "NO", "needles": ("björnkläder", "12 stk")},
    {"id": "SE_BUDI_MC_170", "market": "SE", "needles": ("mc-intresserade", "170 plagg")},
    {"id": "DE_RESTPOSTEN24_SWEAT_2000", "market": "DE", "needles": ("damen-stocksweatshirts", "2000")},
    {"id": "FR_INTERENCHERES_LINGERIE_144", "market": "FR", "needles": ("stock de lingerie", "144 lots")},
    {"id": "FR_INTERENCHERES_TISSUS_13T", "market": "FR", "needles": ("13 tonnes", "stocks tissus")},
    {"id": "IT_GOBID_TESSUTO_116", "market": "IT", "needles": ("116 rotoli", "tessuto")},
    {"id": "NL_PARTIJ_BADKLEDING_500", "market": "NL", "needles": ("500 stuks", "badkleding")},
    {"id": "NL_PARTIJ_TEENSLIPPERS_4575", "market": "NL", "needles": ("4575", "teenslippers")},
)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", unquote(value).casefold().replace(".", " ")).strip()


def _hit_dict(hit) -> dict[str, str]:
    return {"title": hit.title, "url": hit.url, "description": hit.description, "provider": hit.provider}


def _provider(name: str, key: str, market: str):
    if name == "brave":
        return BraveSearchProvider(key, country=market, max_retries=0, extra_snippets=True)
    if name == "exa":
        return ExaSearchProvider(key, max_retries=0)
    raise ValueError(name)


def _run(name: str, key: str) -> list[dict[str, object]]:
    rows = []
    for market, domain, family, query in QUERY_PACK:
        try:
            hits = _provider(name, key, market).search(query, count=RESULTS_PER_QUERY)
            rows.append({"market": market, "domain": domain, "route_family": family, "query": query, "status": "SUCCESS", "hits": [_hit_dict(hit) for hit in hits], "error": None})
        except Exception as exc:
            rows.append({"market": market, "domain": domain, "route_family": family, "query": query, "status": "FAILED", "hits": [], "error": f"{type(exc).__name__}: {exc}"})
    return rows


def _match(anchor: dict[str, object], hit: dict[str, str]) -> bool:
    haystack = _norm(" ".join((hit.get("title", ""), hit.get("url", ""), hit.get("description", ""))))
    return all(_norm(str(needle)) in haystack for needle in anchor["needles"])


def _score(rows: list[dict[str, object]]) -> dict[str, object]:
    matches = []
    for anchor in GOLD_SET:
        found = None
        family = None
        for row in rows:
            if row["market"] != anchor["market"]:
                continue
            for hit in row["hits"]:
                if _match(anchor, hit):
                    found = hit
                    family = row["route_family"]
                    break
            if found:
                break
        matches.append({"id": anchor["id"], "market": anchor["market"], "matched": found is not None, "route_family": family, "matched_title": found.get("title") if found else None, "matched_url": found.get("url") if found else None})
    count = sum(item["matched"] for item in matches)
    per_market = {}
    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        subset = [item for item in matches if item["market"] == market]
        matched = sum(item["matched"] for item in subset)
        per_market[market] = {"gold_count": len(subset), "matched_count": matched, "recall": round(matched / len(subset), 4) if subset else 0.0}
    return {"gold_count": len(matches), "matched_count": count, "recall": round(count / len(matches), 4), "per_market": per_market, "matches": matches}


def main() -> int:
    brave_key = str(os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip()
    exa_key = str(os.environ.get("EXA_API_KEY") or "").strip()
    if not brave_key or not exa_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY and EXA_API_KEY are required")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    brave_rows = _run("brave", brave_key)
    exa_rows = _run("exa", exa_key)
    brave_score = _score(brave_rows)
    exa_score = _score(exa_rows)
    report = {
        "schema_version": "route-family-query-pack-benchmark-1.0",
        "production_mutation": False,
        "source_specific_queries": False,
        "gold_used_for_query_generation": False,
        "query_count_per_provider": len(QUERY_PACK),
        "results_per_query": RESULTS_PER_QUERY,
        "max_retries": 0,
        "brave_estimated_hard_max_cost_usd": round(len(QUERY_PACK) * 0.005, 3),
        "brave": {"rows": brave_rows, "score": brave_score},
        "exa": {"rows": exa_rows, "score": exa_score},
        "gold_set": list(GOLD_SET),
    }
    (OUTPUT_DIR / "route-family-query-pack-benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "ROUTE-FAMILY QUERY PACK BENCHMARK V1",
        f"queries/provider: {len(QUERY_PACK)} | results/query: {RESULTS_PER_QUERY} | retries: 0",
        f"Brave estimated hard-max cost: ${report['brave_estimated_hard_max_cost_usd']:.3f}",
        f"Brave recall: {brave_score['matched_count']}/10 = {brave_score['recall']:.1%}",
        f"Exa recall: {exa_score['matched_count']}/10 = {exa_score['recall']:.1%}",
        "",
    ]
    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        b = brave_score["per_market"][market]
        e = exa_score["per_market"][market]
        lines.append(f"{market}: Brave {b['matched_count']}/{b['gold_count']} ({b['recall']:.1%}) | Exa {e['matched_count']}/{e['gold_count']} ({e['recall']:.1%})")
    lines.extend(["", "MATCHES"])
    for provider_name, score in (("Brave", brave_score), ("Exa", exa_score)):
        found = [f"{item['id']}@{item['route_family']}" for item in score["matches"] if item["matched"]]
        lines.append(f"{provider_name}: {', '.join(found) if found else 'NONE'}")
    lines.extend(["", "Gold anchors are scoring-only; route-family queries are source-neutral."])
    summary = "\n".join(lines) + "\n"
    (OUTPUT_DIR / "route-family-query-pack-benchmark.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
