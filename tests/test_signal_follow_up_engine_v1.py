from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.signal_follow_up_engine import (
    build_signal_follow_up_plan,
    run_signal_follow_up_engine,
    write_signal_follow_up_engine,
)


NOW = datetime(2026, 8, 15, 6, 0, tzinfo=timezone.utc)


def _case(
    case_id: str,
    title: str,
    *,
    country: str = "DE",
    case_type: str = "COMPANY_LIQUIDATION",
    grouping_basis: str = "ITEM",
    grouping_key: str | None = None,
    last_seen: str = "2026-08-15T05:41:22+00:00",
    source_url: str | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "case_type": case_type,
        "case_title": title,
        "case_status": "WATCH",
        "countries": [country],
        "grouping_basis": grouping_basis,
        "grouping_key": grouping_key or f"item:{case_id}",
        "commercial_strength": 67.0,
        "last_seen": last_seen,
        "source_urls": [source_url] if source_url else [],
    }


def test_plan_builds_targeted_company_and_location_queries() -> None:
    cases = {
        "cases": [
            _case(
                "adenauer",
                "Adenauer & Co.: Modekette meldet Insolvenz an – glaubt aber an Erfolg",
                country="DE",
            ),
            _case(
                "knarvik",
                "Næringsliv, Knarvik | Klesbutikken er konkurs: – Har kjempa lenge",
                country="NO",
            ),
        ]
    }

    plan = build_signal_follow_up_plan(cases, max_cases=4)

    assert len(plan) == 2
    by_id = {row["case_id"]: row for row in plan}
    assert by_id["adenauer"]["target_label"] == "Adenauer & Co"
    assert by_id["adenauer"]["target_kind"] == "TITLE_COMPANY_PREFIX"
    assert '"Adenauer & Co"' in by_id["adenauer"]["query"]
    assert "Restposten" in by_id["adenauer"]["query"]
    assert by_id["knarvik"]["target_label"] == "Knarvik"
    assert by_id["knarvik"]["target_kind"] == "LOCATION_EVENT_FALLBACK"
    assert "varelager" in by_id["knarvik"]["query"]
    assert "klesbutikk" in by_id["knarvik"]["query"]


def test_plan_deduplicates_same_explicit_company_target() -> None:
    cases = {
        "cases": [
            _case(
                "newer",
                "Adenauer & Co.",
                grouping_basis="COMPANY",
                grouping_key="DE:adenauer-co",
                last_seen="2026-08-15T06:00:00+00:00",
            ),
            _case(
                "older",
                "Adenauer & Co.",
                grouping_basis="COMPANY",
                grouping_key="DE:adenauer-co",
                last_seen="2026-08-11T06:00:00+00:00",
            ),
        ]
    }

    plan = build_signal_follow_up_plan(cases, max_cases=4)

    assert [row["case_id"] for row in plan] == ["newer"]


def test_exact_grouping_can_link_existing_commercial_case_without_promoting() -> None:
    watch = _case(
        "watch",
        "Adenauer & Co.",
        grouping_basis="COMPANY",
        grouping_key="DE:adenauer-co",
    )
    commercial = _case(
        "commercial",
        "Adenauer & Co. stock lot",
        case_type="AUCTION_INVENTORY",
        grouping_basis="COMPANY",
        grouping_key="DE:adenauer-co",
    )
    commercial["case_status"] = "ACTIVE_REQUIRES_VERIFICATION"

    plan = build_signal_follow_up_plan({"cases": [watch, commercial]}, max_cases=4)

    assert len(plan) == 1
    assert plan[0]["explicit_linked_commercial_case_ids"] == ["commercial"]


class _FakeProvider:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        self.calls.append((query, count))
        return self.hits[:count]


def test_search_hit_is_only_unverified_lead_and_original_news_is_ignored() -> None:
    original = "https://example.com/news/adenauer-insolvenz"
    case = _case(
        "adenauer",
        "Adenauer & Co.: Modekette meldet Insolvenz an",
        source_url=original,
    )
    provider = _FakeProvider(
        [
            SearchHit(
                title="Adenauer & Co. Insolvenz",
                url=original,
                description="Modekette meldet Insolvenz an",
                provider="Brave Search",
            ),
            SearchHit(
                title="Adenauer & Co. Lagerverkauf",
                url="https://auction.example/adenauer-stock",
                description="Warenbestand und Restposten Bekleidung werden verkauft.",
                provider="Brave Search",
            ),
            SearchHit(
                title="Andere Firma Lagerverkauf",
                url="https://auction.example/other-stock",
                description="Restposten Bekleidung werden verkauft.",
                provider="Brave Search",
            ),
        ]
    )

    report = run_signal_follow_up_engine(
        {"cases": [case]},
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=NOW,
        max_cases=4,
        results_per_case=5,
    )

    assert report["status"] == "SUCCESS"
    assert report["search_request_count"] == 1
    assert report["commercial_lead_count"] == 1
    lead = report["cases"][0]["leads"][0]
    assert lead["source_url"] == "https://auction.example/adenauer-stock"
    assert lead["verification_status"] == "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT"
    assert lead["commercial_facts_confirmed"] is False
    assert lead["source_page_verification_required"] is True
    assert lead["promotion_to_opportunity_allowed"] is False
    assert report["promotion_to_opportunity_allowed"] is False
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def test_no_api_key_still_exposes_bounded_follow_up_plan() -> None:
    case = _case("adenauer", "Adenauer & Co.: Modekette meldet Insolvenz an")

    report = run_signal_follow_up_engine(
        {"cases": [case]},
        environment={},
        observed_at=NOW,
    )

    assert report["status"] == "SKIPPED_NO_API_KEY"
    assert report["selected_case_count"] == 1
    assert report["search_request_count"] == 0
    assert report["commercial_lead_count"] == 0
    assert report["cases"][0]["search_status"] == "SKIPPED_NO_API_KEY"


def test_write_attaches_summary_to_existing_single_daily_report(tmp_path: Path) -> None:
    output_dir = tmp_path
    (output_dir / "unified-market-cases.json").write_text(
        json.dumps(
            {
                "cases": [
                    _case(
                        "knarvik",
                        "Næringsliv, Knarvik | Klesbutikken er konkurs: – Har kjempa lenge",
                        country="NO",
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"schema_version": "domain-market-intelligence-brief-1.0"}),
        encoding="utf-8",
    )
    (output_dir / "domain-market-intelligence-brief.txt").write_text(
        "MARKET INTELLIGENCE\nالإجراء البشري الوحيد: CONTINUE_MONITORING\n",
        encoding="utf-8",
    )

    report = write_signal_follow_up_engine(
        output_dir,
        environment={},
        observed_at=NOW,
    )
    write_signal_follow_up_engine(
        output_dir,
        environment={},
        observed_at=NOW,
    )

    saved = json.loads((output_dir / "signal-follow-up-engine.json").read_text(encoding="utf-8"))
    domain = json.loads((output_dir / "domain-market-intelligence-brief.json").read_text(encoding="utf-8"))
    text = (output_dir / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")

    assert saved["schema_version"] == "signal-follow-up-engine-1.0"
    assert report["selected_case_count"] == 1
    assert domain["signal_follow_up_engine"]["selected_case_count"] == 1
    assert domain["signal_follow_up_engine"]["promotion_to_opportunity_allowed"] is False
    assert text.count("SIGNAL FOLLOW-UP ENGINE V1") == 1
    assert text.count("الإجراء البشري الوحيد:") == 1
