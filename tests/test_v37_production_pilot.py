from opportunity_engine.production_pilot import run_production_cycle

RUN_1 = "2026-07-24T13:00:00+00:00"
RUN_2 = "2026-07-24T14:00:00+00:00"


def _opportunity(source, listing_id, title, price):
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


def _snapshot(source, items):
    return {
        "schema_version": "3.6",
        "captured_at": RUN_1,
        "source": source,
        "opportunities": items,
    }


def _evaluator(items):
    results = []
    for item in items:
        source = item["source"]
        ready = source["listing_id"] == "ready-1"
        results.append({
            "opportunity_id": item["opportunity_id"],
            "decision_gate": "READY_FOR_FINANCIAL_REVIEW" if ready else "EVIDENCE_REQUIRED",
            "verified_comparable_count": 3 if ready else 0,
            "verified_cost_component_count": 6 if ready else 1,
            "expected_profit": 15000 if ready else None,
            "roi": 55 if ready else None,
            "evidence_version": "pilot-1",
            "automatic_purchase_decision": False,
        })
    return results


def test_v37_two_cycle_production_pilot_acceptance():
    auksjonen = _snapshot("Auksjonen.no", [
        _opportunity("Auksjonen.no", "ready-1", "Complete shop lot", 10000),
    ])
    finn = _snapshot("FINN.no", [
        _opportunity("FINN.no", "incomplete-1", "Office chairs", 5000),
    ])

    first, lifecycle, review = run_production_cycle(
        [auksjonen, finn], lifecycle_state=None, review_state=None,
        evaluator=_evaluator, run_at=RUN_1,
    )
    assert first == {
        "schema_version": "3.7",
        "run_at": RUN_1,
        "sources": ["Auksjonen.no", "FINN.no"],
        "opportunities_received": 2,
        "unique_opportunities": 2,
        "duplicates_removed": 0,
        "new_opportunities": 2,
        "updated_opportunities": 0,
        "unchanged_opportunities": 0,
        "removed_opportunities": 0,
        "archived_opportunities": 0,
        "opportunities_sent_to_analysis": 2,
        "evaluated_opportunities": 2,
        "review_queue_count": 1,
        "new_alerts_count": 1,
        "automatic_purchase_decision": False,
        "errors": [],
        "status": "PASS",
    }

    second, _, _ = run_production_cycle(
        [auksjonen, finn], lifecycle_state=lifecycle, review_state=review,
        evaluator=_evaluator, run_at=RUN_2,
    )
    assert second["new_opportunities"] == 0
    assert second["updated_opportunities"] == 0
    assert second["unchanged_opportunities"] == 2
    assert second["opportunities_sent_to_analysis"] == 0
    assert second["evaluated_opportunities"] == 0
    assert second["review_queue_count"] == 1
    assert second["new_alerts_count"] == 0
    assert second["automatic_purchase_decision"] is False
    assert second["status"] == "PASS"
