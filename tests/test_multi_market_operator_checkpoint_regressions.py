from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    build_multi_market_checkpoint,
)


EXPECTED_AUKSJONEN_EVIDENCE = (
    "verified exact item-page evidence",
    "verified quantity and condition",
    "documented final payable price including auction fees and VAT",
    "domestic pickup or delivery logistics basis",
    "documented resale-market evidence",
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _canonical_record(candidate: dict) -> dict:
    identity = candidate.get("opportunity_identity") or candidate.get("url")
    listing_status = str(candidate.get("listing_status") or "ACTIVE").upper()
    historical = listing_status in {"ENDED", "HISTORICAL"} or (
        candidate.get("opportunity_state") == "HISTORICAL_MARKET_EVIDENCE"
    )
    return {
        "opportunity_id": identity,
        "listing_status": listing_status,
        "workflow_status": (
            "HISTORICAL_MARKET_EVIDENCE" if historical else "CANDIDATE"
        ),
        "evaluation_status": "HISTORICAL_ONLY" if historical else "HOLD_WATCHLIST",
        "top5_eligible": False if historical else bool(candidate.get("top5_eligible")),
        "analysis_eligible": False if historical else bool(candidate.get("analysis_eligible")),
        "metadata": {
            "lifecycle_reason_code": (
                "HISTORICAL_INACTIVE_LISTING" if historical else "CANDIDATE_DISCOVERED"
            )
        },
    }


def _standard_source(
    root: Path,
    name: str,
    *,
    market: str,
    currency: str,
    candidates: list[dict],
    top5: list[dict] | None = None,
) -> dict:
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
    _write(directory / "all-discovered-candidates.json", candidates)
    _write(directory / "discovery-top5.json", top5 or [])
    _write(
        directory / "unified-opportunity-report.json",
        {
            "market_code": market,
            "currency": currency,
            "record_count": len(candidates),
            "conversion_error_count": 0,
            "records": [_canonical_record(item) for item in candidates],
        },
    )
    _write(
        directory / "unified-persistence-summary.json",
        {"status": "SUCCESS", "persisted_record_count": len(candidates)},
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


def test_blinto_opportunity_state_is_historical_and_cannot_enter_top5(
    tmp_path: Path,
) -> None:
    no_source = _standard_source(
        tmp_path,
        "no-zero",
        market="NO",
        currency="NOK",
        candidates=[],
    )
    historical = {
        "opportunity_identity": "blinto-auction:178629:85260",
        "title": "Arbetskläder - Blåkläder",
        "listing_status": "ENDED",
        "opportunity_state": "HISTORICAL_MARKET_EVIDENCE",
        "top5_eligible": True,
    }
    se_source = _standard_source(
        tmp_path,
        "se-blinto",
        market="SE",
        currency="SEK",
        candidates=[historical],
        top5=[historical],
    )
    de_source = _standard_source(
        tmp_path,
        "de-zero",
        market="DE",
        currency="EUR",
        candidates=[],
    )

    report = build_multi_market_checkpoint(
        {"sources": [no_source, se_source, de_source]},
        _matrix(),
        root=tmp_path,
    )

    record = report["deduplicated_opportunities"][0]
    assert record["listing_status"] == "HISTORICAL"
    assert record["top5_eligible"] is False
    assert report["status_counts"]["HISTORICAL"] == 1
    assert report["status_counts"]["ENDED"] == 0
    assert report["top5_eligible_count"] == 0


def test_auksjonen_top5_record_explains_analysis_ineligibility(tmp_path: Path) -> None:
    directory = tmp_path / "no-auksjonen"
    _write(directory / "execution-status.json", {"exit_code": 0})
    active = {
        "title": "10 stk GSA multinorm arbeidsplagg",
        "url": "https://example.test/no/528194",
        "object_id": 528194,
        "listing_status": "ACTIVE",
        "inventory_lot_signal": True,
        "current_bid_nok": 5000,
        "missing_evidence": list(EXPECTED_AUKSJONEN_EVIDENCE),
    }
    _write(
        directory / "auksjonen-live-clothing-listings.json",
        {"scan_complete": True, "errors": [], "listings": [active]},
    )
    _write(directory / "live-clothing-top5.json", [active])
    _write(
        directory / "unified-opportunity-report.json",
        {
            "record_count": 1,
            "conversion_error_count": 0,
            "records": [
                {
                    "opportunity_id": active["url"],
                    "listing_status": "ACTIVE",
                    "workflow_status": "REQUIRES_VERIFICATION",
                    "evaluation_status": "HOLD_WATCHLIST",
                    "top5_eligible": True,
                    "analysis_eligible": False,
                    "metadata": {
                        "lifecycle_reason_code": "MISSING_REQUIRED_VERIFICATION"
                    },
                }
            ],
        },
    )
    no_source = {
        "market_code": "NO",
        "source_name": "Auksjonen.no",
        "currency": "NOK",
        "artifact_dir": "no-auksjonen",
        "report_kind": "AUKSJONEN_LIVE",
        "report_file": "auksjonen-live-clothing-listings.json",
        "top5_file": "live-clothing-top5.json",
    }
    se_source = _standard_source(
        tmp_path,
        "se-zero",
        market="SE",
        currency="SEK",
        candidates=[],
    )
    de_source = _standard_source(
        tmp_path,
        "de-zero",
        market="DE",
        currency="EUR",
        candidates=[],
    )

    report = build_multi_market_checkpoint(
        {"sources": [no_source, se_source, de_source]},
        _matrix(),
        root=tmp_path,
    )

    record = report["deduplicated_opportunities"][0]
    assert record["top5_eligible"] is True
    assert record["analysis_eligible"] is False
    assert record["missing_evidence"] == sorted(EXPECTED_AUKSJONEN_EVIDENCE)
    assert set(EXPECTED_AUKSJONEN_EVIDENCE).issubset(report["missing_evidence"])
    assert report["next_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
