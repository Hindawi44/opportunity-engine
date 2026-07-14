from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_engine.io import load_opportunities_csv
from opportunity_engine.report import write_evaluation_report


def test_load_and_write_report(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    source.write_text(
        "title,purchase_price,buyer_fee,transport_cost,repair_cost,expected_resale_value,risk_score\n"
        "Test item,1000,100,100,0,2000,2\n",
        encoding="utf-8",
    )

    opportunities = load_opportunities_csv(source)
    output = write_evaluation_report(opportunities, tmp_path / "report.csv")

    assert len(opportunities) == 1
    assert opportunities[0].title == "Test item"
    assert output.exists()
    report_text = output.read_text(encoding="utf-8-sig")
    assert "🟢 فرصة قوية" in report_text
