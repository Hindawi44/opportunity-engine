import csv
from pathlib import Path
from typing import Iterable

from .evaluator import evaluate_opportunity
from .models import Opportunity


def write_evaluation_report(
    opportunities: Iterable[Opportunity],
    output_path: str | Path,
) -> Path:
    """Evaluate opportunities and save a CSV report."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "title",
        "total_cost",
        "expected_profit",
        "return_percent",
        "maximum_bid",
        "classification",
        "reason",
    ]

    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for item in opportunities:
            result = evaluate_opportunity(item)
            writer.writerow(
                {
                    "title": item.title,
                    "total_cost": result.total_cost,
                    "expected_profit": result.expected_profit,
                    "return_percent": result.return_percent,
                    "maximum_bid": result.maximum_bid,
                    "classification": result.classification,
                    "reason": result.reason,
                }
            )

    return target
