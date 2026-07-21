import json
import subprocess
import sys
from pathlib import Path


def _run(tmp_path: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    snapshot = tmp_path / "snapshot.json"
    output = tmp_path / "queue.json"
    snapshot.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/build_opportunity_review_queue.py",
            "--snapshot",
            str(snapshot),
            "--output",
            str(output),
            "--fallback-limit",
            "3",
        ],
        check=True,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_non_target_items_do_not_enter_fallback(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        [
            {"opportunity_id": "a", "title": "Arbeidsbord", "asking_price_nok": 500, "city": "Namsos"},
            {"opportunity_id": "b", "title": "Diverse parti", "asking_price_nok": 100},
            {"opportunity_id": "c", "title": "Liten arbeidsbenk", "asking_price_nok": 300},
            {"opportunity_id": "d", "title": "Personbil", "asking_price_nok": 1000},
        ],
    )
    assert payload["fallback_used"] is False
    assert payload["fallback_count"] == 0
    assert payload["selected_count"] == 0
    assert payload["queue"] == []


def test_strong_matches_take_precedence_over_fallback(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        [
            {"opportunity_id": "strong", "title": "Butikkinnredning med salgsdisk", "asking_price_nok": 1000},
            {"opportunity_id": "weak", "title": "Arbeidsbord", "asking_price_nok": 200},
        ],
    )
    assert payload["fallback_used"] is False
    assert payload["fallback_count"] == 0
    assert payload["selected_count"] == 1
    assert payload["queue"][0]["opportunity_id"] == "strong"
    assert payload["queue"][0]["status"] == "review_first"
