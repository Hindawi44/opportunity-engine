from types import SimpleNamespace

from scripts.run_pending_opportunity_investigation import (
    investigate_pending_opportunities,
    reconcile_investigation_lifecycle,
    select_pending_opportunities,
)


def _record(identity: str, score: int, **extra):
    row = {
        "opportunity_identity": identity,
        "title": f"Lot {identity}",
        "market_code": "DE",
        "listing_status": "ACTIVE",
        "workflow_status": "REQUIRES_VERIFICATION",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "analysis_eligible": False,
        "top5_eligible": True,
        "discovery_score": score,
        "missing_evidence": [],
    }
    row.update(extra)
    return row


def _exact_page(url: str):
    return SimpleNamespace(
        ok=True,
        title="Restposten Bekleidung 20 Stk zu verkaufen 100 EUR",
        text="Restposten Bekleidung 20 Stk zu verkaufen 100 EUR",
        raw_html="",
        final_url=url,
        status_code=200,
        error=None,
    )


def test_source_urls_list_is_usable_when_scalar_urls_are_missing() -> None:
    source_url = "https://example.test/auction/933"
    report = {
        "deduplicated_opportunities": [
            _record(
                "auction:933",
                1,
                source_urls=[source_url],
                missing_evidence=["verified exact item pages for promoted bulk lots"],
            )
        ]
    }

    selected = select_pending_opportunities(report, limit=1)

    assert [row["opportunity_identity"] for row in selected] == ["auction:933"]


def test_exact_page_blocker_alias_is_prioritized_over_generic_pending_rows() -> None:
    report = {
        "deduplicated_opportunities": [
            _record(
                "generic-high",
                100,
                source_url="https://example.test/item/generic-high",
                missing_evidence=["condition", "seller or company identity"],
            ),
            _record(
                "target-low",
                1,
                source_urls=["https://example.test/item/target-low"],
                missing_evidence=["verified exact item pages for promoted bulk lots"],
            ),
        ]
    }

    selected = select_pending_opportunities(report, limit=1)

    assert [row["opportunity_identity"] for row in selected] == ["target-low"]


def test_investigation_persists_page_evidence_for_later_reconciliation() -> None:
    source_url = "https://example.test/item/target"
    report = {
        "deduplicated_opportunities": [
            _record(
                "target",
                1,
                source_urls=[source_url],
                missing_evidence=["verified exact item pages for promoted bulk lots"],
            )
        ]
    }

    result = investigate_pending_opportunities(
        report,
        limit=1,
        page_fetcher=_exact_page,
    )

    state = result["investigation_state"]["records"]["target"]
    assert result["resolution_targetable_pending_count"] == 1
    assert result["selected_resolution_targetable_count"] == 1
    assert state["last_status"] == "VERIFIED_EXACT_LOT_CANDIDATE"
    assert state["last_classification"] == "EXACT_LOT_CANDIDATE"
    assert state["last_evidence"]["item_specific_url_evidence"] is True
    assert result["results"][0]["targeted_missing_evidence"] == [
        "verified exact item pages for promoted bulk lots"
    ]


def test_alias_blocker_is_cleared_but_other_evidence_remains_pending() -> None:
    report = {
        "deduplicated_opportunities": [
            _record(
                "auction:933",
                1,
                source_urls=["https://example.test/auction/933"],
                missing_evidence=[
                    "cross-border logistics basis",
                    "documented final payable price",
                    "verified exact item pages for promoted bulk lots",
                ],
            )
        ],
        "analysis_eligible_count": 0,
        "lifecycle": {
            "stage_counts": {
                "EARLY_SIGNAL": 0,
                "CANDIDATE": 0,
                "REQUIRES_VERIFICATION": 1,
                "ACTIVE_OPPORTUNITY": 0,
                "QUALIFIED_OPPORTUNITY": 0,
                "HISTORICAL_MARKET_EVIDENCE": 0,
                "CLOSED": 0,
                "REJECTED": 0,
            },
            "evaluation_status_counts": {"REQUIRES_VERIFICATION": 1},
            "requires_verification_count": 1,
        },
    }
    state = {
        "records": {
            "auction:933": {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_investigated_at": "2026-09-15T00:00:00+00:00",
                "source_url": "https://example.test/auction/933",
                "last_evidence": {"item_specific_url_evidence": True},
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(
        report,
        state,
        newly_verified_ids=["auction:933"],
    )
    item = reconciled["deduplicated_opportunities"][0]

    assert item["missing_evidence"] == [
        "cross-border logistics basis",
        "documented final payable price",
    ]
    assert item["workflow_status"] == "REQUIRES_VERIFICATION"
    assert item["pending_investigation"]["evidence"]["item_specific_url_evidence"] is True
    assert meta["exact_item_page_blocker_cleared_count"] == 1
    assert meta["still_requires_verification_count"] == 1
    assert meta["unresolved_evidence_counts"] == {
        "cross-border logistics basis": 1,
        "documented final payable price": 1,
    }


def test_verified_exact_lot_without_matching_blocker_is_counted_as_still_pending() -> None:
    report = {
        "deduplicated_opportunities": [
            _record(
                "already-exact",
                50,
                source_url="https://example.test/item/already-exact",
                missing_evidence=["condition", "seller or company identity"],
            )
        ]
    }
    state = {
        "records": {
            "already-exact": {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_investigated_at": "2026-09-15T00:00:00+00:00",
                "source_url": "https://example.test/item/already-exact",
                "last_evidence": {"item_specific_url_evidence": True},
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(report, state)
    item = reconciled["deduplicated_opportunities"][0]

    assert item["workflow_status"] == "REQUIRES_VERIFICATION"
    assert meta["exact_item_page_already_satisfied_count"] == 1
    assert meta["still_requires_verification_count"] == 1
    assert meta["unresolved_evidence_counts"] == {
        "condition": 1,
        "seller or company identity": 1,
    }
