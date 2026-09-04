from __future__ import annotations

import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    CheckpointIntegrityError,
    build_multi_market_checkpoint,
    render_phone_summary,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _canonical_record(candidate: dict) -> dict:
    identity = candidate.get("opportunity_identity") or candidate.get("url")
    listing_status = str(candidate.get("listing_status") or "ACTIVE").upper()
    historical = listing_status in {"ENDED", "HISTORICAL"} or (
        candidate.get("workflow_status") == "HISTORICAL_MARKET_EVIDENCE"
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
    exit_code: int = 0,
    status: str = "PASS",
    persist: bool = True,
) -> dict:
    directory = root / name
    _write(directory / "execution-status.json", {"exit_code": exit_code})
    _write(
        directory / "search-run-report.json",
        {
            "status": status,
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
    if persist:
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
            {
                "market_code": "NO",
                "sources": [
                    {
                        "source": "FINN.no",
                        "runtime_activation_status": "BLOCKED_AUTH",
                        "activation_requirement": "official permission required",
                    }
                ],
            },
            {"market_code": "SE", "sources": []},
            {
                "market_code": "DE",
                "sources": [
                    {
                        "source": "VENTA",
                        "runtime_activation_status": "PLANNED",
                        "activation_requirement": "live clothing catalog required",
                    }
                ],
            },
        ]
    }


def test_checkpoint_covers_three_markets_and_selects_one_review_action(tmp_path: Path) -> None:
    no_dir = tmp_path / "no-auksjonen"
    _write(no_dir / "execution-status.json", {"exit_code": 0})
    active = {
        "title": "Parti med 20 arbeidsjakker",
        "url": "https://example.test/no/1",
        "object_id": 1,
        "listing_status": "ACTIVE",
        "inventory_lot_signal": True,
        "top5_eligible": True,
    }
    _write(
        no_dir / "auksjonen-live-clothing-listings.json",
        {"scan_complete": True, "errors": [], "listings": [active]},
    )
    _write(no_dir / "live-clothing-top5.json", [active])
    _write(
        no_dir / "unified-opportunity-report.json",
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

    se_source = _standard_source(
        tmp_path,
        "se-blinto",
        market="SE",
        currency="SEK",
        candidates=[
            {
                "opportunity_identity": "blinto-auction:old",
                "title": "Historiskt klädparti",
                "listing_status": "ENDED",
                "workflow_status": "HISTORICAL_MARKET_EVIDENCE",
                "top5_eligible": False,
            }
        ],
    )
    de_source = _standard_source(
        tmp_path,
        "de-venta",
        market="DE",
        currency="EUR",
        candidates=[],
    )

    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "currency": "NOK",
                "artifact_dir": "no-auksjonen",
                "report_kind": "AUKSJONEN_LIVE",
                "report_file": "auksjonen-live-clothing-listings.json",
                "top5_file": "live-clothing-top5.json",
            },
            se_source,
            de_source,
        ]
    }
    report = build_multi_market_checkpoint(
        manifest,
        _matrix(),
        root=tmp_path,
        generated_at="2026-08-02T17:45:00+00:00",
    )

    assert report["market_coverage"] == ["NO", "SE", "DE"]
    assert report["deduplicated_record_count"] == 2
    assert report["status_counts"]["ACTIVE"] == 1
    assert report["status_counts"]["HISTORICAL"] == 1
    assert report["source_execution_counts"] == {
        "SUCCESS": 2,
        "VALID_ZERO_RESULT": 1,
    }
    assert report["top5_eligible_count"] == 1
    assert report["next_human_action"]["action"] == "REVIEW_ONE_OPPORTUNITY"
    assert len(report["activation_blockers"]) == 2
    summary = render_phone_summary(report)
    assert summary.count("الإجراء البشري الوحيد:") == 1
    assert "لا شراء، لا مزايدة" in summary


def test_checkpoint_keeps_failure_distinct_from_valid_zero(tmp_path: Path) -> None:
    no_source = _standard_source(
        tmp_path,
        "no-zero",
        market="NO",
        currency="NOK",
        candidates=[],
    )
    se_source = _standard_source(
        tmp_path,
        "se-zero",
        market="SE",
        currency="SEK",
        candidates=[],
    )
    de_source = _standard_source(
        tmp_path,
        "de-failed",
        market="DE",
        currency="EUR",
        candidates=[],
        exit_code=2,
        status="FAILED",
        persist=False,
    )
    report = build_multi_market_checkpoint(
        {"sources": [no_source, se_source, de_source]},
        _matrix(),
        root=tmp_path,
    )
    assert report["source_execution_counts"]["VALID_ZERO_RESULT"] == 2
    assert report["source_execution_counts"]["FAILURE"] == 1
    assert report["next_human_action"]["action"] == "REVIEW_ONE_SOURCE_FAILURE"
    assert report["top5_eligible_count"] == 0


def test_checkpoint_connects_fr_it_nl_without_promoting_unverified_rows(
    tmp_path: Path,
) -> None:
    sources = [
        _standard_source(
            tmp_path,
            f"{market.lower()}-exa-exact-lot",
            market=market,
            currency=currency,
            candidates=[
                {
                    "opportunity_identity": f"https://example.test/{market.lower()}/lot",
                    "title": f"{market} clothing lot",
                    "listing_status": "ACTIVE",
                    "top5_eligible": True,
                    "analysis_eligible": False,
                    "missing_information": ["seller identity", "shipping terms"],
                }
            ],
        )
        for market, currency in (
            ("NO", "NOK"),
            ("SE", "SEK"),
            ("DE", "EUR"),
            ("FR", "EUR"),
            ("IT", "EUR"),
            ("NL", "EUR"),
        )
    ]

    report = build_multi_market_checkpoint(
        {"sources": sources}, _matrix(), root=tmp_path
    )

    assert report["market_coverage"] == ["NO", "SE", "DE", "FR", "IT", "NL"]
    assert [row["market_code"] for row in report["markets"]] == report["market_coverage"]
    assert report["deduplicated_record_count"] == 6
    assert report["top5_eligible_count"] == 6
    assert report["analysis_eligible_count"] == 0
    assert all(
        row["workflow_status"] == "CANDIDATE"
        and row["analysis_eligible"] is False
        for row in report["deduplicated_opportunities"]
    )


def test_checkpoint_rejects_foreign_currency_in_nok_fields(tmp_path: Path) -> None:
    no_source = _standard_source(
        tmp_path,
        "no",
        market="NO",
        currency="NOK",
        candidates=[],
    )
    se_source = _standard_source(
        tmp_path,
        "se",
        market="SE",
        currency="SEK",
        candidates=[
            {
                "opportunity_identity": "se:1",
                "listing_status": "ACTIVE",
                "price_nok": 1000,
            }
        ],
    )
    de_source = _standard_source(
        tmp_path,
        "de",
        market="DE",
        currency="EUR",
        candidates=[],
    )
    with pytest.raises(CheckpointIntegrityError, match="leaked SEK"):
        build_multi_market_checkpoint(
            {"sources": [no_source, se_source, de_source]},
            _matrix(),
            root=tmp_path,
        )


def test_checkpoint_reconciles_persistence_counts(tmp_path: Path) -> None:
    no_source = _standard_source(
        tmp_path,
        "no",
        market="NO",
        currency="NOK",
        candidates=[],
    )
    se_source = _standard_source(
        tmp_path,
        "se",
        market="SE",
        currency="SEK",
        candidates=[],
    )
    de_source = _standard_source(
        tmp_path,
        "de",
        market="DE",
        currency="EUR",
        candidates=[{"opportunity_identity": "de:1", "listing_status": "ENDED"}],
    )
    _write(
        tmp_path / "de" / "unified-persistence-summary.json",
        {"status": "SUCCESS", "persisted_record_count": 0},
    )
    with pytest.raises(CheckpointIntegrityError, match="persisted count"):
        build_multi_market_checkpoint(
            {"sources": [no_source, se_source, de_source]},
            _matrix(),
            root=tmp_path,
        )
