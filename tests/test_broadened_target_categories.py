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
        ],
        check=True,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_accepts_practical_shop_warehouse_and_office_categories(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        [
            {"opportunity_id": "shop", "title": "Butikkreol og kassadisk", "asking_price_nok": 1500},
            {"opportunity_id": "warehouse", "title": "Pakkebord og stålreol", "asking_price_nok": 900},
            {"opportunity_id": "office", "title": "Møtebord og arkivskap", "asking_price_nok": 700},
        ],
    )

    assert payload["selected_count"] == 3
    assert {item["opportunity_id"] for item in payload["queue"]} == {
        "shop",
        "warehouse",
        "office",
    }


def test_accepts_textile_and_sewing_categories(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        [
            {"opportunity_id": "textile", "title": "Stoffparti og metervare", "asking_price_nok": 500},
            {"opportunity_id": "sewing", "title": "Industrisymaskin og overlock", "asking_price_nok": 2500},
        ],
    )

    assert payload["selected_count"] == 2
    assert {item["opportunity_id"] for item in payload["queue"]} == {"textile", "sewing"}


def test_still_excludes_vehicles_and_unrelated_goods(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        [
            {
                "opportunity_id": "car",
                "title": "Audi e-tron med skap",
                "url": "https://www.auksjonen.no/auksjon/bruktbil/audi/1",
                "asking_price_nok": 100000,
            },
            {"opportunity_id": "art", "title": "Original litografi", "asking_price_nok": 200},
        ],
    )

    assert payload["selected_count"] == 0
    assert payload["queue"] == []
