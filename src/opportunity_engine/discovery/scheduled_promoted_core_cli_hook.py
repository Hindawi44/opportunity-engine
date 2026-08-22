"""Pre-checkpoint hook for explicitly promoted learned-query discovery.

The hook runs only when the real multi-market checkpoint CLI starts. It performs
one bounded promoted Core search, verifies exact public closure + inventory pages,
and merges any verified records into the existing Norway cross-source source
before checkpoint consolidation. Failures are isolated as diagnostics and never
remove or mutate the existing source truth beyond a completed successful merge.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


_INSTALLED = False


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def install_scheduled_promoted_core_cli_hook() -> None:
    """Execute once, synchronously, before checkpoint source consolidation."""
    global _INSTALLED
    if _INSTALLED or Path(sys.argv[0]).name != "run_multi_market_daily_operator_checkpoint.py":
        return
    _INSTALLED = True

    input_root = Path(
        str(os.environ.get("INPUT_ROOT") or "").strip()
        or "artifacts/multi-market-inputs"
    )
    learned_dir = input_root / "no-learned-core"
    cross_source_dir = input_root / "no-cross-source"
    bridge_path = learned_dir / "checkpoint-bridge.json"

    try:
        from opportunity_engine.promoted_learned_checkpoint_bridge import (
            merge_promoted_learning_into_norway_cross_source,
        )
        from opportunity_engine.promoted_learned_core_discovery import (
            collect_promoted_learned_core_opportunities,
        )

        discovery = collect_promoted_learned_core_opportunities(
            learned_dir,
            environment=os.environ,
            results_per_query=10,
            max_pages=10,
            max_terms=1,
        )
        if int(discovery.get("verified_opportunity_count") or 0) > 0:
            bridge = merge_promoted_learning_into_norway_cross_source(
                learned_dir,
                cross_source_dir,
            )
        else:
            bridge = {
                "schema_version": "promoted-learned-checkpoint-bridge-1.0",
                "status": "VALID_ZERO",
                "merged_record_count": 0,
                "target": cross_source_dir.as_posix(),
                "automatic_contact": False,
                "automatic_bid": False,
                "automatic_purchase": False,
                "automatic_payment": False,
            }
        payload = {
            "status": "SUCCESS",
            "discovery_status": discovery.get("status"),
            "applied_terms": discovery.get("applied_terms") or [],
            "search_request_count": discovery.get("request_count", 0),
            "page_request_count": discovery.get("page_request_count", 0),
            "verified_opportunity_count": discovery.get("verified_opportunity_count", 0),
            "bridge": bridge,
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    except Exception as exc:
        payload = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error": " ".join(str(exc).split())[:500],
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }

    _write_json(bridge_path, payload)
    print(
        "scheduled_promoted_core:",
        json.dumps(
            {
                "status": payload.get("status"),
                "discovery_status": payload.get("discovery_status"),
                "search_request_count": payload.get("search_request_count", 0),
                "verified_opportunity_count": payload.get("verified_opportunity_count", 0),
                "merged_record_count": (payload.get("bridge") or {}).get(
                    "merged_record_count", 0
                ) if isinstance(payload.get("bridge"), dict) else 0,
                "automatic_query_activation": False,
            },
            sort_keys=True,
        ),
    )
