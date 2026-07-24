from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.external_comparables_accumulator import collect_persisted_comparables


def _write(path: Path, opportunity_id: str, url: str, price: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "opportunity_id": opportunity_id,
        "evidence_id": path.stem,
        "evidence_type": "market_price",
        "source_name": "test",
        "source_url": url,
        "metadata": {"similarity_score": 0.8, "comparable_title": "Comparable"},
        "observations": [{"numeric_value": price, "currency": "NOK", "observed_at": "2026-07-23T00:00:00+00:00"}],
    }), encoding="utf-8")


def test_accumulates_three_persisted_comparables(tmp_path: Path) -> None:
    _write(tmp_path / "opp" / "rev_1.json", "opp", "https://one.no/a", 1000)
    _write(tmp_path / "opp" / "rev_2.json", "opp", "https://two.no/b", 1200)
    _write(tmp_path / "opp" / "rev_3.json", "opp", "https://three.no/c", 1400)

    summary = collect_persisted_comparables(tmp_path)["opp"]

    assert summary.comparable_status == "COMPLETE"
    assert len(summary.verified_comparables) == 3
    assert summary.independent_domains == 3


def test_deduplicates_same_url_and_price(tmp_path: Path) -> None:
    _write(tmp_path / "opp" / "rev_1.json", "opp", "https://one.no/a?x=1", 1000)
    _write(tmp_path / "opp" / "rev_2.json", "opp", "https://one.no/a?x=2", 1000)

    summary = collect_persisted_comparables(tmp_path)["opp"]

    assert summary.comparable_status == "PARTIAL"
    assert len(summary.verified_comparables) == 1
    assert summary.duplicate_count == 1


def test_rejects_missing_currency_and_non_https(tmp_path: Path) -> None:
    bad = tmp_path / "opp" / "rev_bad.json"
    bad.parent.mkdir(parents=True)
    bad.write_text(json.dumps({
        "opportunity_id": "opp",
        "evidence_type": "market_price",
        "source_url": "http://unsafe.test/item",
        "observations": [{"numeric_value": 999, "currency": "EUR"}],
    }), encoding="utf-8")

    assert collect_persisted_comparables(tmp_path) == {}
