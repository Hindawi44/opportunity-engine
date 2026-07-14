import csv
from pathlib import Path

from .models import Opportunity


def _as_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "ja", "نعم"}


def load_opportunities_csv(path: str | Path) -> list[Opportunity]:
    """Read auction opportunities from a UTF-8 CSV file."""
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
                    dismantling_cost=float(row.get("dismantling_cost") or 0),
                    storage_cost=float(row.get("storage_cost") or 0),
                    other_costs=float(row.get("other_costs") or 0),
                    expected_resale_value=float(row["expected_resale_value"] or 0),
                    risk_score=int(row["risk_score"] or 3),
                    auction_url=(row.get("auction_url") or "").strip(),
                    vat_rate=float(row.get("vat_rate") or 0.25),
                    vat_applies_to_bid=_as_bool(row.get("vat_applies_to_bid")),
                )
            )

    return opportunities
