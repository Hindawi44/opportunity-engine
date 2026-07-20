import json
from datetime import datetime, timezone

import pytest

from opportunity_engine.ods.price_history import HistoricalPriceDatabase


def _time(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=timezone.utc)


def test_records_first_price_and_persists_atomically(tmp_path) -> None:
    path = tmp_path / "history.json"
    database = HistoricalPriceDatabase(path)

    summary = database.record("opportunity-1", 10_000, observed_at=_time(20))
    database.save()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert summary.status == "new"
    assert summary.first_price_nok == 10_000
    assert summary.current_price_nok == 10_000
    assert summary.price_change_count == 0
    assert payload["schema_version"] == 1
    assert payload["opportunities"]["opportunity-1"]["prices"][0]["price_nok"] == 10_000
    assert not (tmp_path / "history.json.tmp").exists()


def test_tracks_drop_increase_min_max_and_age(tmp_path) -> None:
    path = tmp_path / "history.json"
    database = HistoricalPriceDatabase(path)
    database.record("opportunity-1", 10_000, observed_at=_time(20))
    drop = database.record("opportunity-1", 8_000, observed_at=_time(22))
    increase = database.record("opportunity-1", 9_000, observed_at=_time(25))

    assert drop.status == "price_drop"
    assert drop.significant_drop is True
    assert drop.change_from_first == -0.2
    assert increase.status == "price_increase"
    assert increase.lowest_price_nok == 8_000
    assert increase.highest_price_nok == 10_000
    assert increase.price_change_count == 2
    assert increase.age_days == 5


def test_repeated_same_price_does_not_create_fake_change(tmp_path) -> None:
    database = HistoricalPriceDatabase(tmp_path / "history.json")
    database.record("opportunity-1", 10_000, observed_at=_time(20))
    summary = database.record("opportunity-1", 10_000, observed_at=_time(21))

    assert summary.price_change_count == 0
    assert summary.current_price_nok == 10_000
    assert summary.last_seen_at.startswith("2026-07-21")


def test_missing_price_remains_unknown(tmp_path) -> None:
    database = HistoricalPriceDatabase(tmp_path / "history.json")
    summary = database.record("opportunity-1", None, observed_at=_time(20))

    assert summary.status == "unpriced"
    assert summary.current_price_nok is None
    assert summary.lowest_price_nok is None


def test_rejects_invalid_price_and_invalid_database(tmp_path) -> None:
    database = HistoricalPriceDatabase(tmp_path / "history.json")
    with pytest.raises(ValueError, match="negative"):
        database.record("opportunity-1", -1)

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="schema"):
        HistoricalPriceDatabase(invalid)
