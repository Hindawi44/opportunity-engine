from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.decision_policy_governance import (
    DecisionPolicyGovernanceSnapshot,
)
from opportunity_engine.ods.decision_policy_governance_ledger import (
    DecisionPolicyGovernanceLedgerEntry,
    GovernanceLedgerEventType,
    append_governance_review_entry,
    append_governance_snapshot_entry,
)
from opportunity_engine.ods.decision_policy_governance_review import (
    DecisionPolicyGovernanceReview,
    GovernanceReviewDecision,
)


def _snapshot() -> DecisionPolicyGovernanceSnapshot:
    return DecisionPolicyGovernanceSnapshot(
        change_set_id="change-1",
        rule_name="minimum_confidence",
        active_version="v2",
        lifecycle_status="active",
        effectiveness_status="healthy",
        recommendation="keep_active",
        requires_human_review=False,
        rolled_back=False,
        restored_version=None,
    )


def _review(reviewed_at: datetime) -> DecisionPolicyGovernanceReview:
    return DecisionPolicyGovernanceReview(
        change_set_id="change-1",
        rule_name="minimum_confidence",
        reviewed_version="v2",
        lifecycle_status="active",
        decision=GovernanceReviewDecision.KEEP_ACTIVE,
        reviewed_by="Mahmoud",
        reviewed_at=reviewed_at,
        notes="Evidence supports keeping this policy active.",
    )


def test_ledger_records_snapshot_then_human_review() -> None:
    snapshot_at = datetime(2026, 7, 19, 16, 30, tzinfo=timezone.utc)
    review_at = datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc)

    ledger = append_governance_snapshot_entry(_snapshot(), recorded_at=snapshot_at)
    ledger = append_governance_review_entry(_review(review_at), existing_entries=ledger)

    assert [item.sequence for item in ledger] == [1, 2]
    assert ledger[0].event_type is GovernanceLedgerEventType.SNAPSHOT_RECORDED
    assert ledger[0].actor == "system"
    assert ledger[1].event_type is GovernanceLedgerEventType.HUMAN_REVIEW_RECORDED
    assert ledger[1].actor == "Mahmoud"
    assert ledger[1].decision == "keep_active"
    assert all(item.automatically_changed is False for item in ledger)


def test_review_requires_matching_snapshot() -> None:
    review_at = datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="matching recorded governance snapshot"):
        append_governance_review_entry(_review(review_at), existing_entries=())


def test_duplicate_snapshot_and_review_are_rejected() -> None:
    snapshot_at = datetime(2026, 7, 19, 16, 30, tzinfo=timezone.utc)
    review_at = datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc)
    ledger = append_governance_snapshot_entry(_snapshot(), recorded_at=snapshot_at)

    with pytest.raises(ValueError, match="snapshot is already recorded"):
        append_governance_snapshot_entry(
            _snapshot(), recorded_at=review_at, existing_entries=ledger
        )

    ledger = append_governance_review_entry(_review(review_at), existing_entries=ledger)
    with pytest.raises(ValueError, match="review is already recorded"):
        append_governance_review_entry(_review(review_at), existing_entries=ledger)


def test_review_cannot_precede_snapshot() -> None:
    snapshot_at = datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc)
    review_at = datetime(2026, 7, 19, 16, 30, tzinfo=timezone.utc)
    ledger = append_governance_snapshot_entry(_snapshot(), recorded_at=snapshot_at)

    with pytest.raises(ValueError, match="cannot precede"):
        append_governance_review_entry(_review(review_at), existing_entries=ledger)


def test_ledger_rejects_non_contiguous_existing_sequence() -> None:
    recorded_at = datetime(2026, 7, 19, 16, 30, tzinfo=timezone.utc)
    malformed = DecisionPolicyGovernanceLedgerEntry(
        sequence=2,
        change_set_id="change-1",
        rule_name="minimum_confidence",
        policy_version="v2",
        lifecycle_status="active",
        event_type=GovernanceLedgerEventType.SNAPSHOT_RECORDED,
        recorded_at=recorded_at,
        actor="system",
        decision=None,
        notes="Recorded snapshot.",
    )

    with pytest.raises(ValueError, match="contiguous sequence"):
        append_governance_snapshot_entry(
            _snapshot(), recorded_at=recorded_at, existing_entries=(malformed,)
        )


def test_ledger_never_allows_automatic_policy_change() -> None:
    with pytest.raises(ValueError, match="cannot change policy automatically"):
        DecisionPolicyGovernanceLedgerEntry(
            sequence=1,
            change_set_id="change-1",
            rule_name="minimum_confidence",
            policy_version="v2",
            lifecycle_status="active",
            event_type=GovernanceLedgerEventType.SNAPSHOT_RECORDED,
            recorded_at=datetime(2026, 7, 19, 16, 30, tzinfo=timezone.utc),
            actor="system",
            decision=None,
            notes="Recorded snapshot.",
            automatically_changed=True,
        )
