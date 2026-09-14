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
        "market_code": "NO",
        "source_url": f"https://example.test/item/{identity}",
        "listing_status": "ACTIVE",
        "workflow_status": "REQUIRES_VERIFICATION",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "analysis_eligible": False,
        "top5_eligible": True,
        "discovery_score": score,
    }
    row.update(extra)
    return row


def test_selects_highest_scoring_pending_records_only() -> None:
    report = {
        "deduplicated_opportunities": [
            _record("low", 10),
            _record("high", 90),
            _record("ended", 100, listing_status="ENDED"),
            _record("missing-url", 95, source_url=""),
        ]
    }
    selected = select_pending_opportunities(report, limit=1)
    assert [row["opportunity_identity"] for row in selected] == ["high"]


def test_selects_public_url_from_opportunity_identity_when_source_url_missing() -> None:
    identity_url = "https://market.example/item/123"
    report = {
        "deduplicated_opportunities": [
            _record(identity_url, 90, source_url="", canonical_url="", url=""),
        ]
    }
    selected = select_pending_opportunities(report, limit=1)
    assert [row["opportunity_identity"] for row in selected] == [identity_url]


def test_rotation_prefers_unseen_then_oldest_attempted_records() -> None:
    report = {
        "deduplicated_opportunities": [
            _record("seen-newer", 100),
            _record("unseen-low", 10),
            _record("seen-older", 90),
            _record("unseen-high", 80),
        ]
    }
    state = {
        "records": {
            "seen-newer": {
                "attempt_count": 1,
                "last_investigated_at": "2026-09-12T10:00:00+00:00",
            },
            "seen-older": {
                "attempt_count": 2,
                "last_investigated_at": "2026-09-10T10:00:00+00:00",
            },
        }
    }
    selected = select_pending_opportunities(report, limit=3, investigation_state=state)
    assert [row["opportunity_identity"] for row in selected] == [
        "unseen-high",
        "unseen-low",
        "seen-older",
    ]


def test_investigation_uses_identity_url_and_exposes_backlog_counts() -> None:
    identity_url = "https://market.example/item/123"
    report = {
        "deduplicated_opportunities": [
            _record(identity_url, 90, source_url="", canonical_url="", url=""),
            _record("missing-everywhere", 80, source_url="", canonical_url="", url=""),
        ]
    }
    seen = []

    def fetch(url: str):
        seen.append(url)
        return SimpleNamespace(
            ok=True,
            title="Restlager klær 20 stk til salgs 100 NOK",
            text="Restlager klær 20 stk til salgs 100 NOK",
            raw_html="",
            final_url=url,
            status_code=200,
            error=None,
        )

    result = investigate_pending_opportunities(report, page_fetcher=fetch)
    assert seen == [identity_url]
    assert result["selection_status"] == "SELECTED_FOR_INVESTIGATION"
    assert result["pending_candidate_count"] == 2
    assert result["selectable_pending_count"] == 1
    assert result["unselectable_pending_count"] == 1
    assert result["selected_count"] == 1
    assert result["investigated_count"] == 1
    assert result["newly_investigated_count"] == 1
    assert result["unseen_pending_after_selection"] == 0
    assert result["investigation_state"]["records"][identity_url]["attempt_count"] == 1


def test_investigation_records_verified_and_failed_without_commercial_promotion() -> None:
    report = {"deduplicated_opportunities": [_record("good", 90), _record("bad", 80)]}

    def fetch(url: str):
        if url.endswith("good"):
            return SimpleNamespace(
                ok=True,
                title="Restlager klær 20 stk til salgs 100 NOK",
                text="Restlager klær 20 stk til salgs 100 NOK",
                raw_html="",
                final_url=url,
                status_code=200,
                error=None,
            )
        return SimpleNamespace(ok=False, error="blocked", final_url=url, status_code=403)

    result = investigate_pending_opportunities(report, page_fetcher=fetch)
    assert result["status_counts"]["VERIFIED_EXACT_LOT_CANDIDATE"] == 1
    assert result["status_counts"]["FETCH_FAILED"] == 1
    assert result["newly_verified_exact_lot_ids"] == ["good"]
    assert result["promotion_to_opportunity_allowed"] is False


def test_exact_lot_reconciliation_clears_only_the_proven_blocker() -> None:
    report = {
        "deduplicated_opportunities": [
            _record(
                "partial",
                90,
                missing_evidence=[
                    "verified exact item-page evidence",
                    "documented final payable price including auction fees and VAT",
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
            "partial": {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_investigated_at": "2026-09-14T00:00:00+00:00",
                "source_url": "https://example.test/item/partial",
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(
        report,
        state,
        newly_verified_ids=["partial"],
    )
    item = reconciled["deduplicated_opportunities"][0]
    assert item["missing_evidence"] == [
        "documented final payable price including auction fees and VAT"
    ]
    assert item["workflow_status"] == "REQUIRES_VERIFICATION"
    assert item["analysis_eligible"] is False
    assert reconciled["lifecycle"]["requires_verification_count"] == 1
    assert meta["exact_item_page_blocker_cleared_count"] == 1
    assert meta["promoted_to_active_count"] == 0


def test_exact_lot_reconciliation_advances_only_when_final_blocker_is_cleared() -> None:
    report = {
        "deduplicated_opportunities": [
            _record(
                "ready",
                95,
                missing_evidence=["verified exact item-page evidence"],
            )
        ],
        "analysis_eligible_count": 0,
        "next_human_action": {
            "action": "NO_IMMEDIATE_ACTION",
            "opportunity_identity": None,
        },
        "daily_novelty": {
            "gate_applied": True,
            "reason": "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT",
            "active_analysis_eligible_count": 0,
            "novel_active_count": 0,
            "carryover_active_count": 0,
            "novel_active_opportunity_ids": [],
            "carryover_active_opportunity_ids": [],
        },
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
            "ready": {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_investigated_at": "2026-09-14T00:00:00+00:00",
                "source_url": "https://example.test/item/ready",
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(
        report,
        state,
        newly_verified_ids=["ready"],
    )
    item = reconciled["deduplicated_opportunities"][0]
    assert item["missing_evidence"] == []
    assert item["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert item["evaluation_status"] == "NOT_EVALUATED"
    assert item["analysis_eligible"] is True
    assert reconciled["analysis_eligible_count"] == 1
    assert reconciled["lifecycle"]["stage_counts"]["REQUIRES_VERIFICATION"] == 0
    assert reconciled["lifecycle"]["stage_counts"]["ACTIVE_OPPORTUNITY"] == 1
    assert reconciled["next_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert reconciled["daily_novelty"]["novel_active_opportunity_ids"] == ["ready"]
    assert meta["promoted_to_active_count"] == 1
    assert meta["current_run_promoted_to_active_count"] == 1
    assert meta["commercial_decision_created"] is False


def test_prior_exact_lot_state_is_reapplied_without_reannouncing_as_new() -> None:
    report = {
        "deduplicated_opportunities": [
            _record(
                "carryover",
                80,
                missing_evidence=["verified exact item-page evidence"],
            )
        ],
        "next_human_action": {
            "action": "NO_IMMEDIATE_ACTION",
            "opportunity_identity": None,
        },
        "daily_novelty": {
            "gate_applied": True,
            "novel_active_count": 0,
            "novel_active_opportunity_ids": [],
        },
    }
    state = {
        "records": {
            "carryover": {
                "last_status": "VERIFIED_EXACT_LOT_CANDIDATE",
                "last_investigated_at": "2026-09-13T00:00:00+00:00",
                "source_url": "https://example.test/item/carryover",
            }
        }
    }

    reconciled, meta = reconcile_investigation_lifecycle(report, state)
    assert reconciled["deduplicated_opportunities"][0]["workflow_status"] == "ACTIVE_OPPORTUNITY"
    assert reconciled["next_human_action"]["action"] == "NO_IMMEDIATE_ACTION"
    assert reconciled["daily_novelty"]["novel_active_count"] == 0
    assert meta["promoted_to_active_count"] == 1
    assert meta["current_run_promoted_to_active_count"] == 0
