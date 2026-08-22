#!/usr/bin/env python3
"""Probe Stocklear's public surface without authentication or bypass behavior."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import requests

from opportunity_engine.stocklear_access_stability import (
    classify_access_sample,
    summarize_access_stability,
)

ROOT_URL = "https://joblot.stocklear.eu/"


def _load_probe_urls(proof_path: str | Path, *, max_lot_pages: int) -> list[str]:
    payload = json.loads(Path(proof_path).read_text(encoding="utf-8"))
    rows = payload.get("verified_new_opportunities") or []
    urls = [ROOT_URL]
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("source_url") or "").strip()
        if (urlparse(url).hostname or "").casefold() != "joblot.stocklear.eu":
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) >= 1 + max_lot_pages:
            break
    return urls


def _probe(url: str, *, timeout_seconds: float, max_bytes: int) -> dict:
    headers = {
        "User-Agent": "OpportunityEngine-AccessStability/1.0 (+read-only public access check)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout_seconds,
            allow_redirects=True,
        )
        body = response.content[:max_bytes].decode(response.encoding or "utf-8", errors="replace")
        final_host = (urlparse(response.url).hostname or "").casefold().rstrip(".")
        if final_host != "joblot.stocklear.eu":
            return {
                "url": url,
                "status_code": response.status_code,
                "final_url": response.url,
                "access_status": "CROSS_DOMAIN_REDIRECT",
                "usable_public": False,
                "public_opportunity_markers": False,
                "login_wall_present": False,
                "login_redirect": False,
                "blocked": False,
                "rate_limited": False,
                "challenge_detected": False,
                "html_drift_suspected": False,
                "network_error": None,
            }
        sample = classify_access_sample(
            url=url,
            status_code=response.status_code,
            final_url=response.url,
            body=body,
        )
        sample["response_bytes_observed"] = min(len(response.content), max_bytes)
        sample["network_error"] = None
        return sample
    except requests.RequestException as exc:
        return {
            "url": url,
            "status_code": 0,
            "final_url": "",
            "access_status": "NETWORK_ERROR",
            "usable_public": False,
            "public_opportunity_markers": False,
            "login_wall_present": False,
            "login_redirect": False,
            "blocked": False,
            "rate_limited": False,
            "challenge_detected": False,
            "html_drift_suspected": False,
            "network_error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof",
        default="docs/benchmarks/source-shadow-live-validation-2026-08-22-result.json",
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-lot-pages", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    args = parser.parse_args()

    if not 1 <= args.max_lot_pages <= 5:
        raise SystemExit("max-lot-pages must be 1..5")
    urls = _load_probe_urls(args.proof, max_lot_pages=args.max_lot_pages)
    samples = [
        _probe(url, timeout_seconds=args.timeout_seconds, max_bytes=args.max_bytes)
        for url in urls
    ]
    report = summarize_access_stability(samples)
    report.update(
        {
            "source_name": "Stocklear",
            "source_domain": "joblot.stocklear.eu",
            "proof_path": Path(args.proof).as_posix(),
            "network_request_count": len(urls),
            "request_cap": 1 + args.max_lot_pages,
            "public_only": True,
            "cookies_supplied": False,
            "credentials_supplied": False,
            "run_mode": "MANUAL_SHADOW_ACCESS_STABILITY",
        }
    )
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "verdict": report["verdict"],
        "sample_count": report["sample_count"],
        "usable_public_ratio": report["usable_public_ratio"],
        "blocked_count": report["blocked_count"],
        "rate_limited_count": report["rate_limited_count"],
        "challenge_count": report["challenge_count"],
        "html_drift_count": report["html_drift_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
