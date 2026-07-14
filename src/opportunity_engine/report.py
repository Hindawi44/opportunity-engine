import csv
from pathlib import Path
from typing import Iterable

from .evaluator import evaluate_opportunity
from .models import Opportunity


def write_evaluation_report(
    opportunities: Iterable[Opportunity],
    output_path: str | Path,
) -> Path:
    """Evaluate auction opportunities and save a CSV report."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "title",
        "auction_url",
        "purchase_price",
        "vat_cost",
        "extra_costs",
        "total_cost",
        "expected_resale_value",
        "expected_profit",
        "return_percent",
        "maximum_bid",
        "risk_score",
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
                    "auction_url": item.auction_url,
                    "purchase_price": item.purchase_price,
                    "vat_cost": result.vat_cost,
                    "extra_costs": result.extra_costs,
                    "total_cost": result.total_cost,
                    "expected_resale_value": item.expected_resale_value,
                    "expected_profit": result.expected_profit,
                    "return_percent": result.return_percent,
                    "maximum_bid": result.maximum_bid,
                    "risk_score": item.risk_score,
                    "classification": result.classification,
                    "reason": result.reason,
                }
            )

    return target
