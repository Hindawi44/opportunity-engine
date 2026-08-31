from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.exa_search import ExaSearchProvider


OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "artifacts/search-maturity-blind-benchmark"))
RESULTS_PER_QUERY = 10
MAX_QUERY_COUNT = 12

# The query matrix is intentionally generic and market-native. It contains no
# benchmark URLs, seller names, or known opportunity titles from the Gold Set.
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

# External Gold Set: scoring-only anchors confirmed independently of the engine.
# These strings never participate in query construction.
GOLD_SET = (
    {"id": "NO_AUKSJONEN_BLAKLADER_22", "market": "NO", "domain": "CLOTHING_INVENTORY", "needles": ("blåkläder", "22 stk")},
    {"id": "NO_AUKSJONEN_BOSCH_32", "market": "NO", "domain": "CLOTHING_INVENTORY", "needles": ("bosch car service", "32 stk")},
    {"id": "NO_AUKSJONEN_BJORNKLADER_12", "market": "NO", "domain": "CLOTHING_INVENTORY", "needles": ("björnkläder", "12 stk")},
    {"id": "SE_BUDI_MC_170", "market": "SE", "domain": "CLOTHING_INVENTORY", "needles": ("mc-intresserade", "170 plagg")},
    {"id": "DE_RESTPOSTEN24_SWEAT_2000", "market": "DE", "domain": "CLOTHING_INVENTORY", "needles": ("damen-stocksweatshirts", "2000")},
    {"id": "FR_INTERENCHERES_LINGERIE_144", "market": "FR", "domain": "CLOTHING_INVENTORY", "needles": ("stock de lingerie", "144 lots")},
    {"id": "FR_INTERENCHERES_TISSUS_13T", "market": "FR", "domain": "FABRIC_PROCUREMENT", "needles": ("13 tonnes", "stocks tissus")},
    {"id": "IT_GOBID_TESSUTO_116", "market": "IT", "domain": "FABRIC_PROCUREMENT", "needles": ("116 rotoli", "tessuto")},
    {"id": "NL_PARTIJ_BADKLEDING_500", "market": "NL", "domain": "CLOTHING_INVENTORY", "needles": ("500 stuks", "badkleding")},
    {"id": "NL_PARTIJ_TEENSLIPPERS_4575", "market": "NL", "domain": "CLOTHING_INVENTORY", "needles": ("4575", "teenslippers")},
)


def _norm(value: str) -> str:
    value = unquote(value).casefold()
    value = value.replace(".", "")
    return re.sub(r"\s+", " ", value).strip()


def _serialize_hit(hit) -> dict[str, str]:
    return {
        "title": hit.title,
        "url": hit.url,
        "description": hit.description,
        "provider": hit.provider,
    }


def _anchor_match(anchor: dict[str, object], hit: dict[str, str]) -> bool:
    haystack = _norm(" ".join((hit.get("title", ""), hit.get("url", ""), hit.get("description", ""))))
    needles = tuple(_norm(str(item)) for item in anchor["needles"])
    return all(needle in haystack for needle in needles)


def _score(provider_results: list[dict[str, object]]) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    matched_ids: set[str] = set()
    per_market: dict[str, dict[str, int | float]] = {}

    for anchor in GOLD_SET:
        market = str(anchor["market"])
        market_hits: list[dict[str, str]] = []
        for row in provider_results:
            if row["market"] != market:
                continue
            market_hits.extend(row["hits"])
        hit = next((item for item in market_hits if _anchor_match(anchor, item)), None)
        matched = hit is not None
        if matched:
            matched_ids.add(str(anchor["id"]))
        matches.append(
            {
                "id": anchor["id"],
                "market": market,
                "domain": anchor["domain"],
                "matched": matched,
                "matched_url": hit.get("url") if hit else None,
                "matched_title": hit.get("title") if hit else None,
            }
        )

    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        anchors = [item for item in GOLD_SET if item["market"] == market]
        found = sum(1 for item in matches if item["market"] == market and item["matched"])
        total = len(anchors)
        per_market[market] = {
            "gold_count": total,
            "matched_count": found,
            "recall": round(found / total, 4) if total else 0.0,
        }

    return {
        "gold_count": len(GOLD_SET),
        "matched_count": len(matched_ids),
        "anchor_recall": round(len(matched_ids) / len(GOLD_SET), 4),
        "per_market": per_market,
        "matches": matches,
    }


def _run_provider(name: str, api_key: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for market, domain, query in QUERY_MATRIX:
        try:
            if name == "brave":
                provider = BraveSearchProvider(
                    api_key,
                    country=market,
                    max_retries=0,
                    extra_snippets=True,
                )
            elif name == "exa":
                provider = ExaSearchProvider(api_key, max_retries=0)
            else:  # pragma: no cover
                raise ValueError(name)
            hits = provider.search(query, count=RESULTS_PER_QUERY)
            rows.append(
                {
                    "market": market,
                    "domain": domain,
                    "query": query,
                    "status": "SUCCESS",
                    "hit_count": len(hits),
                    "hits": [_serialize_hit(hit) for hit in hits],
                    "error": None,
                }
            )
        except Exception as exc:  # benchmark must preserve partial evidence
            rows.append(
                {
                    "market": market,
                    "domain": domain,
                    "query": query,
                    "status": "FAILED",
                    "hit_count": 0,
                    "hits": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows


def _url_set(rows: list[dict[str, object]]) -> set[str]:
    urls: set[str] = set()
    for row in rows:
        for hit in row["hits"]:
            url = str(hit.get("url") or "").strip()
            if url:
                urls.add(url.split("#", 1)[0].rstrip("/"))
    return urls


def main() -> int:
    if len(QUERY_MATRIX) != MAX_QUERY_COUNT:
        raise SystemExit(f"query cap violated: {len(QUERY_MATRIX)} != {MAX_QUERY_COUNT}")

    brave_key = str(os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip()
    exa_key = str(os.environ.get("EXA_API_KEY") or "").strip()
    if not brave_key or not exa_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY and EXA_API_KEY are required")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    brave_rows = _run_provider("brave", brave_key)
    exa_rows = _run_provider("exa", exa_key)
    brave_score = _score(brave_rows)
    exa_score = _score(exa_rows)

    brave_urls = _url_set(brave_rows)
    exa_urls = _url_set(exa_rows)
    union = brave_urls | exa_urls
    overlap = brave_urls & exa_urls

    report = {
        "schema_version": "search-maturity-blind-benchmark-1.0",
        "production_mutation": False,
        "automatic_provider_activation": False,
        "automatic_query_activation": False,
        "query_count_per_provider": len(QUERY_MATRIX),
        "results_per_query": RESULTS_PER_QUERY,
        "hard_outbound_attempt_cap": {
            "brave": len(QUERY_MATRIX),
            "exa": len(QUERY_MATRIX),
            "brave_max_retries": 0,
            "exa_max_retries": 0,
        },
        "brave": {"queries": brave_rows, "score": brave_score},
        "exa": {"queries": exa_rows, "score": exa_score},
        "provider_overlap": {
            "brave_unique_urls": len(brave_urls),
            "exa_unique_urls": len(exa_urls),
            "overlap_urls": len(overlap),
            "union_urls": len(union),
            "jaccard": round(len(overlap) / len(union), 4) if union else 0.0,
        },
        "gold_set": list(GOLD_SET),
    }
    (OUTPUT_DIR / "search-maturity-blind-benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "SEARCH MATURITY BLIND BENCHMARK V1",
        f"queries/provider: {len(QUERY_MATRIX)} | results/query: {RESULTS_PER_QUERY}",
        "Brave/Exa retries: 0/0",
        f"Brave anchor recall: {brave_score['matched_count']}/{brave_score['gold_count']} = {brave_score['anchor_recall']:.1%}",
        f"Exa anchor recall: {exa_score['matched_count']}/{exa_score['gold_count']} = {exa_score['anchor_recall']:.1%}",
        f"Provider URL overlap: {len(overlap)}/{len(union)} = {report['provider_overlap']['jaccard']:.1%}",
        "",
    ]
    for market in ("NO", "SE", "DE", "FR", "IT", "NL"):
        b = brave_score["per_market"][market]
        e = exa_score["per_market"][market]
        lines.append(
            f"{market}: Brave {b['matched_count']}/{b['gold_count']} ({b['recall']:.1%}) | "
            f"Exa {e['matched_count']}/{e['gold_count']} ({e['recall']:.1%})"
        )
    lines.append("")
    lines.append("MISSES")
    for provider_name, score in (("Brave", brave_score), ("Exa", exa_score)):
        misses = [item["id"] for item in score["matches"] if not item["matched"]]
        lines.append(f"{provider_name}: {', '.join(misses) if misses else 'NONE'}")
    lines.extend(
        [
            "",
            "This benchmark is read-only. Gold anchors are scoring-only and are not used in query construction.",
        ]
    )
    summary = "\n".join(lines) + "\n"
    (OUTPUT_DIR / "search-maturity-blind-benchmark.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
