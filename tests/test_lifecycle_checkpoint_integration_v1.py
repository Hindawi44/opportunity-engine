from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

from opportunity_engine.discovery.checkpoint_state_restore import (
    extract_previous_databases,
)
from opportunity_engine.discovery.lifecycle_checkpoint_integration import (
    enrich_checkpoint_with_lifecycle,
    render_lifecycle_phone_summary,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _create_lifecycle_database(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE lifecycle_events (
                id INTEGER PRIMARY KEY,
                opportunity_id TEXT NOT NULL,
                from_listing_status TEXT,
                to_listing_status TEXT NOT NULL,
                from_evaluation_status TEXT,
                to_evaluation_status TEXT NOT NULL,
                from_workflow_status TEXT,
                to_workflow_status TEXT NOT NULL,
                from_reason_code TEXT,
                to_reason_code TEXT,
                source_ref TEXT,
                changed_at TEXT NOT NULL
            )
            """
        )
        for event in events:
            connection.execute(
                """
                INSERT INTO lifecycle_events (
                    opportunity_id,
                    from_listing_status, to_listing_status,
                    from_evaluation_status, to_evaluation_status,
                    from_workflow_status, to_workflow_status,
                    from_reason_code, to_reason_code,
                    source_ref, changed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["opportunity_id"],
                    event.get("from_listing_status"),
                    event["to_listing_status"],
                    event.get("from_evaluation_status"),
                    event["to_evaluation_status"],
                    event.get("from_workflow_status"),
                    event["to_workflow_status"],
                    event.get("from_reason_code"),
                    event.get("to_reason_code"),
                    event.get("source_ref"),
                    event["changed_at"],
                ),
            )
        connection.commit()
    finally:
        connection.close()


def _base_report(records: list[dict]) -> dict:
    return {
        "schema_version": "multi-market-operator-checkpoint-1.0",
        "generated_at": "2026-08-03T06:00:00+00:00",
        "source_execution_counts": {"SUCCESS": 2, "VALID_ZERO_RESULT": 1},
        "status_counts": {
            "ACTIVE": sum(item["listing_status"] == "ACTIVE" for item in records),
            "UPCOMING": 0,
            "HISTORICAL": sum(
                item["listing_status"] == "HISTORICAL" for item in records
            ),
            "ENDED": sum(item["listing_status"] == "ENDED" for item in records),
            "UNRESOLVED": 0,
        },
        "deduplicated_record_count": len(records),
        "deduplicated_opportunities": records,
        "top5_eligible_count": sum(item.get("top5_eligible") is True for item in records),
        "analysis_eligible_count": sum(
            item.get("analysis_eligible") is True for item in records
        ),
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": records[0]["opportunity_identity"],
            "reason": "old wording",
        },
    }


def test_enrichment_adds_stage_counts_and_initial_events(tmp_path: Path) -> None:
    records = [
        {
            "opportunity_identity": "no:1",
            "title": "Norwegian active lot",
            "listing_status": "ACTIVE",
            "top5_eligible": True,
            "analysis_eligible": False,
            "missing_evidence": ["final price"],
        },
        {
            "opportunity_identity": "se:old",
            "title": "Historical Swedish lot",
            "listing_status": "HISTORICAL",
            "top5_eligible": False,
            "analysis_eligible": False,
            "missing_evidence": [],
        },
    ]
    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "no",
            },
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": "se",
            },
            {
                "market_code": "DE",
                "source_name": "VENTA",
                "artifact_dir": "de",
            },
        ]
    }
    _write_json(
        tmp_path / "se" / "unified-opportunity-report.json",
        {
            "records": [
                {
                    "opportunity_id": "se:old",
                    "listing_status": "ENDED",
                    "evaluation_status": "HISTORICAL_ONLY",
                    "workflow_status": "HISTORICAL_MARKET_EVIDENCE",
                    "metadata": {
                        "lifecycle_reason_code": "HISTORICAL_INACTIVE_LISTING"
                    },
                }
            ]
        },
    )
    _write_json(
        tmp_path / "se" / "unified-persistence-summary.json",
        {"status": "SUCCESS", "lifecycle_events_created": 1},
    )
    _create_lifecycle_database(
        tmp_path / "se" / "opportunity_engine.db",
        [
            {
                "opportunity_id": "se:old",
                "to_listing_status": "ENDED",
                "to_evaluation_status": "HISTORICAL_ONLY",
                "to_workflow_status": "HISTORICAL_MARKET_EVIDENCE",
                "to_reason_code": "HISTORICAL_INACTIVE_LISTING",
                "changed_at": "2026-08-03T06:00:00+00:00",
            }
        ],
    )

    enriched = enrich_checkpoint_with_lifecycle(
        _base_report(records),
        manifest,
        root=tmp_path,
        restore_status={"status": "NO_PREVIOUS_STATE", "restored_databases": []},
    )

    assert enriched["schema_version"] == "multi-market-operator-checkpoint-1.1"
    stages = enriched["lifecycle"]["stage_counts"]
    assert stages["REQUIRES_VERIFICATION"] == 1
    assert stages["HISTORICAL_MARKET_EVIDENCE"] == 1
    transitions = enriched["lifecycle"]["transitions"]
    assert transitions["initial_snapshots_created_this_run"] == 1
    assert transitions["transitions_created_this_run"] == 0
    assert enriched["lifecycle"]["persistence"]["cross_run_continuity"] is False
    assert enriched["next_human_action"]["workflow_status"] == "REQUIRES_VERIFICATION"
    assert "requires human verification" in enriched["next_human_action"]["reason"]
    summary = render_lifecycle_phone_summary(enriched)
    assert "دورة الحياة:" in summary
    assert summary.count("الإجراء البشري الوحيد:") == 1


def test_enrichment_reports_real_cross_run_promotion(tmp_path: Path) -> None:
    record = {
        "opportunity_identity": "de:1",
        "title": "German active lot",
        "listing_status": "ACTIVE",
        "top5_eligible": True,
        "analysis_eligible": True,
        "missing_evidence": [],
    }
    manifest = {
        "sources": [
            {
                "market_code": "DE",
                "source_name": "Riegermann",
                "artifact_dir": "de-riegermann",
            }
        ]
    }
    _write_json(
        tmp_path / "de-riegermann" / "unified-opportunity-report.json",
        {
            "records": [
                {
                    "opportunity_id": "de:1",
                    "listing_status": "ACTIVE",
                    "evaluation_status": "NOT_EVALUATED",
                    "workflow_status": "ACTIVE_OPPORTUNITY",
                    "metadata": {"lifecycle_reason_code": "ACTIVE_READY_FOR_ANALYSIS"},
                }
            ]
        },
    )
    _write_json(
        tmp_path / "de-riegermann" / "unified-persistence-summary.json",
        {"status": "SUCCESS", "lifecycle_events_created": 1},
    )
    _create_lifecycle_database(
        tmp_path / "de-riegermann" / "opportunity_engine.db",
        [
            {
                "opportunity_id": "de:1",
                "to_listing_status": "ACTIVE",
                "to_evaluation_status": "REQUIRES_VERIFICATION",
                "to_workflow_status": "REQUIRES_VERIFICATION",
                "to_reason_code": "MISSING_REQUIRED_VERIFICATION",
                "changed_at": "2026-08-02T06:00:00+00:00",
            },
            {
                "opportunity_id": "de:1",
                "from_listing_status": "ACTIVE",
                "to_listing_status": "ACTIVE",
                "from_evaluation_status": "REQUIRES_VERIFICATION",
                "to_evaluation_status": "NOT_EVALUATED",
                "from_workflow_status": "REQUIRES_VERIFICATION",
                "to_workflow_status": "ACTIVE_OPPORTUNITY",
                "from_reason_code": "MISSING_REQUIRED_VERIFICATION",
                "to_reason_code": "ACTIVE_READY_FOR_ANALYSIS",
                "changed_at": "2026-08-03T06:00:00+00:00",
            },
        ],
    )
    restored_path = "de-riegermann/opportunity_engine.db"
    enriched = enrich_checkpoint_with_lifecycle(
        _base_report([record]),
        manifest,
        root=tmp_path,
        restore_status={
            "status": "RESTORED",
            "restored_databases": [{"relative_path": restored_path}],
        },
    )

    lifecycle = enriched["lifecycle"]
    assert lifecycle["stage_counts"]["ACTIVE_OPPORTUNITY"] == 1
    assert lifecycle["transitions"]["transitions_created_this_run"] == 1
    assert lifecycle["transitions"]["promoted_count"] == 1
    assert lifecycle["persistence"]["cross_run_continuity"] is True
    assert (
        lifecycle["persistence"]["comparison_scope"]
        == "SINCE_PREVIOUS_SUCCESSFUL_CHECKPOINT"
    )


def test_restore_extracts_only_allowlisted_sqlite_files(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    connection = sqlite3.connect(source_db)
    connection.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w") as archive:
        archive.writestr(
            "multi-market-inputs/se-blinto/opportunity_engine.db",
            source_db.read_bytes(),
        )
        archive.writestr("unrelated/secret.txt", b"must not be extracted")

    destination = tmp_path / "restored"
    restored = extract_previous_databases(archive_buffer.getvalue(), destination)

    assert restored == [
        {
            "archive_member": "multi-market-inputs/se-blinto/opportunity_engine.db",
            "relative_path": (destination / "se-blinto/opportunity_engine.db").as_posix(),
        }
    ]
    assert (destination / "se-blinto/opportunity_engine.db").exists()
    assert not (destination / "unrelated/secret.txt").exists()
