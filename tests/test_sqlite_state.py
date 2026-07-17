from __future__ import annotations

from opportunity_engine.ods.sqlite_state import SQLiteStateStore, StateFile


def test_sqlite_state_round_trip(tmp_path) -> None:
    database = tmp_path / "state.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    feed = source / "feed.json"
    runs = source / "runs.jsonl"
    feed.write_text('{"records":{"one":{"status":"NEW"}}}', encoding="utf-8")
    runs.write_text('{"run_id":"one"}\n', encoding="utf-8")

    store = SQLiteStateStore(database)
    captured = store.capture(
        (StateFile("feed.json", feed), StateFile("runs.jsonl", runs))
    )
    assert captured == 2
    assert store.snapshot_names() == ("feed.json", "runs.jsonl")

    feed.unlink()
    runs.unlink()
    restored = store.materialize(
        (StateFile("feed.json", feed), StateFile("runs.jsonl", runs))
    )
    assert restored == 2
    assert '"status":"NEW"' in feed.read_text(encoding="utf-8")
    assert runs.read_text(encoding="utf-8").endswith("\n")


def test_capture_ignores_missing_files(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    captured = store.capture((StateFile("missing", tmp_path / "missing.json"),))
    assert captured == 0
    assert store.snapshot_names() == ()
