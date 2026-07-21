import json
import subprocess
import sys
from pathlib import Path


def _run(tmp_path: Path, evidence: dict[str, object] | None = None) -> dict[str, object]:
    queue_path = tmp_path / "queue.json"
    evidence_path = tmp_path / "evidence.json"
    output_path = tmp_path / "output.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "opportunity_id": "opp-1",
                        "title": "Butikkinnredning",
                        "url": "https://example.test/1",
                        "priority": 1,
                        "asking_price_nok": 1000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    if evidence is not None:
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/build_economic_evaluation_queue.py",
            "--queue",
            str(queue_path),
            "--evidence",
            str(evidence_path),
            "--output",
            str(output_path),
        ],
        check=True,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_missing_evidence_blocks_recommendation(tmp_path: Path) -> None:
    payload = _run(tmp_path)
    evaluation = payload["evaluations"][0]
    assert evaluation["decision"] == "EVIDENCE_REQUIRED"
    assert evaluation["expected_profit_nok"] is None
    assert "three_verified_market_comparables" in evaluation["missing_evidence"]


def test_complete_evidence_calculates_conservative_numbers(tmp_path: Path) -> None:
    payload = _run(
        tmp_path,
        {
            "opp-1": {
                "market_comparables_nok": [5000, 4500, 6000],
                "auction_fee_nok": 100,
                "vat_nok": 250,
                "transport_cost_nok": 500,
                "dismantling_cost_nok": 100,
                "storage_cost_nok": 0,
                "repair_cost_nok": 0,
                "other_costs_nok": 50,
            }
        },
    )
    evaluation = payload["evaluations"][0]
    assert evaluation["decision"] == "REVIEW_NUMBERS"
    assert evaluation["conservative_resale_value_nok"] == 4500.0
    assert evaluation["total_cost_nok"] == 2000.0
    assert evaluation["expected_profit_nok"] == 2500.0
    assert evaluation["roi_percent"] == 125.0
