from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from opportunity_engine.discovery.checkpoint_state_restore import (
    extract_previous_databases,
)
from opportunity_engine.discovery.domain_market_intelligence_feed import (
    persist_manifest_market_signals,
)
from opportunity_engine.discovery.finn_email_intake import (
    FinnEmailMessage,
    collect_finn_saved_search_messages,
    run_finn_email_intake,
    write_finn_email_intake_artifacts,
)
from opportunity_engine.discovery.source_artifact_continuity import (
    ensure_source_artifact_continuity,
)


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = ROOT / "alembic.ini"
FINN_URL = "https://www.finn.no/471396147"


def _write_finn_run(
    output_dir: Path,
    *,
    price_nok: int,
    received_at: str,
    ingested_at: str,
    message_id: str,
) -> None:
    message = FinnEmailMessage(
        sender="FINN <agent@finn.no>",
        subject="Nye annonser: vareparti klær",
        body=(
            f"[Restlager arbeidsklær selges samlet]({FINN_URL})\n\n"
            f"{price_nok} kr Oslo\n"
        ),
        received_at=received_at,
        message_id=message_id,
    )
    collection = collect_finn_saved_search_messages(
        [message],
        ingested_at=ingested_at,
    )
    result = run_finn_email_intake(collection)
    write_finn_email_intake_artifacts(result, collection, output_dir)


def _reset_generated_continuity_artifacts(output_dir: Path) -> None:
    for name in (
        "unified-opportunity-report.json",
        "unified-persistence-summary.json",
        "market-signal-report.json",
    ):
        (output_dir / name).unlink(missing_ok=True)


def _manifest() -> dict:
    return {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "FINN saved-search email",
                "artifact_dir": "multi-market-inputs/no-finn-email",
            }
        ]
    }


def test_finn_source_uses_existing_canonical_and_signal_persistence(tmp_path: Path) -> None:
    output_dir = tmp_path / "multi-market-inputs" / "no-finn-email"
    output_dir.mkdir(parents=True)
    first_seen = "2026-08-04T18:00:00+00:00"
    first_run = "2026-08-05T06:30:00+00:00"
    second_run = "2026-08-06T06:30:00+00:00"

    _write_finn_run(
        output_dir,
        price_nok=10000,
        received_at=first_seen,
        ingested_at=first_run,
        message_id="<first-message@example.test>",
    )
    continuity = ensure_source_artifact_continuity(
        output_dir,
        config_path=ALEMBIC_CONFIG,
    )

    assert continuity["status"] == "SUCCESS"
    assert continuity["canonical_persistence_created"] is True
    assert continuity["market_signal_count"] == 1
    assert (output_dir / "opportunity_engine.db").exists()
    unified = json.loads(
        (output_dir / "unified-opportunity-report.json").read_text(encoding="utf-8")
    )
    assert unified["record_count"] == 1
    signal_report = json.loads(
        (output_dir / "market-signal-report.json").read_text(encoding="utf-8")
    )
    signal = signal_report["signals"][0]
    assert signal["signal_id"] == "finn-listing:471396147"
    assert signal["metadata"]["advertised_price_nok"] == 10000.0
    assert "message_fingerprint" not in json.dumps(signal)

    first_persistence = persist_manifest_market_signals(
        _manifest(),
        root=tmp_path,
        config_path=ALEMBIC_CONFIG,
    )
    assert first_persistence["created_signal_ids"] == [
        "finn-listing:471396147"
    ]

    _reset_generated_continuity_artifacts(output_dir)
    _write_finn_run(
        output_dir,
        price_nok=10000,
        received_at="2026-08-05T18:00:00+00:00",
        ingested_at=second_run,
        message_id="<second-message@example.test>",
    )
    ensure_source_artifact_continuity(
        output_dir,
        config_path=ALEMBIC_CONFIG,
    )
    replay = persist_manifest_market_signals(
        _manifest(),
        root=tmp_path,
        config_path=ALEMBIC_CONFIG,
    )

    assert replay["created_signal_ids"] == []
    assert replay["changed_signal_ids"] == []
    current = replay["current_signals"][0]
    assert current["first_observed_at"] == first_seen
    assert current["latest_observed_at"] == second_run

    _reset_generated_continuity_artifacts(output_dir)
    _write_finn_run(
        output_dir,
        price_nok=12500,
        received_at="2026-08-06T18:00:00+00:00",
        ingested_at="2026-08-07T06:30:00+00:00",
        message_id="<third-message@example.test>",
    )
    ensure_source_artifact_continuity(
        output_dir,
        config_path=ALEMBIC_CONFIG,
    )
    changed = persist_manifest_market_signals(
        _manifest(),
        root=tmp_path,
        config_path=ALEMBIC_CONFIG,
    )

    assert changed["changed_signal_ids"] == ["finn-listing:471396147"]
    assert changed["current_signals"][0]["metadata"]["advertised_price_nok"] == 12500.0


def test_restore_allowlist_includes_finn_signal_database(tmp_path: Path) -> None:
    archive_buffer = BytesIO()
    member = "multi-market-inputs/no-finn-email/opportunity_engine.db"
    with ZipFile(archive_buffer, "w") as archive:
        archive.writestr(member, b"SQLite format 3\x00" + b"fixture")

    restored = extract_previous_databases(archive_buffer.getvalue(), tmp_path)

    assert restored == [
        {
            "archive_member": member,
            "relative_path": (
                tmp_path / "no-finn-email" / "opportunity_engine.db"
            ).as_posix(),
        }
    ]
    assert (tmp_path / "no-finn-email" / "opportunity_engine.db").exists()
