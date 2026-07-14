import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from opportunity_engine import Opportunity, evaluate_opportunity


def load_opportunities(path: Path) -> list[Opportunity]:
    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    return [Opportunity(**row) for row in rows]


def main() -> None:
    source = ROOT / "data" / "sample_opportunities.json"
    opportunities = load_opportunities(source)

    for item in opportunities:
        result = evaluate_opportunity(item)
        print("-" * 50)
        print(f"الفرصة: {item.title}")
        print(f"التكلفة الكلية: {result.total_cost:.2f} NOK")
        print(f"الربح المتوقع: {result.expected_profit:.2f} NOK")
        print(f"العائد: {result.return_percent:.2f}%")
        print(f"الحد الأقصى للمزايدة: {result.maximum_bid:.2f} NOK")
        print(f"القرار: {result.classification}")
        print(f"السبب: {result.reason}")


if __name__ == "__main__":
    main()
