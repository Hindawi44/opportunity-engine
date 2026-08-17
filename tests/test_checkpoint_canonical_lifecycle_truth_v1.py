from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    build_multi_market_checkpoint,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _empty_source(root: Path, name: str, market: str, currency: str) -> dict:
    directory = root / name
    _write(directory / "execution-status.json", {"exit_code": 0})
    _write(
        directory / "search-run-report.json",
        {
            "status": "PASS",
            "market_code": market,
            "currency": currency,
            "currency_conversion_performed": False,
        },
    )
    _write(directory / "all-discovered-candidates.json", [])
    _write(directory / "discovery-top5.json", [])
    _write(
        directory / "unified-opportunity-report.json",
        {
            "record_count": 0,
            "conversion_error_count": 0,
            "records": [],
        },
    )
    return {
        "market_code": market,
        "source_name": name,
        "currency": currency,
        "artifact_dir": name,
    }


def _matrix() -> dict:
    return {
        "markets": [
            {"market_code": "NO", "sources": []},
            {"market_code": "SE", "sources": []},
            {"market_code": "DE", "sources": []},
        ]
    }


def _auksjonen_source(
    root: Path,
    *,
    candidate: dict,
    canonical: dict,
) -> dict:
    directory = root / "no-auksjonen"
    _write(directory / "execution-status.json", {"exit_code": 0})
    _write(
        directory / "auksjonen-live-clothing-listings.json",
        {"scan_complete": True, "errors": [], "listings": []},
    )
    _write(directory / "all-discovered-candidates.json", [candidate])
    _write(directory / "live-clothing-top5.json", [candidate])
    _write(
        directory / "unified-opportunity-report.json",
        {
            "record_count": 1,
            "conversion_error_count": 0,
            "records": [canonical],
        },
    )
    return {
        "market_code": "NO",
        "source_name": "Auksjonen.no",
        "currency": "NOK",
        "artifact_dir": "no-auksjonen",
        "report_kind": "AUKSJONEN_LIVE",
        "report_file": "auksjonen-live-clothing-listings.json",
        "top5_file": "live-clothing-top5.json",
    }


def _report(root: Path, no_source: dict) -> dict:
    se_source = _empty_source(root, "se-empty", "SE", "SEK")
    de_source = _empty_source(root, "de-empty", "DE", "EUR")
    return build_multi_market_checkpoint(
        {"sources": [no_source, se_source, de_source]},
        _matrix(),
        root=root,
        generated_at="2026-08-17T20:00:00+00:00",
    )


def test_checkpoint_consumes_canonical_lifecycle_eligibility(tmp_path: Path) -> None:
    identity = "https://auksjonen.no/auksjon/halv-pall-bauer-jakker/123"
    candidate = {
        "title": "Halv pall med Bauer jakker",
        "opportunity_identity": identity,
        "listing_status": "ACTIVE",
        "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
        "top5_eligible": True,
        # Deliberately inconsistent discovery-layer flag. The canonical lifecycle
        # record below is the only authority the checkpoint may consume.
        "analysis_eligible": True,
        "verified": False,
        "missing_information": ["verified exact item-page evidence"],
        "source_urls": [identity],
    }
    canonical = {
        "opportunity_id": identity,
        "listing_status": "ACTIVE",
        "workflow_status": "REQUIRES_VERIFICATION",
        "evaluation_status": "REQUIRES_VERIFICATION",
        "verified": False,
        "top5_eligible": True,
        "analysis_eligible": False,
        "metadata": {"lifecycle_reason_code": "MISSING_REQUIRED_VERIFICATION"},
    }

    report = _report(
        tmp_path,
        _auksjonen_source(tmp_path, candidate=candidate, canonical=canonical),
    )
    record = report["deduplicated_opportunities"][0]

    assert record["listing_status"] == "ACTIVE"
    assert record["top5_eligible"] is True
    assert record["analysis_eligible"] is False
    assert report["analysis_eligible_count"] == 0


def test_checkpoint_does_not_invent_blockers_for_canonical_analysis_ready_lot(
    tmp_path: Path,
) -> None:
    identity = "https://auksjonen.no/auksjon/halv-pall-bauer-jakker/456"
    candidate = {
        "title": "Halv pall med Bauer jakker",
        "opportunity_identity": identity,
        "listing_status": "ACTIVE",
        "opportunity_state": "ACTIVE_OPPORTUNITY",
        "top5_eligible": True,
        "analysis_eligible": True,
        "verified": True,
        "missing_information": [],
        "verification_blockers": [],
        "quantity": 12,
        "condition": "USED",
        "price_nok": 250,
        "source_urls": [identity],
    }
    canonical = {
        "opportunity_id": identity,
        "listing_status": "ACTIVE",
        "workflow_status": "ACTIVE_OPPORTUNITY",
        "evaluation_status": "NOT_EVALUATED",
        "verified": True,
        "top5_eligible": True,
        "analysis_eligible": True,
        "metadata": {"lifecycle_reason_code": "ACTIVE_READY_FOR_ANALYSIS"},
    }

    report = _report(
        tmp_path,
        _auksjonen_source(tmp_path, candidate=candidate, canonical=canonical),
    )
    record = report["deduplicated_opportunities"][0]

    assert record["analysis_eligible"] is True
    assert record["top5_eligible"] is True
    assert record["missing_evidence"] == []
    assert report["analysis_eligible_count"] == 1
