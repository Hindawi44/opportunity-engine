from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from opportunity_engine.discovery import market_comparables_benchmark as base
from opportunity_engine.discovery.market_comparables_target_hydration import (
    FEED_FAMILY,
    hydrate_items_report,
    load_local_source_records,
    quality_query_core,
    safe_target_price,
    select_quality_benchmark_targets,
    write_hydrated_market_comparables_benchmark,
)
from opportunity_engine.discovery.search_provider import SearchHit


def _item(
    item_id: str,
    title: str,
    url: str,
    *,
    details: dict | None = None,
    record_kind: str = "CANONICAL_OPPORTUNITY",
) -> dict:
    return {
        "intelligence_id": item_id,
        "record_kind": record_kind,
        "title": title,
        "source_name": "Auksjonen.no",
        "source_country": "NO",
        "source_url": url,
        "score": 80,
        "details": details or {},
    }


def _river() -> tuple[dict, dict, dict]:
    generic = _item(
        "generic:1",
        "Auksjonen.No AS, Sem",
        "https://www.finn.no/471396147",
    )
    gsa = _item(
        "gsa:1",
        "10 stk GSA multinorm arbeidsplagg – 9 kjeledresser + 1 jakke – Str. 62 (2XL)",
        "https://ny.auksjonen.no/auksjon/torget/gsa/528194",
    )
    bjorn = _item(
        "bjorn:1",
        "Parti Björnkläder arbeidsklær og varselklær",
        "https://ny.auksjonen.no/auksjon/torget/bjorn/574647",
    )
    brief = {
        "actionable_now": [
            {"case_id": "case:generic", "headline": generic["title"], "actionability_score": 92},
            {"case_id": "case:gsa", "headline": gsa["title"], "actionability_score": 95},
            {"case_id": "case:bjorn", "headline": bjorn["title"], "actionability_score": 90},
        ]
    }
    cases = {
        "cases": [
            {"case_id": "case:generic", "item_ids": ["generic:1"]},
            {"case_id": "case:gsa", "item_ids": ["gsa:1"]},
            {"case_id": "case:bjorn", "item_ids": ["bjorn:1"]},
        ]
    }
    return brief, cases, {"items": [generic, gsa, bjorn]}


def _source_record(url: str, current_bid: float) -> dict:
    return {
        "title": "source",
        "url": url,
        "current_bid_nok": current_bid,
        "ends_at": "2026-08-10T17:16:00+00:00",
        "_hydration_artifact": "auksjonen-live-clothing-listings.json",
        "_hydration_currency": "NOK",
    }


def test_hydrates_bid_quantity_currency_brand_and_end_time() -> None:
    _, _, items = _river()
    gsa_url = items["items"][1]["source_url"]
    hydrated, provenance = hydrate_items_report(items, [_source_record(gsa_url, 100)])
    gsa = hydrated["items"][1]
    assert gsa["details"]["current_bid"] == 100
    assert gsa["details"]["quantity"] == 10
    assert gsa["details"]["quantity_unit"] == "items"
    assert gsa["details"]["unit_hint"] == "items"
    assert gsa["details"]["currency"] == "NOK"
    assert gsa["details"]["brands"] == ["GSA"]
    assert gsa["details"]["auction_end_text"] == "2026-08-10T17:16:00+00:00"
    assert provenance["gsa:1"]["status"] == "HYDRATED"
    assert "current_bid" in provenance["gsa:1"]["fields_added"]


def test_selection_skips_generic_company_title_and_continues() -> None:
    brief, cases, items = _river()
    source_records = [
        _source_record(items["items"][1]["source_url"], 100),
        _source_record(items["items"][2]["source_url"], 2000),
    ]
    hydrated, _ = hydrate_items_report(items, source_records)
    targets = select_quality_benchmark_targets(brief, cases, hydrated, max_targets=2)
    assert [target["intelligence_id"] for target in targets] == ["gsa:1", "bjorn:1"]


def test_safe_target_price_divides_only_when_quantity_is_known() -> None:
    brief, cases, items = _river()
    source_records = [
        _source_record(items["items"][1]["source_url"], 100),
        _source_record(items["items"][2]["source_url"], 2000),
    ]
    hydrated, _ = hydrate_items_report(items, source_records)
    targets = select_quality_benchmark_targets(brief, cases, hydrated, max_targets=2)
    gsa_price = safe_target_price(targets[0], {"NOK": 1.0})
    bjorn_price = safe_target_price(targets[1], {"NOK": 1.0})
    assert gsa_price["amount"] == 10
    assert gsa_price["basis"] == "PER_ITEM"
    assert gsa_price["visible_total_amount"] == 100
    assert bjorn_price["amount"] is None
    assert bjorn_price["visible_total_amount"] == 2000
    assert bjorn_price["unit_price_requires_quantity"] is True


def test_query_core_is_product_focused_and_removes_size_noise() -> None:
    brief, cases, items = _river()
    hydrated, _ = hydrate_items_report(
        items,
        [_source_record(items["items"][1]["source_url"], 100)],
    )
    target = select_quality_benchmark_targets(brief, cases, hydrated, max_targets=1)[0]
    core = quality_query_core(target)
    assert '"GSA"' in core
    assert "multinorm" in core
    assert "kjeledresser" in core
    assert "Str" not in core
    assert "62" not in core
    assert "2XL" not in core
    assert "10 " not in core


def test_loads_only_manifest_named_local_source_reports(tmp_path: Path) -> None:
    output = tmp_path / "artifacts" / "multi-market-daily-operator-checkpoint"
    source = tmp_path / "artifacts" / "multi-market-inputs" / "no-auksjonen"
    output.mkdir(parents=True)
    source.mkdir(parents=True)
    (output / "input-manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "artifact_dir": "artifacts/multi-market-inputs/no-auksjonen",
                        "currency": "NOK",
                        "report_file": "auksjonen-live-clothing-listings.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (source / "auksjonen-live-clothing-listings.json").write_text(
        json.dumps(
            {
                "listings": [
                    {
                        "url": "https://ny.auksjonen.no/auksjon/torget/gsa/528194",
                        "current_bid_nok": 100,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    records = load_local_source_records(output)
    assert len(records) == 1
    assert records[0]["current_bid_nok"] == 100
    assert records[0]["_hydration_currency"] == "NOK"


class FakeProvider:
    @property
    def name(self) -> str:
        return "Fake Brave"

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]:
        if any(term in query.casefold() for term in ("engros", "parti", "restlager")):
            return []
        return [
            SearchHit(
                title=f"GSA multinorm kjeledress {index}",
                url=f"https://retail-{index}.example/gsa",
                description=f"GSA multinorm workwear jacket {700 + index * 20} NOK",
                provider="Fake Brave",
            )
            for index in range(1, 6)
        ]


def test_writer_hydrates_target_skips_generic_and_produces_comparison(tmp_path: Path) -> None:
    output = tmp_path / "artifacts" / "multi-market-daily-operator-checkpoint"
    source = tmp_path / "artifacts" / "multi-market-inputs" / "no-auksjonen"
    output.mkdir(parents=True)
    source.mkdir(parents=True)
    brief, cases, items = _river()
    (output / "unified-daily-decision-brief.json").write_text(json.dumps(brief), encoding="utf-8")
    (output / "unified-market-cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (output / "unified-intelligence-items.json").write_text(json.dumps(items), encoding="utf-8")
    (output / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"unified_market_intelligence_river": {"status": "SUCCESS"}}),
        encoding="utf-8",
    )
    (output / "domain-market-intelligence-brief.txt").write_text("BASE\n", encoding="utf-8")
    (output / "input-manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "artifact_dir": "artifacts/multi-market-inputs/no-auksjonen",
                        "currency": "NOK",
                        "report_file": "auksjonen-live-clothing-listings.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (source / "auksjonen-live-clothing-listings.json").write_text(
        json.dumps(
            {
                "listings": [
                    {
                        "url": items["items"][1]["source_url"],
                        "current_bid_nok": 100,
                        "ends_at": "2026-08-09T12:02:00+00:00",
                    },
                    {
                        "url": items["items"][2]["source_url"],
                        "current_bid_nok": 2000,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = write_hydrated_market_comparables_benchmark(
        output,
        environment={"BRAVE_SEARCH_API_KEY": "secret"},
        provider_factory=lambda *_: FakeProvider(),
    )
    assert report["target_hydration_feed_family"] == FEED_FAMILY
    assert report["generic_actionable_targets_skipped"] == 1
    assert report["hydrated_item_count"] >= 2
    assert report["target_benchmarks"][0]["title"].startswith("10 stk GSA")
    assert report["target_benchmarks"][0]["target_price"]["amount"] == 10
    assert report["target_benchmarks"][0]["benchmark_classification"] == "CLEARLY_BELOW_MARKET"
    assert report["target_benchmarks"][0]["target_hydration"]["status"] == "HYDRATED"
    assert report["automatic_purchase"] is False
    assert (output / base.OUTPUT_FILENAME).exists()
