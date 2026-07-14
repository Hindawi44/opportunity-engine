from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from opportunity_engine.io import load_opportunities_csv
from opportunity_engine.report import write_evaluation_report


def main() -> None:
    source = ROOT / "data" / "opportunities.csv"
    output = ROOT / "reports" / "opportunity_report.csv"

    opportunities = load_opportunities_csv(source)
    report_path = write_evaluation_report(opportunities, output)

    print(f"تم إنشاء التقرير: {report_path}")
    print(f"عدد الفرص: {len(opportunities)}")


if __name__ == "__main__":
    main()
