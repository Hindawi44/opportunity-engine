from __future__ import annotations

import pytest

from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    CheckpointIntegrityError,
    _apply_canonical_lifecycle,
    _merge_records,
)


def _candidate(identity: str = "opp-1") -> dict:
    return {
        "opportunity_identity": identity,
        "title": "Fixture lot",
        "listing_status": "ACTIVE",
        "top5_eligible": True,
        "analysis_eligible": True,
        "missing_evidence": [],
    }


def _canonical(identity: str = "opp-1", **overrides) -> dict:
    record = {
        "opportunity_id": identity,
        "listing_status": "ACTIVE",
        "workflow_status": "ACTIVE_OPPORTUNITY",
        "evaluation_status": "NOT_EVALUATED",
        "top5_eligible": True,
        "analysis_eligible": True,
        "metadata": {"lifecycle_reason_code": "ACTIVE_READY_FOR_ANALYSIS"},
    }
    record.update(overrides)
    return record


def _source_run(record: dict, *, source_name: str = "Fixture") -> dict:
    return {
        "source_name": source_name,
        "market_code": "NO",
        "currency": "NOK",
        "records": [record],
        "top5_records": [],
    }


def test_checkpoint_rejects_candidate_missing_from_canonical_lifecycle() -> None:
    records = [_candidate()]

    with pytest.raises(
        CheckpointIntegrityError,
        match=r"missing canonical lifecycle truth.*opp-1",
    ):
        _apply_canonical_lifecycle(
            records,
            source_name="Fixture",
            unified={"records": []},
        )


def test_checkpoint_rejects_incomplete_canonical_eligibility() -> None:
    records = [_candidate()]
    canonical = _canonical()
    canonical.pop("analysis_eligible")

    with pytest.raises(
        CheckpointIntegrityError,
        match=r"incomplete canonical lifecycle truth.*opp-1.*analysis_eligible",
    ):
        _apply_canonical_lifecycle(
            records,
            source_name="Fixture",
            unified={"records": [canonical]},
        )


def test_merge_rejects_noncanonical_record_instead_of_legacy_derivation() -> None:
    with pytest.raises(
        CheckpointIntegrityError,
        match=r"missing canonical lifecycle truth.*opp-1",
    ):
        _merge_records([_source_run(_candidate())])


def test_merge_rejects_conflicting_canonical_eligibility() -> None:
    first = _candidate()
    first["_canonical_lifecycle_present"] = True
    second = _candidate()
    second["_canonical_lifecycle_present"] = True
    second["analysis_eligible"] = False

    with pytest.raises(
        CheckpointIntegrityError,
        match=r"conflicting canonical lifecycle truth.*opp-1",
    ):
        _merge_records(
            [
                _source_run(first, source_name="Fixture A"),
                _source_run(second, source_name="Fixture B"),
            ]
        )
