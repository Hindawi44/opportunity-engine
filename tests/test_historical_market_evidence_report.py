from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace
from typing import Any, cast

import pytest

from opportunity_engine.persistence.historical_market_evidence_report import (
    build_historical_market_evidence_report,
    render_historical_market_evidence_summary,
    write_historical_market_evidence_report,
)
from opportunity_engine.persistence.repository import PersistenceError
from opportunity_engine.persistence.unified_repository import UnifiedOpportunityRepository


def _model(
    *,
    opportunity_id: str,
    title: str,
    workflow_status: str,
    bid_price: float | None,
    metadata: dict[str, Any],
    quantity: int | None = None,
) -> SimpleNamespace:
    observed_at = datetime(2026, 8, 1, 18, 30, tzinfo=timezone.utc)
    return SimpleNamespace(
        opportunity_id=opportunity_id,
        title=title,
        source_provider="Brave Search",
        source_url="https://blinto.se/auction/example",
        market_code="SE",
        listing_status="ENDED",
        evaluation_status=(
            "HISTORICAL_ONLY"
            if workflow_status == "HISTORICAL_MARKET_EVIDENCE"
            else "REQUIRES_VERIFICATION"
        ),
        workflow_status=workflow_status,
        scenario="LARGE_LOT_SALE",
        location="Växjö" if workflow_status == "HISTORICAL_MARKET_EVIDENCE" else None,
        inventory_type=(
            "workwear_inventory"
            if workflow_status == "HISTORICAL_MARKET_EVIDENCE"
            else None
        ),
        quantity=quantity,
        currency="SEK",
        bid_price=bid_price,
        record_json={"metadata": metadata},
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )


def _repository(
    *,
    trusted: list[SimpleNamespace],
    trusted_prices: list[SimpleNamespace],
    manual: list[SimpleNamespace],
) -> UnifiedOpportunityRepository:
    repository = UnifiedOpportunityRepository(cast(Any, object()))
    repository.list_trusted_historical_market_evidence = lambda: trusted  # type: ignore[method-assign]
    repository.list_trusted_historical_price_records = lambda: trusted_prices  # type: ignore[method-assign]
    repository.list_historical_evidence_manual_review = lambda: manual  # type: ignore[method-assign]
    return repository


def test_builds_separate_trusted_and_manual_review_sections() -> None:
    trusted = _model(
        opportunity_id="blinto-auction:178629:85260",
        title="Arbetskläder - Blåkläder",
        workflow_status="HISTORICAL_MARKET_EVIDENCE",
        bid_price=5400,
        quantity=38,
        metadata={
            "source_object_id": "178629",
            "auction_occurrence_id": "85260",
            "verification_content_match": True,
            "historical_market_evidence_eligible": True,
            "historical_data_fields_trusted": True,
            "bid_price_trusted": True,
            "reference_value_trusted": True,
            "exclude_from_historical_price_analysis": False,
            "bid_price_sek": 5400,
            "bid_price_currency": "SEK",
            "reference_value_sek": 50000,
            "reference_value_kind": "market_or_retail_reference",
        },
    )
    manual = _model(
        opportunity_id="item-url:https://blinto.se/auction/Arbetsbyxor-Double-W",
        title="Blinto - Restparti - Arbetsbyxor Double W.",
        workflow_status="CLOSED",
        bid_price=None,
        metadata={
            "verification_content_match": False,
            "historical_market_evidence_eligible": False,
            "historical_data_fields_trusted": False,
            "bid_price_trusted": False,
            "exclude_from_historical_price_analysis": True,
            "historical_price_analysis_exclusion_reason": "verification_content_mismatch",
            "bid_price_sek": 2000,
            "bid_price_currency": "SEK",
        },
    )

    report = build_historical_market_evidence_report(
        _repository(trusted=[trusted], trusted_prices=[trusted], manual=[manual]),
        generated_at=datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc),
    )

    assert report["summary"] == {
        "trusted_historical_evidence_count": 1,
        "trusted_historical_price_record_count": 1,
        "manual_review_count": 1,
        "total_reported_record_count": 2,
    }
    trusted_item = report["trusted_historical_market_evidence"][0]
    assert trusted_item["bid_price"] == 5400
    assert trusted_item["price_analysis_eligible"] is True
    assert trusted_item["auction_occurrence_id"] == "85260"

    manual_item = report["manual_review"][0]
    assert manual_item["bid_price"] is None
    assert manual_item["raw_bid_price_amount"] == 2000
    assert manual_item["price_analysis_eligible"] is False
    assert manual_item["exclude_from_historical_price_analysis"] is True


def test_writes_json_and_operator_text_summary(tmp_path) -> None:
    trusted = _model(
        opportunity_id="blinto-auction:178629:85260",
        title="Arbetskläder - Blåkläder",
        workflow_status="HISTORICAL_MARKET_EVIDENCE",
        bid_price=5400,
        quantity=38,
        metadata={
            "historical_market_evidence_eligible": True,
            "historical_data_fields_trusted": True,
            "bid_price_trusted": True,
            "exclude_from_historical_price_analysis": False,
        },
    )
    repository = _repository(trusted=[trusted], trusted_prices=[trusted], manual=[])

    report, report_path, summary_path = write_historical_market_evidence_report(
        repository,
        tmp_path,
        generated_at=datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc),
    )

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    summary = summary_path.read_text(encoding="utf-8")
    assert saved == report
    assert "Trusted historical evidence: 1" in summary
    assert "5400 SEK" in summary
    assert "Manual review:\n- None" in summary
    assert render_historical_market_evidence_summary(report) == summary


def test_report_fails_closed_when_sections_overlap() -> None:
    model = _model(
        opportunity_id="duplicate-id",
        title="Conflicting record",
        workflow_status="HISTORICAL_MARKET_EVIDENCE",
        bid_price=1000,
        metadata={
            "historical_market_evidence_eligible": True,
            "historical_data_fields_trusted": True,
            "bid_price_trusted": True,
            "exclude_from_historical_price_analysis": False,
        },
    )

    with pytest.raises(PersistenceError, match="sections overlap"):
        build_historical_market_evidence_report(
            _repository(trusted=[model], trusted_prices=[model], manual=[model]),
            generated_at=datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc),
        )
