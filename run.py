from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from opportunity_engine import Opportunity, evaluate_opportunity


def main() -> None:
    sample = Opportunity(
        title="تجهيزات محل مستعملة",
        purchase_price=10_000,
        buyer_fee=1_500,
        transport_cost=2_000,
        repair_cost=500,
        expected_resale_value=22_000,
        risk_score=2,
    )

    result = evaluate_opportunity(sample)

    print(f"الفرصة: {sample.title}")
    print(f"التكلفة الكلية: {result.total_cost:.2f} NOK")
    print(f"الربح المتوقع: {result.expected_profit:.2f} NOK")
    print(f"العائد المتوقع: {result.return_percent:.2f}%")
    print(f"الحد الأقصى للمزايدة: {result.maximum_bid:.2f} NOK")
    print(f"القرار: {result.classification}")
    print(f"السبب: {result.reason}")


if __name__ == "__main__":
    main()
