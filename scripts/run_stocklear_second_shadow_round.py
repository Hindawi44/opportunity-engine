#!/usr/bin/env python3
"""Run a second independent Stocklear shadow round excluding prior recoveries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from opportunity_engine.source_discovery_shadow import build_source_shadow_candidates
from opportunity_engine.source_shadow_live_validation import run_shadow_source_validation


class HttpFetcher:
    def __init__(self, *, timeout_seconds: float = 15.0, max_bytes: int = 2_000_000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OpportunityEngine-ShadowValidation/1.0 (+read-only source proof)",
            "Accept": "text/html,application/xhtml+xml",
        })

    def __call__(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        final_host = (requests.utils.urlparse(response.url).hostname or "").casefold().rstrip(".")
        expected_host = (requests.utils.urlparse(url).hostname or "").casefold().rstrip(".")
        if final_host != expected_host:
            raise ValueError(f"cross-domain redirect blocked: {expected_host} -> {final_host}")
        return response.content[: self.max_bytes].decode(response.encoding or "utf-8", errors="replace")


def _load(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default="config/learning/external_ground_truth_benchmark_2026-08-22.json")
    parser.add_argument("--benchmark-result", default="docs/benchmarks/external-ground-truth-2026-08-22-result.json")
    parser.add_argument("--prior-live-proof", default="docs/benchmarks/source-shadow-live-validation-2026-08-22-result.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--max-detail-requests", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    source_candidates = build_source_shadow_candidates(_load(args.benchmark), _load(args.benchmark_result))
    prior = _load(args.prior_live_proof)
    previous_urls = {
        str(row.get("source_url") or "").strip()
        for row in (prior.get("verified_new_opportunities") or [])
        if isinstance(row, dict) and row.get("source_domain") == "joblot.stocklear.eu" and row.get("source_url")
    }

    stocklear_rows = []
    for raw in source_candidates.get("source_candidates", []):
        if not isinstance(raw, dict) or raw.get("source_domain") != "joblot.stocklear.eu":
            continue
        row = dict(raw)
        row["evidence_urls"] = sorted(set(row.get("evidence_urls") or []) | previous_urls)
        stocklear_rows.append(row)

    shadow_input = {
        "schema_version": source_candidates.get("schema_version"),
        "source_candidates": stocklear_rows,
    }
    report = run_shadow_source_validation(
        shadow_input,
        fetcher=HttpFetcher(timeout_seconds=args.timeout_seconds),
        max_candidates_per_source=args.max_candidates,
        max_detail_requests=args.max_detail_requests,
    )
    report.update({
        "round": 2,
        "source_domain": "joblot.stocklear.eu",
        "prior_recovery_urls_excluded": sorted(previous_urls),
        "prior_recovery_url_exclusion_count": len(previous_urls),
        "independent_round_rule": "TEACHING_URLS_AND_ALL_PRIOR_VERIFIED_RECOVERIES_EXCLUDED",
        "run_mode": "MANUAL_SHADOW_ONLY",
    })

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "novel_candidate_count": report["novel_candidate_count"],
        "verified_new_opportunity_count": report["verified_new_opportunity_count"],
        "prior_recovery_url_exclusion_count": report["prior_recovery_url_exclusion_count"],
        "production_mutation": report["production_mutation"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
