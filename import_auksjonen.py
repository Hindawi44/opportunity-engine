from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from opportunity_engine.auksjonen_import import load_auksjonen_csv
from opportunity_engine.report import write_evaluation_report


def main() -> None:
    source = ROOT / "data" / "auksjonen_sample.csv"
    output = ROOT / "reports" / "auksjonen_report.csv"

    opportunities = load_auksjonen_csv(source)
    report_path = write_evaluation_report(opportunities, output)

    print(f"تم استيراد {len(opportunities)} فرصة من ملف المزاد.")
    print(f"تم إنشاء التقرير: {report_path}")


if __name__ == "__main__":
    main()
