#!/usr/bin/env python3
"""Qualify one Stage-3 exact-lot candidate from an existing shadow report.

The input is a saved Exa exact-lot hunt JSON artifact. This command performs one
read-only re-fetch of the selected original item page, extracts source facts,
and writes a conservative Stage-4 qualification artifact. It performs no
contact, bid, reservation, purchase, or payment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.exact_lot_commercial_qualification import (
    EXACT_LOT_CANDIDATE,
    qualify_exact_lot_commercial_page,
)
from opportunity_engine.discovery.keyword_shadow_verification import fetch_public_page


def _load(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _select_candidate(report: dict, requested_url: str | None) -> dict:
    verification = report.get("verification") or {}
    pages = verification.get("verified_pages") or []
    exact = [
        item
        for item in pages
        if isinstance(item, dict) and item.get("classification") == EXACT_LOT_CANDIDATE
    ]
    if requested_url:
        exact = [
            item
            for item in exact
            if str(item.get("final_url") or item.get("url") or "").strip() == requested_url.strip()
        ]
    if len(exact) != 1:
        raise ValueError(
            f"expected exactly one matching EXACT_LOT_CANDIDATE, found {len(exact)}"
        )
    return exact[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hunt-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--url", default="")
    args = parser.parse_args()

    hunt = _load(args.hunt_report)
    candidate = _select_candidate(hunt, args.url or None)
    url = str(candidate.get("final_url") or candidate.get("url") or "").strip()
    if not url:
        raise SystemExit("selected exact-lot candidate has no URL")

    page = fetch_public_page(url)
    qualified = qualify_exact_lot_commercial_page(candidate, page)
    qualified["stage3_source"] = {
        "schema_version": hunt.get("schema_version"),
        "generated_at": hunt.get("generated_at"),
        "shadow_only": hunt.get("shadow_only"),
        "candidate_url": url,
    }
    _write(Path(args.output), qualified)

    print("status=", qualified.get("status"))
    print("exact_lot_status=", qualified.get("exact_lot_status"))
    facts = qualified.get("source_facts") or {}
    print("price=", (facts.get("price") or {}).get("amount"), (facts.get("price") or {}).get("currency"))
    print("quantity=", (facts.get("quantity") or {}).get("total_units"))
    print("location=", (facts.get("location") or {}).get("locality"))
    print("logistics=", (facts.get("logistics") or {}).get("status"))
    print("analysis_state=", qualified.get("analysis_state"))
    print("next_human_action=", (qualified.get("next_human_action") or {}).get("action"))
    return 0 if qualified.get("status") == "QUALIFIED_SOURCE_FACTS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
