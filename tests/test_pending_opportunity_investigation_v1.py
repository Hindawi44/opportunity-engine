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


def test_selects_public_url_from_opportunity_identity_when_source_url_missing() -> None:
    identity_url = "https://market.example/item/123"
    report = {
        "deduplicated_opportunities": [
            _record(identity_url, 90, source_url="", canonical_url="", url=""),
        ]
    }
    selected = select_pending_opportunities(report, limit=1)
    assert [row["opportunity_identity"] for row in selected] == [identity_url]


def test_investigation_uses_identity_url_and_exposes_backlog_counts() -> None:
    identity_url = "https://market.example/item/123"
    report = {
        "deduplicated_opportunities": [
            _record(identity_url, 90, source_url="", canonical_url="", url=""),
            _record("missing-everywhere", 80, source_url="", canonical_url="", url=""),
        ]
    }
    seen = []

    def fetch(url: str):
        seen.append(url)
        return SimpleNamespace(
            ok=True,
            title="Restlager klær 20 stk til salgs 100 NOK",
            text="Restlager klær 20 stk til salgs 100 NOK",
            raw_html="",
            final_url=url,
            status_code=200,
            error=None,
        )

    result = investigate_pending_opportunities(report, page_fetcher=fetch)
    assert seen == [identity_url]
    assert result["selection_status"] == "SELECTED_FOR_INVESTIGATION"
    assert result["pending_candidate_count"] == 2
    assert result["selectable_pending_count"] == 1
    assert result["unselectable_pending_count"] == 1
    assert result["selected_count"] == 1
    assert result["investigated_count"] == 1


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
