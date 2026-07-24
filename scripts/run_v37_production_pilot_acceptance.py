from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.production_pilot import run_production_cycle

RUN_1 = "2026-07-24T13:00:00+00:00"
RUN_2 = "2026-07-24T14:00:00+00:00"


def opportunity(source: str, listing_id: str, title: str, price: float) -> dict:
    return {
        "schema_version": "3.6",
        "opportunity_id": f"{source.lower()}-{listing_id}",
        "source": {
            "name": source,
            "listing_id": listing_id,
            "url": f"https://example.no/{listing_id}",
            "title": title,
            "location": "Namsos",
            "listing_status": "ACTIVE",
            "asking_price_nok": price,
        },
    }


def snapshot(source: str, items: list[dict]) -> dict:
    return {"schema_version": "3.6", "captured_at": RUN_1, "source": source, "opportunities": items}


def evaluator(items: list[dict]) -> list[dict]:
    output = []
    for item in items:
        ready = item["source"]["listing_id"] == "ready-1"
        output.append({
            "opportunity_id": item["opportunity_id"],
            "decision_gate": "READY_FOR_FINANCIAL_REVIEW" if ready else "EVIDENCE_REQUIRED",
            "verified_comparable_count": 3 if ready else 0,
            "verified_cost_component_count": 6 if ready else 1,
            "expected_profit": 15000 if ready else None,
            "roi": 55 if ready else None,
            "evidence_version": "pilot-1",
            "automatic_purchase_decision": False,
        })
    return output


def main() -> None:
    inputs = [
        snapshot("Auksjonen.no", [opportunity("Auksjonen.no", "ready-1", "Complete shop lot", 10000)]),
        snapshot("FINN.no", [opportunity("FINN.no", "incomplete-1", "Office chairs", 5000)]),
    ]
    first, lifecycle, review = run_production_cycle(
        inputs, lifecycle_state=None, review_state=None, evaluator=evaluator, run_at=RUN_1
    )
    second, _, _ = run_production_cycle(
        inputs, lifecycle_state=lifecycle, review_state=review, evaluator=evaluator, run_at=RUN_2
    )
    summary = {
        "schema_version": "3.7",
        "cycles_completed": 2,
        "first_cycle_new": first["new_opportunities"],
        "first_cycle_review_queue": first["review_queue_count"],
        "first_cycle_alerts": first["new_alerts_count"],
        "second_cycle_new": second["new_opportunities"],
        "second_cycle_unchanged": second["unchanged_opportunities"],
        "second_cycle_sent_to_analysis": second["opportunities_sent_to_analysis"],
        "second_cycle_alerts": second["new_alerts_count"],
        "automatic_purchase_decision": False,
        "errors": [],
        "status": "PASS",
    }
    assert summary["first_cycle_new"] == 2
    assert summary["first_cycle_review_queue"] == 1
    assert summary["first_cycle_alerts"] == 1
    assert summary["second_cycle_new"] == 0
    assert summary["second_cycle_unchanged"] == 2
    assert summary["second_cycle_sent_to_analysis"] == 0
    assert summary["second_cycle_alerts"] == 0
    output = Path("artifacts/v3.7-production-pilot-summary.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
