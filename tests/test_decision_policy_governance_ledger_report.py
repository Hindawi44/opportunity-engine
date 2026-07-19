from datetime import datetime, timedelta, timezone

import pytest

from opportunity_engine.ods.decision_policy_governance_ledger import (
    DecisionPolicyGovernanceLedgerEntry,
    GovernanceLedgerEventType,
)
from opportunity_engine.ods.decision_policy_governance_ledger_report import (
    build_governance_ledger_report,
)


def _entry(
    sequence: int,
    event_type: GovernanceLedgerEventType,
    *,
    minute: int,
    decision: str | None = None,
    actor: str = "system",
    change_set_id: str = "change-1",
    rule_name: str = "minimum_margin",
    policy_version: str = "v2",
    lifecycle_status: str = "active",
) -> DecisionPolicyGovernanceLedgerEntry:
    return DecisionPolicyGovernanceLedgerEntry(
        sequence=sequence,
        change_set_id=change_set_id,
        rule_name=rule_name,
        policy_version=policy_version,
        lifecycle_status=lifecycle_status,
        event_type=event_type,
        recorded_at=datetime(2026, 7, 19, 12, minute, tzinfo=timezone.utc),
        actor=actor,
        decision=decision,
        notes="Auditable governance event.",
    )


def test_report_marks_snapshot_without_review_as_pending() -> None:
    report = build_governance_ledger_report(
        (_entry(1, GovernanceLedgerEventType.SNAPSHOT_RECORDED, minute=0),),
        change_set_id="change-1",
        policy_version="v2",
    )

    assert report.pending_human_review is True
    assert report.review_sequence is None
    assert report.entry_count == 1
    assert report.automatically_changed is False


def test_report_links_snapshot_and_human_review() -> None:
    entries = (
        _entry(1, GovernanceLedgerEventType.SNAPSHOT_RECORDED, minute=0),
        _entry(
            2,
            GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED,
            minute=5,
            decision="keep_active",
            actor="mahmod",
        ),
    )

    report = build_governance_ledger_report(
        entries,
        change_set_id="change-1",
        policy_version="v2",
    )

    assert report.pending_human_review is False
    assert report.review_sequence == 2
    assert report.review_decision == "keep_active"
    assert report.review_actor == "mahmod"
    assert report.first_sequence == 1
    assert report.last_sequence == 2


def test_report_filters_other_policy_versions() -> None:
    entries = (
        _entry(1, GovernanceLedgerEventType.SNAPSHOT_RECORDED, minute=0),
        _entry(
            2,
            GovernanceLedgerEventType.SNAPSHOT_RECORDED,
            minute=1,
            change_set_id="change-2",
            policy_version="v3",
        ),
    )

    report = build_governance_ledger_report(
        entries,
        change_set_id="change-2",
        policy_version="v3",
    )

    assert report.change_set_id == "change-2"
    assert report.snapshot_sequence == 2
    assert report.entry_count == 1


def test_report_rejects_missing_snapshot() -> None:
    entries = (
        _entry(
            1,
            GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED,
            minute=0,
            decision="keep_active",
            actor="reviewer",
        ),
    )

    with pytest.raises(ValueError, match="exactly one matching snapshot"):
        build_governance_ledger_report(
            entries,
            change_set_id="change-1",
            policy_version="v2",
        )


def test_report_rejects_non_contiguous_ledger() -> None:
    entries = (
        _entry(2, GovernanceLedgerEventType.SNAPSHOT_RECORDED, minute=0),
    )

    with pytest.raises(ValueError, match="contiguous"):
        build_governance_ledger_report(
            entries,
            change_set_id="change-1",
            policy_version="v2",
        )


def test_report_rejects_mismatched_rule() -> None:
    entries = (
        _entry(1, GovernanceLedgerEventType.SNAPSHOT_RECORDED, minute=0),
        _entry(
            2,
            GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED,
            minute=5,
            decision="keep_active",
            actor="reviewer",
            rule_name="different_rule",
        ),
    )

    with pytest.raises(ValueError, match="same rule"):
        build_governance_ledger_report(
            entries,
            change_set_id="change-1",
            policy_version="v2",
        )
