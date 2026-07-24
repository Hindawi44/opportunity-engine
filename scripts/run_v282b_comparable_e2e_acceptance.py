#!/usr/bin/env python3
"""Deterministic V2.8.2B comparable-evidence acceptance run."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.external_financial_bridge import collect_external_financial_evidence
from opportunity_engine.external_market_comparables import MarketComparablesEngine
from opportunity_engine.external_research.comparable_evidence import candidate_to_market_price_evidence


OPPORTUNITY_ID = "e2e-comparable-test"


def _candidate(title: str, url: str, price: float, similarity: float) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        url=url,
        price_nok=price,
        price_currency="NOK",
        source_name="V2.8.2B deterministic acceptance fixture",
        observed_at=datetime.now(timezone.utc).isoformat(),
        similarity_score=similarity,
    )


def build_report(root: Path) -> dict[str, object]:
    errors: list[str] = []
    candidates = (
        _candidate("Industrial machine comparable A", "https://market-a.no/items/1", 10_000, 0.84),
        _candidate("Industrial machine comparable B", "https://market-b.no/items/2", 12_000, 0.81),
        _candidate("Industrial machine comparable C", "https://market-c.no/items/3", 14_000, 0.79),
    )
    analysed = MarketComparablesEngine().analyse(candidates)
    accepted = tuple(analysed.accepted)

    repository = EvidenceRepository(root / "evidence")
    persisted_ids: list[str] = []
    for item in accepted:
        try:
            result = repository.upsert(candidate_to_market_price_evidence(item, OPPORTUNITY_ID))
            persisted_ids.append(result.evidence.evidence_id)
        except ValueError as exc:
            errors.append(str(exc))

    reloaded = []
    for evidence_id in persisted_ids:
        try:
            reloaded.append(repository.load(OPPORTUNITY_ID, evidence_id))
        except (FileNotFoundError, ValueError, OSError) as exc:
            errors.append(str(exc))

    financial = collect_external_financial_evidence(root / "evidence")
    comparables = financial.get(OPPORTUNITY_ID, {}).get("market_comparables", [])
    verified_count = len(comparables) if isinstance(comparables, list) else 0
    complete = verified_count >= 3

    report: dict[str, object] = {
        "schema_version": "2.8.2B",
        "opportunity_id": OPPORTUNITY_ID,
        "candidates_received": len(candidates),
        "valid_price_candidates": len(accepted),
        "evidence_persisted": len(persisted_ids),
        "evidence_reloaded": len(reloaded),
        "verified_comparable_count": verified_count,
        "comparable_status": "COMPLETE" if complete else "INCOMPLETE",
        "scenarios_regenerated": complete,
        "financial_score_status": "PRELIMINARY",
        "errors": errors,
    }
    report["status"] = "PASS" if (
        report["valid_price_candidates"] == 3
        and report["evidence_persisted"] == 3
        and report["evidence_reloaded"] == 3
        and report["verified_comparable_count"] == 3
        and report["comparable_status"] == "COMPLETE"
        and not errors
    ) else "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/validation/v2.8.2b-comparable-e2e-acceptance.json")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="v282b-") as temporary:
        report = build_report(Path(temporary))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
