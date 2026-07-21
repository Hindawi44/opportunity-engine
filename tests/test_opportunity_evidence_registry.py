import json
import subprocess
import sys
from pathlib import Path


def _run(tmp_path: Path, existing: dict[str, object]) -> dict[str, object]:
    queue_path = tmp_path / "queue.json"
    existing_path = tmp_path / "existing.json"
    output_path = tmp_path / "output.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "opportunity_id": "opp-1",
                        "title": "Butikkinnredning",
                        "url": "https://example.test/auction",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    existing_path.write_text(json.dumps(existing), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/build_opportunity_evidence_registry.py",
            "--queue",
            str(queue_path),
            "--existing",
            str(existing_path),
            "--output",
            str(output_path),
        ],
        check=True,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_unknown_values_remain_null_and_block_verification(tmp_path: Path) -> None:
    payload = _run(tmp_path, {})
    record = payload["evidence"]["opp-1"]
    assert payload["evidence_count"] == 1
    assert payload["verified_count"] == 0
    assert record["verified"] is False
    assert record["auction_fee_nok"] is None
    assert "three_verified_market_comparables" in record["missing_evidence"]


def test_only_verified_documented_comparables_are_kept(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        {
            "opp-1": {
                "market_comparables": [
                    {
                        "source": "FINN",
                        "url": "https://example.test/1",
                        "price_nok": 5000,
                        "verified": True,
                    },
                    {
                        "source": "FINN",
                        "url": "https://example.test/2",
                        "price_nok": 5200,
                        "verified": False,
                    },
                    {
                        "source": "",
                        "url": "https://example.test/3",
                        "price_nok": 5300,
                        "verified": True,
                    },
                ]
            }
        },
    )
    record = payload["evidence"]["opp-1"]
    assert len(record["market_comparables"]) == 1
    assert record["market_comparables"][0]["price_nok"] == 5000.0


def test_complete_verified_record_is_marked_verified(tmp_path: Path) -> None:
    comparables = [
        {
            "source": "FINN",
            "url": f"https://example.test/{index}",
            "price_nok": 5000 + index * 100,
            "verified": True,
        }
        for index in range(3)
    ]
    payload = _run(
        tmp_path,
        {
            "evidence": {
                "opp-1": {
                    "market_comparables": comparables,
                    "auction_fee_nok": 100,
                    "vat_status": "included",
                    "vat_nok": 0,
                    "transport_cost_nok": 500,
                    "dismantling_cost_nok": 0,
                    "storage_cost_nok": 0,
                    "repair_cost_nok": 0,
                    "other_costs_nok": 0,
                }
            }
        },
    )
    record = payload["evidence"]["opp-1"]
    assert record["verified"] is True
    assert record["missing_evidence"] == []
    assert payload["verified_count"] == 1
