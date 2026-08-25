from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import zipfile

from opportunity_engine.discovery.sweden_official_clothing_liquidation_anchor import (
    BOLAGSVERKET_BULK_URL,
    SCB_BULK_URL,
    collect_and_store_sweden_official_clothing_liquidation_anchors,
    collect_sweden_official_clothing_liquidation_anchors,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _zip_text(path: Path, filename: str, text: str, *, encoding: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, text.encode(encoding))


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    scb = tmp_path / "scb.zip"
    scb_text = (
        "PeOrgNr\tNamn\tForetagsnamn\tFtgstat\tNg1\n"
        "165561112222\tNordic Workwear AB\t\t1\t46420\n"
        "165563334444\tModebutiken AB\t\t1\t47711\n"
        "165565556666\tCykelhandel AB\t\t1\t47642\n"
        "165567778888\tApparel Rekonstruktion AB\t\t1\t14130\n"
        "199001011234\tPhysical Person\t\t1\t47711\n"
    )
    _zip_text(scb, "scb_bulkfil.txt", scb_text, encoding="iso-8859-1")

    bolags = tmp_path / "bolags.zip"
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "organisationsidentitet",
            "organisationsnamn",
            "pagandeAvvecklingsEllerOmstruktureringsforfarande",
        ],
        delimiter=";",
        quotechar='"',
        escapechar="\\",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(
        [
            {
                "organisationsidentitet": "5561112222$ORGNR-IDORG",
                "organisationsnamn": "Nordic Workwear AB$FORETAGSNAMN-ORGNAM$2020-01-01$",
                "pagandeAvvecklingsEllerOmstruktureringsforfarande": "KK-AVOMFO$2026-08-20",
            },
            {
                "organisationsidentitet": "5563334444$ORGNR-IDORG",
                "organisationsnamn": "Modebutiken AB$FORETAGSNAMN-ORGNAM$2020-01-01$",
                "pagandeAvvecklingsEllerOmstruktureringsforfarande": "LI-AVOMFO$Likvidation$2026-08-19",
            },
            {
                "organisationsidentitet": "5565556666$ORGNR-IDORG",
                "organisationsnamn": "Cykelhandel AB$FORETAGSNAMN-ORGNAM$2020-01-01$",
                "pagandeAvvecklingsEllerOmstruktureringsforfarande": "KK-AVOMFO$Konkurs$2026-08-18",
            },
            {
                "organisationsidentitet": "5567778888$ORGNR-IDORG",
                "organisationsnamn": "Apparel Rekonstruktion AB$FORETAGSNAMN-ORGNAM$2020-01-01$",
                "pagandeAvvecklingsEllerOmstruktureringsforfarande": "FR-AVOMFO$Företagsrekonstruktion$2026-08-17",
            },
        ]
    )
    _zip_text(bolags, "bolagsverket_bulkfil.txt", buffer.getvalue(), encoding="utf-8")
    return scb, bolags


def _downloader_for(scb: Path, bolags: Path):
    def download(url: str, destination: Path, timeout: float, max_bytes: int) -> int:
        assert timeout > 0
        source = (
            scb
            if url == SCB_BULK_URL
            else bolags
            if url == BOLAGSVERKET_BULK_URL
            else None
        )
        assert source is not None
        assert source.stat().st_size <= max_bytes
        shutil.copyfile(source, destination)
        return source.stat().st_size

    return download


def test_bulk_join_uses_ng1_and_current_kk_li_only(tmp_path: Path) -> None:
    scb, bolags = _fixtures(tmp_path)
    report = collect_sweden_official_clothing_liquidation_anchors(
        observed_at=NOW,
        downloader=_downloader_for(scb, bolags),
    )

    assert report["status"] == "SUCCESS"
    assert report["retrieval_complete"] is True
    assert report["scb_rows_scanned"] == 5
    assert report["scb_clothing_company_count"] == 3
    assert report["bolagsverket_rows_scanned"] == 4
    assert report["candidate_anchor_count"] == 2
    assert report["accepted_signal_count"] == 2
    assert report["search_requests_made"] == 0
    assert report["exa_query_budget_delta"] == 0
    assert report["anchor_is_qualification_evidence"] is False
    assert report["promotion_to_opportunity_allowed"] is False

    signals = report["signals"]
    assert {item["company_name"] for item in signals} == {
        "Nordic Workwear AB",
        "Modebutiken AB",
    }
    assert {item["metadata"]["legal_status_code"] for item in signals} == {"KK", "LI"}
    assert all(item["metadata"]["signal_only"] is True for item in signals)
    assert all(item["metadata"]["anchor_only"] is True for item in signals)
    assert all(
        item["metadata"]["anchor_is_qualification_evidence"] is False
        for item in signals
    )
    assert all(item["evidence"][0]["verified"] is True for item in signals)
    assert all(
        item["evidence"][0]["evidence_type"] == "OFFICIAL_SWEDISH_COMPANY_STATUS"
        for item in signals
    )
    nordic = next(item for item in signals if item["company_name"] == "Nordic Workwear AB")
    assert nordic["metadata"]["legal_status_text"] == "Konkurs"
    assert nordic["metadata"]["from_date"] == "2026-08-20"
    assert str(nordic["event_date"]).startswith("2026-08-20")


def test_bulk_join_merges_into_existing_sweden_signal_artifact(tmp_path: Path) -> None:
    scb, bolags = _fixtures(tmp_path)
    manifest = {
        "sources": [
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": "se-blinto",
            }
        ]
    }
    report = collect_and_store_sweden_official_clothing_liquidation_anchors(
        manifest,
        root=tmp_path,
        observed_at=NOW,
        downloader=_downloader_for(scb, bolags),
    )

    assert report["status"] == "SUCCESS"
    assert report["stored_signal_count"] == 2
    path = tmp_path / "se-blinto" / "market-signal-report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["signals"]) == 2
    assert payload["source_country"] == "SE"
    assert payload["anchor_only"] is True


def test_bulk_download_failure_is_truthful_and_safe() -> None:
    def fail(url: str, destination: Path, timeout: float, max_bytes: int) -> int:
        raise RuntimeError("network unavailable")

    report = collect_sweden_official_clothing_liquidation_anchors(
        observed_at=NOW,
        downloader=fail,
    )

    assert report["status"] == "FAILED_RETRIEVAL"
    assert report["retrieval_complete"] is False
    assert report["accepted_signal_count"] == 0
    assert report["signals"] == []
    assert report["search_requests_made"] == 0
    assert report["exa_query_budget_delta"] == 0
    assert report["automatic_purchase"] is False
