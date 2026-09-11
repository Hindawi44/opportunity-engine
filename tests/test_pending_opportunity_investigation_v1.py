from types import SimpleNamespace

from scripts.run_pending_opportunity_investigation import (
    investigate_pending_opportunities,
    select_pending_opportunities,
)


def _record(identity: str, score: int, **extra):
    row = {
        "opportunity_identity": identity,
        "title": f"Lot {identity}",
        "market_code": "NO",
        "source_url": f"https://example.test/item/{identity}",
        "listing_status": "ACTIVE",
        "workflow_status": "REQUIRES_VERIFICATION",
        "discovery_score": score,
    }
    row.update(extra)
    return row


def test_selects_highest_scoring_pending_records_only() -> None:
    report = {
        "deduplicated_opportunities": [
            _record("low", 10),
            _record("high", 90),
            _record("ended", 100, listing_status="ENDED"),
            _record("missing-url", 95, source_url=""),
        ]
    }
    selected = select_pending_opportunities(report, limit=1)
    assert [row["opportunity_identity"] for row in selected] == ["high"]


def test_investigation_records_verified_and_failed_without_promoting() -> None:
    report = {"deduplicated_opportunities": [_record("good", 90), _record("bad", 80)]}

    def fetch(url: str):
        if url.endswith("good"):
            return SimpleNamespace(
                ok=True,
                title="Restlager klær 20 stk til salgs 100 NOK",
                text="Restlager klær 20 stk til salgs 100 NOK",
                raw_html="",
                final_url=url,
                status_code=200,
                error=None,
            )
        return SimpleNamespace(ok=False, error="blocked", final_url=url, status_code=403)

    result = investigate_pending_opportunities(report, page_fetcher=fetch)
    assert result["status_counts"]["VERIFIED_EXACT_LOT_CANDIDATE"] == 1
    assert result["status_counts"]["FETCH_FAILED"] == 1
    assert result["promotion_to_opportunity_allowed"] is False
