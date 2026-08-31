from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.exa_search import ExaSearchProvider

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "artifacts/dynamic-source-route-expansion-benchmark"))
RESULTS_PER_QUERY = 20
MAX_ROUTE_HOSTS_PER_QUERY = 2

# Stage 1 stays source-neutral. No Gold-Set identity, seller, platform, or URL is
# used to create these searches.
QUERY_MATRIX = (
    ("NO", "CLOTHING_INVENTORY", "parti klær konkurs restlager grossist auksjon lager"),
    ("NO", "FABRIC_PROCUREMENT", "parti stoff tekstil metervare konkurs restlager ruller"),
    ("SE", "CLOTHING_INVENTORY", "parti kläder konkurs restlager grossist auktion lager"),
    ("SE", "FABRIC_PROCUREMENT", "parti tyg textil konkurs restlager grossist rullar"),
    ("DE", "CLOTHING_INVENTORY", "Bekleidung Restposten Insolvenz Lagerbestand Posten Großhandel"),
    ("DE", "FABRIC_PROCUREMENT", "Stoff Textil Restposten Insolvenz Lagerbestand Rollen"),
    ("FR", "CLOTHING_INVENTORY", "lot vêtements liquidation judiciaire stock déstockage grossiste"),
    ("FR", "FABRIC_PROCUREMENT", "lot tissu liquidation judiciaire stock rouleaux textile"),
    ("IT", "CLOTHING_INVENTORY", "lotto abbigliamento liquidazione giudiziale stock magazzino"),
    ("IT", "FABRIC_PROCUREMENT", "rotoli tessuto liquidazione giudiziale stock magazzino"),
    ("NL", "CLOTHING_INVENTORY", "partij kleding faillissement voorraad restpartij groothandel"),
    ("NL", "FABRIC_PROCUREMENT", "partij stof textiel faillissement voorraad rollen restpartij"),
)

# Scoring-only anchors independently confirmed outside the engine. They are never
# read by host selection or query generation.
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

_ROUTE_MARKERS = (
    "auction", "auktion", "auksjon", "veiling", "enchere", "enchères", "asta", "aste",
    "liquidation", "liquidazione", "faillissement", "konkurs", "insolvenz", "restposten",
    "restpartij", "stock", "lot", "grossist", "grossiste", "wholesale", "groothandel",
    "ingrosso", "destock", "déstock", "parti", "partij",
)

_EXACT_LOT_BOOSTERS = {
    ("NO", "CLOTHING_INVENTORY"): "klær vareparti pris antall stk til salgs",
    ("NO", "FABRIC_PROCUREMENT"): "stoff tekstil ruller pris antall til salgs",
    ("SE", "CLOTHING_INVENTORY"): "kläder restparti pris antal st säljes",
    ("SE", "FABRIC_PROCUREMENT"): "tyg textil rullar pris antal säljes",
    ("DE", "CLOTHING_INVENTORY"): "Bekleidung Restposten Preis Menge Stück Angebot",
    ("DE", "FABRIC_PROCUREMENT"): "Stoff Textil Rollen Preis Menge Angebot",
    ("FR", "CLOTHING_INVENTORY"): "vêtements lot prix quantité vente",
    ("FR", "FABRIC_PROCUREMENT"): "tissu rouleaux prix quantité vente",
    ("IT", "CLOTHING_INVENTORY"): "abbigliamento lotto prezzo quantità pezzi vendita",
    ("IT", "FABRIC_PROCUREMENT"): "tessuto rotoli prezzo quantità vendita",
    ("NL", "CLOTHING_INVENTORY"): "kleding partij prijs aantal stuks te koop",
    ("NL", "FABRIC_PROCUREMENT"): "stof textiel rollen prijs aantal te koop",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", unquote(value).casefold().replace(".", " ")).strip()


def _hit_dict(hit) -> dict[str, str]:
    return {"title": hit.title, "url": hit.url, "description": hit.description, "provider": hit.provider}


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _route_score(hit: dict[str, str], position: int) -> tuple[int, int, int]:
    url = hit.get("url", "")
    host = _host(url)
    if not host:
        return (-999, 0, 0)
    path = (urlsplit(url).path or "").casefold()
    if path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
        return (-999, 0, 0)
    text = _norm(" ".join((hit.get("title", ""), host, path, hit.get("description", ""))))
    marker_count = sum(marker in text for marker in _ROUTE_MARKERS)
    # Prefer commercially dense results and stable HTTPS domains, then earlier rank.
    # No domain name is whitelisted or pinned.
    title_marker_count = sum(marker in _norm(hit.get("title", "")) for marker in _ROUTE_MARKERS)
    return (marker_count + title_marker_count, -position, -len(host))


def _select_route_hosts(hits: list[dict[str, str]]) -> list[dict[str, object]]:
    best_by_host: dict[str, tuple[tuple[int, int, int], int, dict[str, str]]] = {}
    for position, hit in enumerate(hits):
        host = _host(hit.get("url", ""))
        if not host:
            continue
        score = _route_score(hit, position)
        if score[0] < 2:
            continue
        existing = best_by_host.get(host)
        if existing is None or score > existing[0]:
            best_by_host[host] = (score, position, hit)
    ranked = sorted(best_by_host.items(), key=lambda item: item[1][0], reverse=True)
    return [
        {
            "host": host,
            "route_score": data[0][0],
            "stage1_rank": data[1] + 1,
            "evidence_title": data[2].get("title"),
            "evidence_url": data[2].get("url"),
        }
        for host, data in ranked[:MAX_ROUTE_HOSTS_PER_QUERY]
    ]


def _provider(name: str, key: str, market: str):
    if name == "brave":
        return BraveSearchProvider(key, country=market, max_retries=0, extra_snippets=True)
    if name == "exa":
        return ExaSearchProvider(key, max_retries=0)
    raise ValueError(name)


def _safe_search(name: str, key: str, market: str, query: str) -> tuple[str, list[dict[str, str]], str | None]:
    try:
        hits = _provider(name, key, market).search(query, count=RESULTS_PER_QUERY)
        return "SUCCESS", [_hit_dict(hit) for hit in hits], None
    except Exception as exc:
        return "FAILED", [], f"{type(exc).__name__}: {exc}"


def _anchor_match(anchor: dict[str, object], hit: dict[str, str]) -> bool:
    haystack = _norm(" ".join((hit.get("title", ""), hit.get("url", ""), hit.get("description", ""))))
    return all(_norm(str(needle)) in haystack for needle in anchor["needles"])


def _score(rows: list[dict[str, object]]) -> dict[str, object]:
    matches = []
    for anchor in GOLD_SET:
        hit = None
        stage = None
        for row in rows:
            if row["market"] != anchor["market"]:
                continue
            for candidate in row["hits"]:
                if _anchor_match(anchor, candidate):
                    hit = candidate
                    stage = row["stage"]
                    break
            if hit:
                break
        matches.append({
            "id": anchor["id"],
            "market": anchor["market"],
            "matched": hit is not None,
            "matched_stage": stage,
            "matched_url": hit.get("url") if hit else None,
            "matched_title": hit.get("title") if hit else None,
        })
    found = sum(item["matched"] for item in matches)
    per_market = {}
    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        subset = [item for item in matches if item["market"] == market]
        matched = sum(item["matched"] for item in subset)
        per_market[market] = {
            "gold_count": len(subset),
            "matched_count": matched,
            "recall": round(matched / len(subset), 4) if subset else 0.0,
        }
    return {"gold_count": len(matches), "matched_count": found, "recall": round(found / len(matches), 4), "per_market": per_market, "matches": matches}


def _run(name: str, key: str) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    stage1_by_key: dict[tuple[str, str], list[dict[str, str]]] = {}
    route_hosts: dict[str, list[dict[str, object]]] = {}
    search_attempts = 0

    for market, domain, query in QUERY_MATRIX:
        status, hits, error = _safe_search(name, key, market, query)
        search_attempts += 1
        rows.append({"stage": "STAGE1_BROAD", "market": market, "domain": domain, "query": query, "status": status, "hits": hits, "error": error})
        stage1_by_key[(market, domain)] = hits

    stage1_score = _score(rows)

    for market, domain, _ in QUERY_MATRIX:
        selected = _select_route_hosts(stage1_by_key[(market, domain)])
        route_hosts[f"{market}:{domain}"] = selected
        booster = _EXACT_LOT_BOOSTERS[(market, domain)]
        for route in selected:
            host = str(route["host"])
            query = f"site:{host} {booster}"
            status, hits, error = _safe_search(name, key, market, query)
            search_attempts += 1
            rows.append({
                "stage": "STAGE2_DYNAMIC_SOURCE_ROUTE",
                "market": market,
                "domain": domain,
                "query": query,
                "derived_host": host,
                "host_selection": route,
                "status": status,
                "hits": hits,
                "error": error,
            })

    final_score = _score(rows)
    return {
        "provider": name,
        "search_attempts": search_attempts,
        "hard_max_search_attempts": len(QUERY_MATRIX) * (1 + MAX_ROUTE_HOSTS_PER_QUERY),
        "stage1_score": stage1_score,
        "final_score": final_score,
        "recall_delta": round(float(final_score["recall"]) - float(stage1_score["recall"]), 4),
        "selected_route_hosts": route_hosts,
        "rows": rows,
    }


def main() -> int:
    brave_key = str(os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip()
    exa_key = str(os.environ.get("EXA_API_KEY") or "").strip()
    if not brave_key or not exa_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY and EXA_API_KEY are required")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    brave = _run("brave", brave_key)
    exa = _run("exa", exa_key)
    report = {
        "schema_version": "dynamic-source-route-expansion-benchmark-1.0",
        "production_mutation": False,
        "source_pinning": False,
        "gold_used_for_query_generation": False,
        "results_per_query": RESULTS_PER_QUERY,
        "max_route_hosts_per_query": MAX_ROUTE_HOSTS_PER_QUERY,
        "brave_estimated_max_incremental_cost_usd": round(brave["hard_max_search_attempts"] * 0.005, 3),
        "brave": brave,
        "exa": exa,
        "gold_set": list(GOLD_SET),
    }
    (OUTPUT_DIR / "dynamic-source-route-expansion-benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "DYNAMIC SOURCE-ROUTE EXPANSION BENCHMARK V1",
        f"Stage1 queries/provider: {len(QUERY_MATRIX)} | results/query: {RESULTS_PER_QUERY}",
        f"Stage2 dynamic hosts/query: <= {MAX_ROUTE_HOSTS_PER_QUERY}",
        f"Brave attempts: {brave['search_attempts']} / hard max {brave['hard_max_search_attempts']}",
        f"Brave estimated hard-max cost: ${report['brave_estimated_max_incremental_cost_usd']:.3f}",
        f"Brave recall: stage1 {brave['stage1_score']['matched_count']}/10 ({brave['stage1_score']['recall']:.1%}) -> final {brave['final_score']['matched_count']}/10 ({brave['final_score']['recall']:.1%})",
        f"Exa recall: stage1 {exa['stage1_score']['matched_count']}/10 ({exa['stage1_score']['recall']:.1%}) -> final {exa['final_score']['matched_count']}/10 ({exa['final_score']['recall']:.1%})",
        "",
        "FINAL PER MARKET",
    ]
    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        b = brave["final_score"]["per_market"][market]
        e = exa["final_score"]["per_market"][market]
        lines.append(f"{market}: Brave {b['matched_count']}/{b['gold_count']} ({b['recall']:.1%}) | Exa {e['matched_count']}/{e['gold_count']} ({e['recall']:.1%})")
    lines.extend(["", "MATCHES"])
    for provider in (brave, exa):
        found = [f"{item['id']}@{item['matched_stage']}" for item in provider["final_score"]["matches"] if item["matched"]]
        lines.append(f"{provider['provider']}: {', '.join(found) if found else 'NONE'}")
    lines.extend(["", "Gold anchors are scoring-only. Stage2 domains are derived only from Stage1 provider results."])
    summary = "\n".join(lines) + "\n"
    (OUTPUT_DIR / "dynamic-source-route-expansion-benchmark.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
