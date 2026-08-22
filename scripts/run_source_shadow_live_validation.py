#!/usr/bin/env python3
"""Run one bounded live shadow scan of sources learned from confirmed misses."""
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
        self.session.headers.update(
            {
                "User-Agent": "OpportunityEngine-ShadowValidation/1.0 (+read-only source proof)",
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def __call__(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=True)
        response.raise_for_status()
        final_host = (requests.utils.urlparse(response.url).hostname or "").casefold().rstrip(".")
        expected_host = (requests.utils.urlparse(url).hostname or "").casefold().rstrip(".")
        if final_host != expected_host:
            raise ValueError(f"cross-domain redirect blocked: {expected_host} -> {final_host}")
        content = response.content[: self.max_bytes]
        encoding = response.encoding or "utf-8"
        return content.decode(encoding, errors="replace")


def _load_json(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        default="config/learning/external_ground_truth_benchmark_2026-08-22.json",
    )
    parser.add_argument(
        "--benchmark-result",
        default="docs/benchmarks/external-ground-truth-2026-08-22-result.json",
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-candidates-per-source", type=int, default=5)
    parser.add_argument("--max-detail-requests", type=int, default=6)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    benchmark = _load_json(args.benchmark)
    benchmark_result = _load_json(args.benchmark_result)
    source_candidates = build_source_shadow_candidates(benchmark, benchmark_result)
    report = run_shadow_source_validation(
        source_candidates,
        fetcher=HttpFetcher(timeout_seconds=args.timeout_seconds),
        max_candidates_per_source=args.max_candidates_per_source,
        max_detail_requests=args.max_detail_requests,
    )
    report.update(
        {
            "benchmark_path": Path(args.benchmark).as_posix(),
            "benchmark_result_path": Path(args.benchmark_result).as_posix(),
            "source_candidate_count": source_candidates.get("source_candidate_count", 0),
            "validated_source_count": source_candidates.get("validated_source_count", 0),
            "run_mode": "MANUAL_SHADOW_ONLY",
        }
    )
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "eligible_source_count": report["eligible_source_count"],
                "novel_candidate_count": report["novel_candidate_count"],
                "verified_new_opportunity_count": report["verified_new_opportunity_count"],
                "network_request_count": report["network_request_count"],
                "production_mutation": report["production_mutation"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
