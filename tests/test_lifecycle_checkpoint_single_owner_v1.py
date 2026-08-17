import json

import pytest

from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    LifecycleCheckpointIntegrityError,
    enrich_checkpoint_with_lifecycle,
)


def _manifest_with_unified(tmp_path, records):
    artifact_dir = tmp_path / "source"
    artifact_dir.mkdir()
    (artifact_dir / "unified-opportunity-report.json").write_text(
        json.dumps({"records": records}),
        encoding="utf-8",
    )
    return {
        "sources": [
            {
                "source_name": "fixture-source",
                "market_code": "NO",
                "artifact_dir": "source",
            }
        ]
    }


def _checkpoint_record(identity="opp-1"):
    return {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": identity,
                "listing_status": "ACTIVE",
                "top5_eligible": True,
                "analysis_eligible": True,
                "workflow_status": "QUALIFIED_OPPORTUNITY",
                "evaluation_status": "ACTIONABLE",
                "lifecycle_reason_code": "LOCAL_REDERIVATION_MUST_NOT_WIN",
            }
        ]
    }


def test_lifecycle_checkpoint_uses_only_canonical_lifecycle_truth(tmp_path):
    manifest = _manifest_with_unified(
        tmp_path,
        [
            {
                "opportunity_id": "opp-1",
                "workflow_status": "REQUIRES_VERIFICATION",
                "evaluation_status": "HOLD_WATCHLIST",
                "metadata": {"lifecycle_reason_code": "MISSING_REQUIRED_EVIDENCE"},
            }
        ],
    )

    enriched = enrich_checkpoint_with_lifecycle(
        _checkpoint_record(),
        manifest,
        root=tmp_path,
    )

    record = enriched["deduplicated_opportunities"][0]
    assert record["workflow_status"] == "REQUIRES_VERIFICATION"
    assert record["evaluation_status"] == "HOLD_WATCHLIST"
    assert record["lifecycle_reason_code"] == "MISSING_REQUIRED_EVIDENCE"


def test_lifecycle_checkpoint_rejects_missing_canonical_truth(tmp_path):
    manifest = _manifest_with_unified(tmp_path, [])

    with pytest.raises(
        LifecycleCheckpointIntegrityError,
        match=r"missing canonical lifecycle truth.*opp-1",
    ):
        enrich_checkpoint_with_lifecycle(
            _checkpoint_record(),
            manifest,
            root=tmp_path,
        )


def test_lifecycle_checkpoint_rejects_incomplete_canonical_truth(tmp_path):
    manifest = _manifest_with_unified(
        tmp_path,
        [
            {
                "opportunity_id": "opp-1",
                "workflow_status": "REQUIRES_VERIFICATION",
                "evaluation_status": "HOLD_WATCHLIST",
                "metadata": {},
            }
        ],
    )

    with pytest.raises(
        LifecycleCheckpointIntegrityError,
        match=r"incomplete canonical lifecycle truth.*opp-1",
    ):
        enrich_checkpoint_with_lifecycle(
            _checkpoint_record(),
            manifest,
            root=tmp_path,
        )
