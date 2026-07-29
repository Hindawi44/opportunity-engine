#!/usr/bin/env python3
"""Run four controlled Brave requests to isolate the zero-hit failure."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from opportunity_engine.discovery.brave_retrieval_probe import (
    RetrievalProbeResult,
    classify_retrieval_probe,
)
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.ods.brave_search import BraveSearchClient


GENERIC_QUERY = "klær konkurs Norge"
AXL_UNSCOPED_QUERY = '"AXL Sport Og Fritid" Kolvereid'
AXL_SITE_QUERY = "site:norskavvikling.no AXL Kolvereid"


def _sample_current(hits: Sequence[object]) -> tuple[dict[str, str], ...]:
    samples: list[dict[str, str]] = []
    for hit in hits[:5]:
        samples.append({
            "title": str(getattr(hit, "title", "")),
            "url": str(getattr(hit, "url", "")),
        })
    return tuple(samples)


def _sample_legacy(hits: Sequence[dict[str, object]]) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "title": str(hit.get("title") or ""),
            "url": str(hit.get("url") or ""),
        }
        for hit in hits[:5]
    )


def _run_probe(
    probe_id: str,
    client: str,
    query: str,
    search: Callable[[], Sequence[object]],
    sample: Callable[[Sequence[object]], tuple[dict[str, str], ...]],
) -> RetrievalProbeResult:
    try:
        hits = search()
    except Exception as exc:
        return RetrievalProbeResult(
            probe_id=probe_id,
            client=client,
            query=query,
            result_count=0,
            error=str(exc),
        )
    return RetrievalProbeResult(
        probe_id=probe_id,
        client=client,
        query=query,
        result_count=len(hits),
        sample_results=sample(hits),
    )


def _write_summary(payload: dict, path: Path) -> None:
    lines = [
        "BRAVE RETRIEVAL PROBE",
        "=====================",
        "Requests planned: 4",
        f"Requests completed: {payload['requests_completed']}",
        f"Diagnosis: {payload['diagnosis']}",
        f"Next action: {payload['next_action']}",
        "",
        "PROBES",
        "------",
    ]
    for probe in payload["probes"]:
        error = f" error={probe['error']}" if probe["error"] else ""
        lines.append(
            f"{probe['probe_id']}: client={probe['client']} "
            f"results={probe['result_count']}{error}"
        )
    lines.extend([
        "",
        "SAFETY",
        "------",
        "Diagnostic search only. No URL was verified.",
        "Playwright, Analysis, contact, bid, purchase, and payment were not used.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/brave-retrieval-probe",
        help="Artifact directory",
    )
    args = parser.parse_args()

    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("BRAVE_SEARCH_API_KEY is required")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    current = BraveSearchProvider(
        api_key,
        freshness=None,
        extra_snippets=False,
        operators=True,
        max_retries=0,
    )
    legacy = BraveSearchClient(
        api_key=api_key,
        cache_dir=str(output_dir / "cache"),
        cache_ttl_hours=0,
        max_requests_per_run=3,
        usage_log_path=str(output_dir / "usage.jsonl"),
    )

    probes = [
        _run_probe(
            "current-generic",
            "discovery-current",
            GENERIC_QUERY,
            lambda: current.search(GENERIC_QUERY, count=10),
            _sample_current,
        ),
        _run_probe(
            "legacy-generic",
            "legacy-nb-spellcheck",
            GENERIC_QUERY,
            lambda: legacy.search(GENERIC_QUERY, count=10, use_cache=False),
            _sample_legacy,
        ),
        _run_probe(
            "legacy-axl-unscoped",
            "legacy-nb-spellcheck",
            AXL_UNSCOPED_QUERY,
            lambda: legacy.search(AXL_UNSCOPED_QUERY, count=10, use_cache=False),
            _sample_legacy,
        ),
        _run_probe(
            "legacy-axl-site",
            "legacy-nb-spellcheck",
            AXL_SITE_QUERY,
            lambda: legacy.search(AXL_SITE_QUERY, count=10, use_cache=False),
            _sample_legacy,
        ),
    ]
    classification = classify_retrieval_probe(probes)
    payload = {
        "schema_version": "brave-retrieval-probe-1.0",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "requests_planned": 4,
        "requests_completed": len(probes),
        "diagnosis": classification["diagnosis"],
        "next_action": classification["next_action"],
        "probes": [probe.to_dict() for probe in probes],
        "automatic_contact": False,
        "automatic_purchase_decision": False,
        "page_verification_performed": False,
        "playwright_used": False,
        "analysis_engine_used": False,
    }

    json_path = output_dir / "brave-retrieval-probe.json"
    summary_path = output_dir / "brave-retrieval-probe-summary.txt"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_summary(payload, summary_path)
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
