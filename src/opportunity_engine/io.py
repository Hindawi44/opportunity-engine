import csv
from pathlib import Path

from .models import Opportunity


def load_opportunities_csv(path: str | Path) -> list[Opportunity]:
    """Read opportunities from a UTF-8 CSV file."""
    source = Path(path)
    opportunities: list[Opportunity] = []

    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"title", "purchase_price", "expected_resale_value", "risk_score"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")

        for row in reader:
            opportunities.append(
                Opportunity(
                    title=row["title"].strip(),
                    purchase_price=float(row["purchase_price"] or 0),
                    buyer_fee=float(row.get("buyer_fee") or 0),
                    transport_cost=float(row.get("transport_cost") or 0),
                    repair_cost=float(row.get("repair_cost") or 0),
                    expected_resale_value=float(row["expected_resale_value"] or 0),
                    risk_score=int(row["risk_score"] or 3),
                )
            )

    return opportunities
